from __future__ import annotations

from celery_app import celery_app
from services.scrape_runner import execute_scrape_job


@celery_app.task(name="tasks.scrape_profile_task")
def scrape_profile_task(job_id: int, username: str) -> dict:
    return execute_scrape_job(job_id=job_id, username=username)


@celery_app.task(name="tasks.ping")
def ping() -> str:
    return "pong"
