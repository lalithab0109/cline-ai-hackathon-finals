"""Application configuration.

Values are read from environment variables (optionally via a local `.env`
file loaded by the developer's tooling). No secrets are hardcoded; defaults
are safe for local development only.
"""

from __future__ import annotations

import os

APP_NAME = "Aarogya Bindu API"
APP_VERSION = "0.1.0"

# Visible prototype disclaimer reused across responses and (later) the UI/PDF.
SIMULATION_DISCLAIMER = "SIMULATED — NOT FOR MEDICAL USE"


def allowed_origins() -> list[str]:
    """Return the CORS origins allowed to call this API.

    Configure with the ALLOWED_ORIGINS environment variable as a
    comma-separated list, e.g. "http://localhost:3000,https://example.com".
    Defaults to the local Next.js development server.
    """

    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
