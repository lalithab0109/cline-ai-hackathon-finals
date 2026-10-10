"""Aarogya Bindu FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .config import APP_NAME, APP_VERSION, allowed_origins
from .routers import health, models, patients, reports, scans, tests
from .services import inference

logger = logging.getLogger("aarogya.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create SQLite tables on startup (idempotent).
    database.init_db()

    # Load the hemoglobin model once, up front, so the first scan is fast and
    # a missing/incompatible artifact is reported immediately. A failure does
    # NOT crash the app (glucose / urine albumin mocks keep working) and does
    # NOT switch hemoglobin to mock: hemoglobin scans return HTTP 503 and
    # /api/models/info reports the model as unavailable.
    try:
        inference.startup_check()
    except inference.MLUnavailableError as exc:
        logger.error("HEMOGLOBIN ML MODEL UNAVAILABLE - scans will return 503: %s", exc)
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Patient-facing API for AI-assisted preliminary diagnostic screening "
        "demonstrations. All results are SIMULATED — NOT FOR MEDICAL USE."
    ),
    lifespan=lifespan,
)

# CORS for local frontend development (Next.js dev server).
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(tests.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(patients.router, prefix="/api")
app.include_router(scans.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
