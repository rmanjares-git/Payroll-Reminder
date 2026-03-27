#!/usr/bin/env python3
"""
Payroll Reminder Image Generator
=================================
Generates branded PNG images for Smartsourcing payroll cut-off reminders:
  1. Payroll Cut-off & Approval Period.png  — the schedule table
  2. Reminder 1.png                         — the payroll schedule infographic

Usage:
  python generate_images.py                  # auto-detects trigger day from today
  python generate_images.py 2026-04-10       # test with a specific date
  python generate_images.py 2026-04-25       # test with 25th trigger
"""

import base64
import sys
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright


# ---------------------------------------------------------------------------
# Date calculation helpers
# ---------------------------------------------------------------------------

def _ordinal(n: int) -> str:
    """Return ordinal suffix: 1st, 2nd, 3rd, 4th, 20th, 21st, etc."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{('st', 'nd', 'rd')[n % 10 - 1] if n % 10 in (1, 2, 3) else 'th'}"


def get_payroll_dates(trigger_day: int, ref: datetime) -> dict:
    """
    Calculate all payroll cycle dates for the given trigger day (10 or 25).

    Cycle A — 10th trigger:
      Period:    26th of prev month  →  10th of current month
      Payday:    20th of current month

    Cycle B — 25th trigger:
      Period:    11th of current month  →  25th of current month
      Payday:    5th of next month
    """
    y, m = ref.year, ref.month

    if trigger_day == 10:
        pm = m - 1 if m > 1 else 12
        py = y if m > 1 else y - 1
        period_start    = datetime(py, pm, 26)
        period_end      = datetime(y, m, 10)
        level1          = datetime(y, m, 11)
        draft           = datetime(y, m, 12)
        dispute         = datetime(y, m, 13)
        proc_start      = datetime(y, m, 10)
        proc_end        = datetime(y, m, 18)
        payday          = datetime(y, m, 20)
    else:  # 25
        nm = m + 1 if m < 12 else 1
        ny = y if m < 12 else y + 1
        period_start    = datetime(y, m, 11)
        period_end      = datetime(y, m, 25)
        level1          = datetime(y, m, 26)
        draft           = datetime(y, m, 27)
        dispute         = datetime(y, m, 28)
        proc_start      = datetime(y, m, 25)
        proc_end        = datetime(ny, nm, 2)
        payday          = datetime(ny, nm, 5)

    period_label = (
        f"{period_start.strftime('%B %d')} to "
        f"{period_end.strftime('%B %d, %Y')}"
    )
    processing_range = (
        f"{proc_start.strftime('%B %d')} to "
        f"{proc_end.strftime('%B %d, %Y')}"
    )

    return {
        # Schedule table fields
        "period_label":       period_label,
        "level1_day":         level1.strftime("%A"),
        "level1_date":        level1.strftime("%B %d, %Y"),
        "level1_time":        "5 PM",
        "draft_day":          draft.strftime("%A"),
        "draft_date":         draft.strftime("%B %d, %Y"),
        "dispute_day":        dispute.strftime("%A"),
        "dispute_date":       dispute.strftime("%B %d, %Y"),
        "dispute_time":       "11 PM",
        "processing_range":   processing_range,
        # Reminder infographic fields
        "payday_label":       f"{payday.strftime('%B')} {_ordinal(payday.day)}",
        "payday_full":        payday.strftime("%B %d, %Y"),
    }


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _logo_to_data_uri(path: Path) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"


def _load_logo_symbol_data_uri() -> str:
    """
    Teal infinity symbol only (no text) as a transparent PNG data URI.
    Text is rendered as sharp CSS in the templates instead of from a raster source.
    """
    return _logo_to_data_uri(Path(__file__).parent / "templates" / "logo_symbol.png")


def _render_html(template_name: str, context: dict) -> str:
    """Render a Jinja2 HTML template with the given context."""
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=False)
    return env.get_template(template_name).render(**context)


def _html_to_png(html: str, output_path: Path, width: int, height: int) -> None:
    """
    Render HTML to PNG at 2× pixel density for sharp, crisp output.
    device_scale_factor=2 doubles the rendered pixels (like a Retina display),
    so the output image is width×2 × height×2 at full quality.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=2,
        )
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(output_path))
        browser.close()
    print(f"  Saved: {output_path.name}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_all(
    trigger_day: int = None,
    output_dir: Path = None,
    reference_date: datetime = None,
) -> Path:
    """
    Generate both reminder images.

    Args:
        trigger_day:    10 or 25. If None, uses the day of reference_date.
        output_dir:     Where to save the PNGs. Defaults to ./output/
        reference_date: Override 'today'. Defaults to datetime.now().

    Returns:
        Path to the output directory containing the generated PNGs.
    """
    if reference_date is None:
        reference_date = datetime.now()

    if trigger_day is None:
        trigger_day = reference_date.day
        if trigger_day not in (10, 25):
            raise ValueError(
                f"Today is the {trigger_day}th — this script is designed to run "
                "on the 10th or 25th. Pass a date argument to override, e.g.:\n"
                "  python generate_images.py 2026-04-10"
            )

    if output_dir is None:
        output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    dates = get_payroll_dates(trigger_day, reference_date)
    dates["logo_symbol_src"] = _load_logo_symbol_data_uri()

    print(f"\nGenerating images — {reference_date.strftime('%B %d, %Y')} (trigger: {trigger_day}th)")
    print(f"  Payroll date : {dates['payday_full']}")
    print(f"  Period       : {dates['period_label']}\n")

    # 1. Payroll Cut-off & Approval Period table
    html1 = _render_html("cutoff_schedule.html", dates)
    _html_to_png(
        html1,
        output_dir / "Payroll Cut-off & Approval Period.png",
        width=900,
        height=420,
    )

    # 2. Payroll Schedule reminder infographic
    html2 = _render_html("payroll_reminder.html", dates)
    _html_to_png(
        html2,
        output_dir / "Reminder 1.png",
        width=750,
        height=500,
    )

    print(f"\nDone! Images saved to: {output_dir.resolve()}")
    return output_dir


if __name__ == "__main__":
    ref = None
    if len(sys.argv) > 1:
        try:
            ref = datetime.strptime(sys.argv[1], "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date format '{sys.argv[1]}'. Use YYYY-MM-DD, e.g. 2026-04-10")
            sys.exit(1)

    generate_all(reference_date=ref)
