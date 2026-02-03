import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI(title="LocalForge Coach API")
app.include_router(api_router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.method == "GET" and request.url.path.startswith("/api/run/"):
        return await call_next(request)
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed method=%s path=%s",
            request.method,
            request.url.path,
        )
        raise
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
