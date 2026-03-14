from __future__ import annotations

import os
import platform
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

load_dotenv(REPO_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=False)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
IS_DARWIN = platform.system() == "Darwin"

DEFAULT_WORKER_POOL = "solo" if IS_DARWIN else "prefork"
DEFAULT_WORKER_CONCURRENCY = "1" if DEFAULT_WORKER_POOL == "solo" else "2"

WORKER_POOL = os.getenv("CELERY_WORKER_POOL", DEFAULT_WORKER_POOL)
try:
    WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", DEFAULT_WORKER_CONCURRENCY))
except ValueError:
    WORKER_CONCURRENCY = int(DEFAULT_WORKER_CONCURRENCY)

celery_app = Celery(
    "spyboxd",
    broker=REDIS_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["tasks.scrape"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_pool=WORKER_POOL,
    worker_concurrency=WORKER_CONCURRENCY,
)

# Alias commonly used by celery CLI
app = celery_app
