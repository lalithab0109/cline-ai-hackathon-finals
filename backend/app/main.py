"""Aarogya Bindu FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_NAME, APP_VERSION, allowed_origins
from .routers import future, health, models, tests

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Patient-facing API for AI-assisted preliminary diagnostic screening "
        "demonstrations. All results are SIMULATED — NOT FOR MEDICAL USE."
    ),
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
app.include_router(future.router, prefix="/api")
