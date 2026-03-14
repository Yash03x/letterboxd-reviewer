from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from database.connection import SessionLocal
from database.repository import ProfileRepository, ScrapingJobRepository
from scraper import EnhancedLetterboxdScraper
from services.ingestion import unified_data_loader
from services.profile_loader import load_profile_data

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR.parent / "data"
SCRAPED_DATA_DIR = DATA_DIR / "scraped"


def execute_scrape_job(job_id: int, username: str) -> dict:
    """
    Execute the full profile scrape lifecycle in a worker-safe context.
    """
    db = SessionLocal()
    profile_repo = ProfileRepository(db)
    job_repo = ScrapingJobRepository(db)
    profile = None

    try:
        job_repo.update_job_status(job_id, "in_progress", "Initializing scraper...", 0.0)
        profile = profile_repo.get_profile_by_username(username)
        if not profile:
            raise RuntimeError(f"Profile '{username}' not found for scraping job {job_id}")

        profile_repo.update_profile(profile.id, scraping_status="in_progress")

        with tempfile.TemporaryDirectory() as temp_dir:
            scraper_output_dir = os.path.join(temp_dir, f"{username}_data")
            scraper = EnhancedLetterboxdScraper(username, scraper_output_dir, debug=False)

            # Fail fast for missing/unreachable profiles instead of running every scrape step.
            profile_probe = scraper.fetch_with_retry(scraper.urls["profile"], max_retries=1)
            if not profile_probe:
                raise RuntimeError(f"Letterboxd profile '{username}' could not be fetched.")

            job_repo.update_job_status(job_id, "in_progress", "Scraping profile data...", 10.0)
            scraper.scrape_profile_info()

            job_repo.update_job_status(job_id, "in_progress", "Scraping all films...", 25.0)
            scraper.scrape_all_films()

            job_repo.update_job_status(job_id, "in_progress", "Scraping diary entries...", 40.0)
            scraper.scrape_diary_entries()

            job_repo.update_job_status(job_id, "in_progress", "Scraping reviews...", 55.0)
            scraper.scrape_reviews()

            job_repo.update_job_status(job_id, "in_progress", "Scraping watchlist...", 70.0)
            scraper.scrape_watchlist()

            job_repo.update_job_status(job_id, "in_progress", "Scraping custom lists...", 80.0)
            scraper.scrape_custom_lists()

            job_repo.update_job_status(job_id, "in_progress", "Saving data...", 90.0)
            scraper.save_all_data()

            job_repo.update_job_status(job_id, "in_progress", "Processing data...", 95.0)
            analyzer_profile = load_profile_data(scraper_output_dir, username)

            profile_repo.update_profile(
                profile.id,
                avg_rating=analyzer_profile.avg_rating,
                total_reviews=analyzer_profile.total_reviews,
                join_date=analyzer_profile.join_date,
                last_scraped_at=datetime.utcnow(),
                scraping_status="completed",
            )

            movies_loaded = unified_data_loader(analyzer_profile, profile.id, db)
            print(f"Loaded {movies_loaded} movies for {username} via scraping")

            permanent_dir = SCRAPED_DATA_DIR / username
            permanent_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(scraper_output_dir, permanent_dir, dirs_exist_ok=True)

        job_repo.update_job_status(job_id, "completed", "Scraping completed successfully!", 100.0)
        return {"job_id": job_id, "username": username, "status": "completed"}
    except Exception as exc:
        job_repo.update_job_status(job_id, "failed", f"Error occurred: {exc}", 0.0, str(exc))
        if profile:
            profile_repo.update_profile(profile.id, scraping_status="error")
        raise
    finally:
        db.close()
