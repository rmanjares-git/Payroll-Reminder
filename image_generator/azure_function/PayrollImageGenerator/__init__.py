"""
Azure Function — HTTP Trigger
==============================
Generates payroll reminder images and uploads them to SharePoint.
Called by the Power Automate flow at 8:30 AM PHT (30 min before the Teams
approval card is sent to Nireen), so the images are always up-to-date.

POST /api/PayrollImageGenerator
Body (optional JSON):
  { "date": "2026-04-10" }    ← override date for testing
  { "trigger_day": 25 }       ← override trigger day

Returns JSON:
  {
    "reminder1_url": "https://...",
    "cutoff_url":    "https://..."
  }
"""

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

import azure.functions as func

# Local modules (deployed alongside this function)
from generate_images import generate_all
from sharepoint_upload import upload_all


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("PayrollImageGenerator triggered.")

    # ── Parse optional overrides from request body ──────────────────────────
    try:
        body = req.get_json()
    except Exception:
        body = {}

    reference_date = None
    trigger_day    = None

    if "date" in body:
        try:
            reference_date = datetime.strptime(body["date"], "%Y-%m-%d")
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid date format. Use YYYY-MM-DD."}),
                status_code=400,
                mimetype="application/json",
            )

    if "trigger_day" in body:
        trigger_day = int(body["trigger_day"])
        if trigger_day not in (10, 25):
            return func.HttpResponse(
                json.dumps({"error": "trigger_day must be 10 or 25."}),
                status_code=400,
                mimetype="application/json",
            )

    # ── Generate images into a temp directory ───────────────────────────────
    try:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            generate_all(
                trigger_day=trigger_day,
                output_dir=output_dir,
                reference_date=reference_date,
            )

            # ── Upload to SharePoint ─────────────────────────────────────────
            urls = upload_all(output_dir)

    except Exception as exc:
        logging.exception("Image generation or upload failed.")
        return func.HttpResponse(
            json.dumps({"error": str(exc)}),
            status_code=500,
            mimetype="application/json",
        )

    # ── Return SharePoint URLs to Power Automate ─────────────────────────────
    payload = {
        "reminder1_url": urls.get("Reminder 1.png", ""),
        "cutoff_url":    urls.get("Payroll Cut-off & Approval Period.png", ""),
    }
    logging.info("Success: %s", payload)

    return func.HttpResponse(
        json.dumps(payload),
        status_code=200,
        mimetype="application/json",
    )
