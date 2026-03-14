import asyncio
import json
import math
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from auth import ClerkUser, get_current_user
from celery_app import celery_app
from database.connection import get_db, init_db
from database.repository import (
    ProfileRepository, RatingRepository, ReviewRepository,
    ScrapingJobRepository, AnalyticsRepository
)
from pydantic import BaseModel
from services.ingestion import unified_data_loader
from services.profile_loader import load_profile_data
from sqlalchemy.orm import Session
from tasks.scrape import scrape_profile_task

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)

# Support both repo-level .env and legacy backend/.env.
load_dotenv(os.path.join(REPO_ROOT, ".env"))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
SCRAPED_DATA_DIR = os.path.join(DATA_DIR, "scraped")
SSE_PROGRESS_TIMEOUT_SECONDS = int(os.getenv("SSE_PROGRESS_TIMEOUT_SECONDS", "900"))
SSE_PROGRESS_POLL_INTERVAL_SECONDS = float(os.getenv("SSE_PROGRESS_POLL_INTERVAL_SECONDS", "1.5"))
SCRAPE_STALE_JOB_MINUTES = int(os.getenv("SCRAPE_STALE_JOB_MINUTES", "20"))

# Pydantic models for request/response
class ProfileCreate(BaseModel):
    username: str
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None

class ProfileUpdate(BaseModel):
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    is_active: Optional[bool] = None

class ScrapingJobResponse(BaseModel):
    id: int
    status: str
    progress_message: Optional[str]
    progress_percentage: float
    started_at: Optional[datetime]
    error_message: Optional[str]


def _get_cors_origins() -> List[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    defaults = [
        frontend_url,
        "http://localhost:3000",
        "https://spyboxd.com",
        "https://www.spyboxd.com",
    ]

    deduped: List[str] = []
    seen = set()
    for origin in defaults:
        if origin and origin not in seen:
            deduped.append(origin)
            seen.add(origin)
    return deduped


def _job_reference_time(job) -> Optional[datetime]:
    return job.started_at or job.queued_at


def _seconds_since(timestamp: Optional[datetime]) -> Optional[int]:
    if not timestamp:
        return None

    now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.utcnow()
    delta = now - timestamp
    return max(0, int(delta.total_seconds()))


def _is_job_stale(job, stale_minutes: int) -> bool:
    if job.status not in ["queued", "in_progress"]:
        return False
    age_seconds = _seconds_since(_job_reference_time(job))
    if age_seconds is None:
        return False
    return age_seconds >= stale_minutes * 60


def _safe_json_float(value, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def _format_enqueue_error(exc: Exception) -> str:
    raw_message = str(exc).strip()
    if "Retry limit exceeded while trying to reconnect to the Celery redis result store backend" in raw_message:
        return "Celery/Redis connection is stale. Restart API and Celery worker after confirming Redis is running."
    if raw_message:
        return raw_message
    return exc.__class__.__name__


def _enqueue_scrape_task(job_id: int, username: str):
    """
    Enqueue scraping task and try one connection reset when Celery backend got stale.
    This commonly happens after local Redis/Celery restarts during development.
    """
    try:
        return scrape_profile_task.apply_async(args=[job_id, username])
    except Exception as exc:
        if "Retry limit exceeded while trying to reconnect to the Celery redis result store backend" not in str(exc):
            raise
        try:
            celery_app.close()
        except Exception:
            pass
        return scrape_profile_task.apply_async(args=[job_id, username])


def _serialize_scrape_job(job, username: str, stale_minutes: int) -> dict:
    age_seconds = _seconds_since(_job_reference_time(job))
    return {
        "id": job.id,
        "username": username,
        "profile_id": job.profile_id,
        "status": job.status,
        "progress_message": job.progress_message,
        "progress_percentage": job.progress_percentage,
        "queued_at": job.queued_at.isoformat() if job.queued_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "job_type": job.job_type,
        "age_seconds": age_seconds,
        "is_stale": _is_job_stale(job, stale_minutes),
    }


app = FastAPI(
    title="Spyboxd API",
    description="Analytics and insights for Letterboxd profiles",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("🎬 Spyboxd API started successfully!")

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/public/profile/{username}")
async def get_public_profile(username: str, db: Session = Depends(get_db)):
    """
    Public profile snapshot used by share pages/OG images.
    Only exposes completed, active profiles.
    """
    profile_repo = ProfileRepository(db)
    rating_repo = RatingRepository(db)

    profile = profile_repo.get_profile_by_username(username)
    if not profile or not profile.is_active:
        raise HTTPException(status_code=404, detail="Profile not found")

    if profile.scraping_status != "completed":
        raise HTTPException(status_code=404, detail="Profile has no public data yet")

    all_entries = rating_repo.get_ratings_by_profile(profile.id)
    total_films = len(all_entries)
    rated_films = len([entry for entry in all_entries if entry.rating is not None and entry.rating > 0])
    liked_films = len([entry for entry in all_entries if entry.is_liked])
    avg_rating = _safe_json_float(profile.avg_rating, 0.0)

    return {
        "username": profile.username,
        "total_films": total_films,
        "rated_films": rated_films,
        "liked_films": liked_films,
        "avg_rating": avg_rating,
        "total_reviews": profile.total_reviews or 0,
        "profile_image_url": profile.profile_image_url,
        "bio": profile.bio,
        "location": profile.location,
        "website": profile.website,
        "last_scraped_at": profile.last_scraped_at.isoformat() if profile.last_scraped_at else None,
    }

def extract_zip_file(uploaded_file, temp_dir):
    """Extract uploaded zip file to temporary directory"""
    zip_path = os.path.join(temp_dir, uploaded_file.filename)
    with open(zip_path, "wb") as f:
        f.write(uploaded_file.file.read())

    extract_dir = os.path.join(temp_dir, uploaded_file.filename.replace('.zip', ''))
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Find the actual data directory (might be nested)
    for root, dirs, files in os.walk(extract_dir):
        if any(f in files for f in ['ratings.csv', 'watched.csv', 'reviews.csv']):
            return root

    return extract_dir

# Profile Management Endpoints
@app.get("/profiles/")
async def list_profiles(
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get all active profiles with their basic information"""
    profile_repo = ProfileRepository(db)
    
    profiles = profile_repo.get_all_profiles(active_only=True)
    
    profile_list = []
    for profile in profiles:
        profile_dict = profile.to_dict()
        # Add real-time stats with proper distinction
        rating_repo = RatingRepository(db)
        all_entries = rating_repo.get_ratings_by_profile(profile.id)
        
        # Calculate separate counts
        total_films = len(all_entries)  # All films in database (watched/rated/liked)
        rated_films = len([r for r in all_entries if r.rating is not None and r.rating > 0])  # Only films with actual ratings
        liked_films = len([r for r in all_entries if r.is_liked])  # Films that are liked
        
        profile_dict['total_films'] = total_films  # All films discovered
        profile_dict['rated_films'] = rated_films  # Only films with ratings
        profile_dict['liked_films'] = liked_films  # Only films that are liked
        # Remove total_movies to avoid confusion - use total_films instead
        
        if rated_films > 0:
            profile_dict['avg_rating'] = sum(r.rating for r in all_entries if r.rating and r.rating > 0) / rated_films
        else:
            profile_dict['avg_rating'] = 0
            
        profile_list.append(profile_dict)
    
    return {"profiles": profile_list}

@app.get("/api/dashboard/analytics")
async def get_consolidated_dashboard_analytics(
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get consolidated system-wide analytics for the main dashboard."""
    analytics_repo = AnalyticsRepository(db)
    rating_repo = RatingRepository(db)

    # Get system stats from the dedicated repository method
    system_stats = analytics_repo.get_system_stats()
    
    # Get top-rated movies
    top_movies = analytics_repo.get_top_rated_movies(limit=10)
    
    # Get global rating distribution
    rating_distribution = rating_repo.get_global_rating_distribution()

    # Get monthly activity data
    activity_data = rating_repo.get_global_monthly_activity()

    return {
        "system_stats": system_stats,
        "top_rated_movies": top_movies,
        "rating_distribution": rating_distribution,
        "activity_data": activity_data,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/profiles/{username}/analysis")
async def get_analysis(
    username: str,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get detailed analysis for a specific profile"""
    profile_repo = ProfileRepository(db)
    rating_repo = RatingRepository(db)
    review_repo = ReviewRepository(db)
    
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Get rating distribution
    rating_distribution = rating_repo.get_rating_distribution(profile.id)
    
    # Get monthly stats
    monthly_stats = rating_repo.get_monthly_watch_stats(profile.id, months=12)
    
    # Get recent ratings and reviews
    recent_ratings = rating_repo.get_ratings_by_profile(profile.id, limit=20)
    recent_reviews = review_repo.get_reviews_by_profile(profile.id, limit=10)
    
    # Get recent watching trend (movies with watched dates)
    recent_watching = rating_repo.get_ratings_by_profile(profile.id)
    recent_watching_with_dates = [r for r in recent_watching if r.watched_date]
    recent_watching_sorted = sorted(recent_watching_with_dates, key=lambda x: x.watched_date, reverse=True)[:10]
    
    # Calculate detailed film counts
    all_entries = rating_repo.get_ratings_by_profile(profile.id)
    total_films = len(all_entries)
    rated_films = len([r for r in all_entries if r.rating is not None and r.rating > 0])
    liked_films = len([r for r in all_entries if r.is_liked])
    
    analysis = {
        "username": profile.username,
        "total_films": total_films,
        "rated_films": rated_films,
        "liked_films": liked_films,
        "avg_rating": _safe_json_float(profile.avg_rating, 0.0),
        "total_reviews": profile.total_reviews,
        "join_date": profile.join_date.isoformat() if profile.join_date else None,
        "last_scraped_at": profile.last_scraped_at.isoformat() if profile.last_scraped_at else None,
        "scraping_status": profile.scraping_status,
        "enhanced_metrics": profile.enhanced_metrics or {},
        "rating_distribution": rating_distribution,
        "monthly_stats": monthly_stats,
        "recent_ratings": [
            {
                "movie_title": r.movie_title,
                "movie_year": r.movie_year,
                "rating": _safe_json_float(r.rating),
                "watched_date": r.watched_date.isoformat() if r.watched_date else None,
                "is_rewatch": r.is_rewatch
            } for r in recent_ratings
        ],
        "recent_reviews": [
            {
                "movie_title": r.movie_title,
                "movie_year": r.movie_year,
                "rating": _safe_json_float(r.rating),
                "review_text": r.review_text[:200] + "..." if r.review_text and len(r.review_text) > 200 else r.review_text,
                "published_date": r.published_date.isoformat() if r.published_date else None,
                "likes_count": r.likes_count
            } for r in recent_reviews
        ],
        "recent_watching_trend": [
            {
                "movie_title": r.movie_title,
                "movie_year": r.movie_year,
                "watched_date": r.watched_date.isoformat() if r.watched_date else None,
                "rating": _safe_json_float(r.rating),
                "is_rewatch": r.is_rewatch
            } for r in recent_watching_sorted
        ]
    }

    return analysis

@app.post("/profiles/create")
async def create_profile(
    profile_data: ProfileCreate,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Create a new profile"""
    profile_repo = ProfileRepository(db)
    
    # Check if profile already exists
    existing_profile = profile_repo.get_profile_by_username(profile_data.username)
    if existing_profile:
        raise HTTPException(status_code=409, detail="Profile already exists")
    
    profile = profile_repo.create_profile(
        username=profile_data.username,
        bio=profile_data.bio,
        location=profile_data.location,
        website=profile_data.website
    )
    
    return {"message": f"Profile created for {profile_data.username}", "profile": profile.to_dict()}

@app.put("/profiles/{username}")
async def update_profile(
    username: str,
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Update an existing profile"""
    profile_repo = ProfileRepository(db)
    
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Update profile with provided data
    update_data = profile_data.dict(exclude_unset=True)
    updated_profile = profile_repo.update_profile(profile.id, **update_data)
    
    return {"message": f"Profile updated for {username}", "profile": updated_profile.to_dict()}

@app.delete("/profiles/{username}")
async def delete_profile(
    username: str,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Delete a profile and all associated data"""
    profile_repo = ProfileRepository(db)
    
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Clean up data directory
    data_path = os.path.normpath(os.path.join(SCRAPED_DATA_DIR, username))
    # Ensure the final path is within SCRAPED_DATA_DIR
    if not data_path.startswith(os.path.abspath(SCRAPED_DATA_DIR) + os.sep):
        raise HTTPException(status_code=400, detail="Invalid username/path")
    if os.path.exists(data_path):
        shutil.rmtree(data_path)
    
    # Delete from database (cascades to ratings, reviews, etc.)
    profile_repo.delete_profile(profile.id)
    
    return {"message": f"Profile {username} deleted successfully"}

# File Upload Endpoints
@app.post("/upload/")
async def upload_files(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Upload multiple ZIP files containing Letterboxd data"""
    profile_repo = ProfileRepository(db)
    
    loaded_profiles = []
    errors = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            if not file.filename.endswith('.zip'):
                errors.append(f"Invalid file type for {file.filename}. Please upload ZIP files only.")
                continue
                
            try:
                # Extract username from filename (remove .zip extension)
                username = file.filename.replace('.zip', '').replace('letterboxd-', '')
                
                profile_path = extract_zip_file(file, temp_dir)
                
                # Load profile data from extracted CSVs
                analyzer_profile = load_profile_data(profile_path, username)
                
                # Create or update profile in database
                existing_profile = profile_repo.get_profile_by_username(username)
                if existing_profile:
                    profile = profile_repo.update_profile(
                        existing_profile.id,
                        avg_rating=analyzer_profile.avg_rating,
                        total_reviews=analyzer_profile.total_reviews,
                        join_date=analyzer_profile.join_date,
                        last_scraped_at=datetime.utcnow(),
                        scraping_status="completed"
                    )
                else:
                    profile = profile_repo.create_profile(
                        username=username,
                        avg_rating=analyzer_profile.avg_rating,
                        total_reviews=analyzer_profile.total_reviews,
                        join_date=analyzer_profile.join_date,
                        last_scraped_at=datetime.utcnow(),
                        scraping_status="completed"
                    )
                
                # Use unified data loader to prevent duplicates
                movies_loaded = unified_data_loader(analyzer_profile, profile.id, db)
                print(f"Loaded {movies_loaded} movies for {username} via upload")
                
                loaded_profiles.append(username)
                
            except Exception as e:
                errors.append(f"Failed to process {file.filename}: {str(e)}")
    
    result = {"loaded_profiles": loaded_profiles}
    if errors:
        result["errors"] = errors
    
    if not loaded_profiles:
        raise HTTPException(status_code=400, detail="No profiles could be loaded")
    
    return result

# Enhanced Scraper Endpoints
@app.post("/scrape/profile/{username}")
async def scrape_profile(
    username: str,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Start scraping a Letterboxd profile."""
    profile_repo = ProfileRepository(db)
    job_repo = ScrapingJobRepository(db)
    
    # Create or get profile
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        profile = profile_repo.create_profile(username=username, scraping_status="queued")
    
    # Check for existing active job
    existing_job = job_repo.get_job_by_profile(profile.id)
    if existing_job and existing_job.status in ["queued", "in_progress"]:
        raise HTTPException(status_code=409, detail="Scraping already in progress for this user.")
    
    # Create new scraping job
    job = job_repo.create_job(profile.id, job_type="full_scrape", status="queued")
    
    # Update profile status
    profile_repo.update_profile(profile.id, scraping_status="queued")
    
    try:
        queued_task = _enqueue_scrape_task(job.id, username)
    except Exception as exc:
        enqueue_error = _format_enqueue_error(exc)
        job_repo.update_job_status(job.id, "failed", "Failed to enqueue scraping task", 0.0, enqueue_error)
        profile_repo.update_profile(profile.id, scraping_status="error")
        raise HTTPException(status_code=503, detail=f"Failed to enqueue scraping task: {enqueue_error}") from exc

    return {
        "message": f"Started scraping profile for {username}",
        "job_id": job.id,
        "task_id": queued_task.id,
        "status": "queued",
        "check_status_url": f"/scrape/status/{username}"
    }

@app.get("/scrape/status/{username}")
async def get_scraping_status(
    username: str,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get the current scraping status for a user."""
    profile_repo = ProfileRepository(db)
    job_repo = ScrapingJobRepository(db)
    
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    job = job_repo.get_job_by_profile(profile.id)
    if not job:
        return {
            "status": profile.scraping_status,
            "progress_message": "No active scraping job",
            "progress_percentage": 0.0
        }
    
    return {
        "id": job.id,
        "status": job.status,
        "progress_message": job.progress_message,
        "progress_percentage": job.progress_percentage,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "error_message": job.error_message
    }


@app.get("/scrape/jobs")
async def list_scrape_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    stale_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """List recent scraping jobs with queue/stale metadata."""
    job_repo = ScrapingJobRepository(db)
    rows = job_repo.get_recent_jobs_with_profile(limit=limit)

    jobs = []
    for job, username in rows:
        serialized = _serialize_scrape_job(job, username=username, stale_minutes=SCRAPE_STALE_JOB_MINUTES)
        if stale_only and not serialized["is_stale"]:
            continue
        jobs.append(serialized)

    counts = {
        "total": len(jobs),
        "queued": len([job for job in jobs if job["status"] == "queued"]),
        "in_progress": len([job for job in jobs if job["status"] == "in_progress"]),
        "completed": len([job for job in jobs if job["status"] == "completed"]),
        "failed": len([job for job in jobs if job["status"] == "failed"]),
        "stale": len([job for job in jobs if job["is_stale"]]),
    }

    return {
        "jobs": jobs,
        "counts": counts,
        "stale_threshold_minutes": SCRAPE_STALE_JOB_MINUTES,
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.post("/scrape/jobs/{job_id}/retry")
async def retry_scrape_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Create a fresh scrape job for the same profile and enqueue it."""
    job_repo = ScrapingJobRepository(db)
    profile_repo = ProfileRepository(db)

    original_job = job_repo.get_job_by_id(job_id)
    if not original_job:
        raise HTTPException(status_code=404, detail="Scraping job not found")

    profile = profile_repo.get_profile_by_id(original_job.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile for scraping job not found")

    active_jobs = job_repo.get_active_jobs_for_profile(profile.id, exclude_job_id=original_job.id)
    if active_jobs:
        raise HTTPException(status_code=409, detail="An active scraping job already exists for this profile")

    new_retry_count = (original_job.retry_count or 0) + 1
    new_job = job_repo.create_job(
        profile.id,
        job_type=original_job.job_type or "full_scrape",
        status="queued",
        retry_count=new_retry_count,
    )
    profile_repo.update_profile(profile.id, scraping_status="queued")

    try:
        queued_task = _enqueue_scrape_task(new_job.id, profile.username)
    except Exception as exc:
        enqueue_error = _format_enqueue_error(exc)
        job_repo.update_job_status(
            new_job.id,
            "failed",
            "Failed to enqueue retry task",
            0.0,
            enqueue_error,
        )
        profile_repo.update_profile(profile.id, scraping_status="error")
        raise HTTPException(status_code=503, detail=f"Failed to enqueue retry task: {enqueue_error}") from exc

    return {
        "message": f"Retry queued for {profile.username}",
        "job": _serialize_scrape_job(new_job, username=profile.username, stale_minutes=SCRAPE_STALE_JOB_MINUTES),
        "task_id": queued_task.id,
    }


@app.post("/scrape/jobs/{job_id}/cancel")
async def cancel_scrape_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Mark an active scraping job as failed to unblock the queue from UI."""
    job_repo = ScrapingJobRepository(db)
    profile_repo = ProfileRepository(db)

    job = job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scraping job not found")

    if job.status not in ["queued", "in_progress"]:
        raise HTTPException(status_code=409, detail="Only queued/in-progress jobs can be cancelled")

    job_repo.update_job_status(
        job.id,
        "failed",
        "Cancelled from UI",
        job.progress_percentage if job.progress_percentage is not None else 0.0,
        "Cancelled manually from scraper dashboard",
    )

    profile = profile_repo.get_profile_by_id(job.profile_id)
    if profile:
        remaining_active_jobs = job_repo.get_active_jobs_for_profile(profile.id, exclude_job_id=job.id)
        if not remaining_active_jobs:
            profile_repo.update_profile(profile.id, scraping_status="pending")

    updated = job_repo.get_job_by_id(job.id)
    username = profile.username if profile else "unknown"
    return {
        "message": f"Cancelled scraping job {job.id}",
        "job": _serialize_scrape_job(updated, username=username, stale_minutes=SCRAPE_STALE_JOB_MINUTES) if updated else None,
    }


@app.post("/scrape/jobs/reset-stale")
async def reset_stale_scrape_jobs(
    stale_minutes: int = Query(default=SCRAPE_STALE_JOB_MINUTES, ge=1, le=720),
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Mark stale queued/in-progress jobs as failed to recover from worker crashes."""
    job_repo = ScrapingJobRepository(db)
    profile_repo = ProfileRepository(db)

    active_jobs = job_repo.get_active_jobs()
    reset_jobs = []

    for job in active_jobs:
        if not _is_job_stale(job, stale_minutes):
            continue

        profile = profile_repo.get_profile_by_id(job.profile_id)
        username = profile.username if profile else f"profile:{job.profile_id}"

        job_repo.update_job_status(
            job.id,
            "failed",
            "Marked stale and reset from UI",
            job.progress_percentage if job.progress_percentage is not None else 0.0,
            f"Job exceeded stale threshold ({stale_minutes}m)",
        )

        if profile:
            remaining_active_jobs = job_repo.get_active_jobs_for_profile(profile.id, exclude_job_id=job.id)
            if not remaining_active_jobs:
                profile_repo.update_profile(profile.id, scraping_status="pending")

        refreshed = job_repo.get_job_by_id(job.id)
        if refreshed:
            reset_jobs.append(_serialize_scrape_job(refreshed, username=username, stale_minutes=stale_minutes))

    return {
        "message": f"Reset {len(reset_jobs)} stale jobs",
        "reset_count": len(reset_jobs),
        "stale_threshold_minutes": stale_minutes,
        "jobs": reset_jobs,
    }


@app.get("/scrape/progress/{job_id}/stream")
async def stream_scrape_progress(job_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Stream scraping progress updates for a specific job via Server-Sent Events.
    """
    job_repo = ScrapingJobRepository(db)
    initial_job = job_repo.get_job_by_id(job_id)
    if not initial_job:
        raise HTTPException(status_code=404, detail="Scraping job not found")

    async def event_generator():
        deadline = datetime.utcnow() + timedelta(seconds=SSE_PROGRESS_TIMEOUT_SECONDS)
        last_payload = None

        while True:
            if await request.is_disconnected():
                break

            db.expire_all()
            job = job_repo.get_job_by_id(job_id)
            if not job:
                payload = {
                    "id": job_id,
                    "status": "failed",
                    "progress_message": "Scraping job not found",
                    "progress_percentage": 0.0,
                    "error_message": "Job no longer exists",
                    "done": True,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                break

            payload = {
                "id": job.id,
                "status": job.status,
                "progress_message": job.progress_message,
                "progress_percentage": job.progress_percentage,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "error_message": job.error_message,
                "done": job.status in ["completed", "failed"],
            }

            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n"
                last_payload = payload

            if payload["done"]:
                break

            if datetime.utcnow() >= deadline:
                timeout_payload = {
                    **payload,
                    "progress_message": payload.get("progress_message") or "Progress stream timeout",
                    "timeout": True,
                    "done": True,
                }
                yield f"data: {json.dumps(timeout_payload)}\n\n"
                break

            await asyncio.sleep(SSE_PROGRESS_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/scrape/available")
async def get_available_profiles(
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get all available scraped profiles."""
    profile_repo = ProfileRepository(db)
    profiles = profile_repo.get_all_profiles(active_only=True)
    
    available_profiles = []
    for profile in profiles:
        if profile.last_scraped_at and profile.scraping_status == "completed":
            available_profiles.append({
                "username": profile.username,
                "scraped_at": profile.last_scraped_at.isoformat()
            })
    
    return {"available_profiles": available_profiles}

@app.delete("/scrape/{username}")
async def clear_scraped_data(
    username: str,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Clear scraped data for a user - alias for /profiles/{username}/data"""
    return await clear_profile_data(username, db, _user)

# Analytics and Dashboard Endpoints

@app.get("/profiles/suggestions/update")
async def get_update_suggestions(
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get profiles that need updating"""
    profile_repo = ProfileRepository(db)
    profiles_needing_update = profile_repo.get_profiles_requiring_update(hours=24)
    
    return {
        "profiles_needing_update": [
            {
                "username": p.username,
                "last_scraped_at": p.last_scraped_at.isoformat() if p.last_scraped_at else None,
                "hours_since_update": int((datetime.utcnow() - p.last_scraped_at).total_seconds() / 3600) if p.last_scraped_at else None
            }
            for p in profiles_needing_update
        ]
    }

@app.delete("/profiles/{username}/data")
async def clear_profile_data(
    username: str,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Clear scraped data for a user."""
    profile_repo = ProfileRepository(db)
    
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Reset profile scraping status
    profile_repo.update_profile(
        profile.id,
        scraping_status="pending",
        last_scraped_at=None,
        avg_rating=0.0,
        total_reviews=0
    )
    
    # Clean up data directory
    data_path = os.path.join(SCRAPED_DATA_DIR, username)
    if os.path.exists(data_path):
        shutil.rmtree(data_path)
    
    return {"message": f"Cleared all scraped data for {username}"}

# Analysis Endpoints (required by frontend)
@app.get("/analysis/comparative")
async def get_comparative_analysis(
    usernames: List[str] = Query(default=[]),
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get comparative analysis between multiple profiles"""
    if not usernames:
        raise HTTPException(status_code=400, detail="usernames parameter is required")
    
    # Support both ?usernames=a,b and ?usernames=a&usernames=b forms.
    username_list: List[str] = []
    for raw_value in usernames:
        username_list.extend([value.strip() for value in raw_value.split(",") if value.strip()])
    username_list = list(dict.fromkeys(username_list))
    
    if len(username_list) < 2:
        raise HTTPException(status_code=400, detail="At least 2 usernames required for comparison")
        
    profile_repo = ProfileRepository(db)
    rating_repo = RatingRepository(db)
    
    profiles_data = []
    for username in username_list:
        profile = profile_repo.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{username}' not found")
        
        ratings = rating_repo.get_ratings_by_profile(profile.id)
        rating_distribution = rating_repo.get_rating_distribution(profile.id)
        
        profiles_data.append({
            "profile": profile.to_dict(),
            "ratings_count": len(ratings),
            "rating_distribution": rating_distribution,
            "recent_ratings": [
                {
                    "movie_title": r.movie_title,
                    "movie_year": r.movie_year,
                    "rating": _safe_json_float(r.rating),
                    "watched_date": r.watched_date.isoformat() if r.watched_date else None
                } for r in ratings[:10]
            ]
        })
    
    # Simple comparison metrics
    comparison_result = {
        "profiles": profiles_data,
        "comparison_metrics": {
            "total_profiles": len(profiles_data),
            "avg_movies_per_profile": sum(p["ratings_count"] for p in profiles_data) / len(profiles_data),
            "rating_spread": {
                username_list[i]: profiles_data[i]["profile"]["avg_rating"] 
                for i in range(len(username_list))
            }
        }
    }
    
    return comparison_result

@app.get("/analysis/recommendations/{username}")
async def get_recommendations(
    username: str,
    db: Session = Depends(get_db),
    _user: ClerkUser = Depends(get_current_user),
):
    """Get movie recommendations for a specific profile"""
    profile_repo = ProfileRepository(db)
    rating_repo = RatingRepository(db)
    analytics_repo = AnalyticsRepository(db)
    
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get user's ratings for analysis
    user_ratings = rating_repo.get_ratings_by_profile(profile.id)
    
    # Get highly rated movies from other users as recommendations
    top_movies = analytics_repo.get_top_rated_movies(limit=20)
    
    # Simple recommendation logic: suggest top-rated movies the user hasn't seen
    user_watched_titles = {r.movie_title for r in user_ratings}
    recommendations = [
        movie for movie in top_movies 
        if movie['title'] not in user_watched_titles
    ][:10]
    
    return {
        "username": username,
        "user_stats": {
            "total_movies": len(user_ratings),
            "avg_rating": _safe_json_float(profile.avg_rating, 0.0),
            "favorite_genres": []  # Could be enhanced with genre analysis
        },
        "recommendations": recommendations,
        "recommendation_type": "popular_unwatched",
        "total_recommendations": len(recommendations)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
