import logging
import time

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from starlette.formparsers import MultiPartParser

from app.core.config import settings, ensure_upload_dir
from app.core.logging_config import setup_logging

# Raise the per-part size limit for multipart uploads (default is 1 MB)
MultiPartParser.max_part_size = settings.MAX_UPLOAD_MB * 1024 * 1024
from app.routes.logs import router as logs_router
from app.routes.stats import router as stats_router
from app.routes.analytics import router as analytics_router
from app.routes.auth import router as auth_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Intelligent Log Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "%s %s -> %s (%.2fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router)
app.include_router(logs_router)
app.include_router(stats_router)
app.include_router(analytics_router)

if settings.JWT_SECRET_KEY == "CHANGE-ME-IN-PRODUCTION":
    logger.warning("JWT_SECRET_KEY is set to the default value. Change it in production!")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {
        "message": "Intelligent Log Analyzer API is running",
        "docs": "/docs",
        "health": "/health",
    }
