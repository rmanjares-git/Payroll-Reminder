"""
SharePoint Uploader
====================
Uploads generated PNG images to a SharePoint document library
using Office365 user-credential authentication (no Azure AD app required).

Required environment variables (set in .env or GitHub Actions secrets):
  M365_USERNAME        — Office 365 email address
  M365_PASSWORD        — Office 365 password
  SHAREPOINT_SITE_URL  — Full SharePoint site URL, e.g. https://contoso.sharepoint.com/sites/Finance
  SHAREPOINT_FOLDER    — Server-relative folder path inside the library, e.g. Shared Documents/Payroll Reminders
"""

import os
from pathlib import Path

from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Config (from environment)
# ---------------------------------------------------------------------------

USERNAME    = os.environ["M365_USERNAME"]
PASSWORD    = os.environ["M365_PASSWORD"]
SITE_URL    = os.environ["SHAREPOINT_SITE_URL"].rstrip("/")
FOLDER      = os.environ.get("SHAREPOINT_FOLDER", "Shared Documents/Payroll Reminders")


# ---------------------------------------------------------------------------
# Auth + context
# ---------------------------------------------------------------------------

def _get_context() -> ClientContext:
    """Return an authenticated SharePoint ClientContext."""
    credentials = UserCredential(USERNAME, PASSWORD)
    return ClientContext(SITE_URL).with_credentials(credentials)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_file(local_path: Path, ctx: ClientContext) -> str:
    """
    Upload a single file to SharePoint.
    Overwrites if the file already exists (fixed URL in Power Automate stays valid).

    Returns:
        The full web URL of the uploaded file.
    """
    filename = local_path.name

    with open(local_path, "rb") as f:
        content = f.read()

    target_folder = ctx.web.get_folder_by_server_relative_url(FOLDER)
    uploaded = target_folder.upload_file(filename, content).execute_query()

    # Build the web URL from the site URL + server-relative path
    tenant_base = "/".join(SITE_URL.split("/")[:3])   # https://contoso.sharepoint.com
    web_url = tenant_base + uploaded.serverRelativeUrl

    print(f"  Uploaded: {filename}")
    print(f"  URL: {web_url}")
    return web_url


def upload_all(output_dir: Path) -> dict:
    """
    Upload both reminder PNGs from output_dir to SharePoint.

    Returns:
        dict with keys 'reminder1_url' and 'cutoff_url' (matching Power Automate schema)
    """
    ctx = _get_context()

    files = {
        "reminder1_url": output_dir / "Reminder 1.png",
        "cutoff_url":    output_dir / "Payroll Cut-off & Approval Period.png",
    }

    urls = {}
    for key, path in files.items():
        if not path.exists():
            print(f"  Warning: {path.name} not found, skipping.")
            continue
        urls[key] = upload_file(path, ctx)

    return urls


# ---------------------------------------------------------------------------
# CLI usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "output"
    print(f"Uploading from: {output_dir}\n")
    result = upload_all(output_dir)
    print("\nSharePoint URLs:")
    for key, url in result.items():
        print(f"  {key}: {url}")
