# Entry point for the AI Website Builder FastAPI application.
# Registers routes, CORS middleware, loads environment variables,
# and starts the APScheduler cron job for Serey knowledge sync.

# load_dotenv MUST run before any service imports that read env vars
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routes.builder import router as builder_router
from routes.chat import router as chat_router
from routes.builder_chat import router as builder_chat_router
from services.knowledge_sync import sync_knowledge
import logging
import os
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheduler — runs sync_knowledge() once a day at 02:00 server time
# Change hour/minute here or set SYNC_CRON_HOUR / SYNC_CRON_MINUTE in .env
# ---------------------------------------------------------------------------
_scheduler = AsyncIOScheduler()

_SYNC_HOUR = int(os.getenv("SYNC_CRON_HOUR", "2"))
_SYNC_MINUTE = int(os.getenv("SYNC_CRON_MINUTE", "0"))


async def _scheduled_sync():
    logger.info("Cron: starting Serey knowledge sync...")
    try:
        summary = await sync_knowledge()
        logger.info("Cron: sync complete — %s", summary)
    except Exception as e:
        logger.error("Cron: sync failed — %s\n%s", str(e), traceback.format_exc())


@asynccontextmanager
async def lifespan(application: FastAPI):
    # --- startup ---
    logger.info("Running initial Serey knowledge sync on startup...")
    try:
        summary = await sync_knowledge()
        logger.info("Startup sync complete — %s", summary)
    except Exception as e:
        logger.warning("Startup sync failed (non-fatal) — %s", str(e))

    _scheduler.add_job(
        _scheduled_sync,
        trigger="cron",
        hour=_SYNC_HOUR,
        minute=_SYNC_MINUTE,
        id="serey_knowledge_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Knowledge cron scheduled — runs daily at %02d:%02d server time.",
        _SYNC_HOUR, _SYNC_MINUTE,
    )

    yield  # server is running

    # --- shutdown ---
    _scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(title="AI Website Builder API", lifespan=lifespan)

_ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Serey-Api-Key"],
)

app.include_router(builder_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(builder_chat_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ready")
def readiness_check():
    """Checks that ChromaDB is indexed and Gemini is reachable before serving requests."""
    from services.gemini import test_connection
    from services.search import get_all_component_names

    try:
        names = get_all_component_names()
        if not names:
            return JSONResponse(status_code=503, content={"ready": False, "reason": "ChromaDB collection is empty. Run: python scripts/index_components.py"})
    except Exception as e:
        return JSONResponse(status_code=503, content={"ready": False, "reason": f"ChromaDB error: {str(e)}"})

    if not test_connection():
        return JSONResponse(status_code=503, content={"ready": False, "reason": "Gemini connection failed. Check GOOGLE_API_KEY."})

    return {"ready": True}


_ADMIN_KEY = os.getenv("ADMIN_API_KEY", "")


@app.post("/api/admin/sync-knowledge")
async def manual_sync(request: Request):
    """Manually trigger a Serey knowledge sync outside of the cron schedule."""
    if _ADMIN_KEY:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {_ADMIN_KEY}":
            return JSONResponse(status_code=403, content={"error": "Forbidden"})
    logger.info("Manual knowledge sync triggered via API.")
    try:
        summary = await sync_knowledge()
        return {"status": "ok", "summary": summary}
    except Exception as e:
        logger.error("Manual sync failed: %s", str(e))
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s\n%s", str(exc), traceback.format_exc())
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
