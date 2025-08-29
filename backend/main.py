from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from core.analyzer import UnifiedLetterboxdAnalyzer
from scraper import EnhancedLetterboxdScraper
from database.connection import get_db, init_db
from database.models import Profile, Rating, Review, ScrapingJob
from database.repository import (
    ProfileRepository, RatingRepository, ReviewRepository, 
    ScrapingJobRepository, AnalyticsRepository
)
import tempfile
import zipfile
import os
import shutil
import asyncio
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from pydantic import BaseModel

# Get base directory for absolute paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
SCRAPED_DATA_DIR = os.path.join(DATA_DIR, "scraped")

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

app = FastAPI(
    title="Letterboxd Reviewer API v2.0",
    description="Advanced Letterboxd profile analysis with persistent database storage",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("🎬 Letterboxd Reviewer API v2.0 started successfully!")

# Keep analyzer for processing
analyzer = UnifiedLetterboxdAnalyzer()

def parse_date_for_db(date_value):
    """Parse date string/object to Python date object for database storage"""
    if not date_value:
        return None
    try:
        # Convert to pandas datetime then to Python date
        parsed_date = pd.to_datetime(date_value, errors='coerce')
        if not pd.isna(parsed_date):
            return parsed_date.date()
    except Exception:
        pass
    return None

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
async def list_profiles(db: Session = Depends(get_db)):
    """Get all active profiles with their basic information"""
    profile_repo = ProfileRepository(db)
    analytics_repo = AnalyticsRepository(db)
    
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
async def get_consolidated_dashboard_analytics(db: Session = Depends(get_db)):
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
async def get_analysis(username: str, db: Session = Depends(get_db)):
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
        "avg_rating": profile.avg_rating,
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
                "rating": r.rating,
                "watched_date": r.watched_date.isoformat() if r.watched_date else None,
                "is_rewatch": r.is_rewatch
            } for r in recent_ratings
        ],
        "recent_reviews": [
            {
                "movie_title": r.movie_title,
                "movie_year": r.movie_year,
                "rating": r.rating,
                "review_text": r.review_text[:200] + "..." if r.review_text and len(r.review_text) > 200 else r.review_text,
                "published_date": r.published_date.isoformat() if r.published_date else None,
                "likes_count": r.likes_count
            } for r in recent_reviews
        ]
    }

    return analysis

@app.post("/profiles/create")
async def create_profile(profile_data: ProfileCreate, db: Session = Depends(get_db)):
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
async def update_profile(username: str, profile_data: ProfileUpdate, db: Session = Depends(get_db)):
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
async def delete_profile(username: str, db: Session = Depends(get_db)):
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
async def upload_files(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """Upload multiple ZIP files containing Letterboxd data"""
    profile_repo = ProfileRepository(db)
    rating_repo = RatingRepository(db)
    review_repo = ReviewRepository(db)
    
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
                
                # Load profile using analyzer
                analyzer_profile = analyzer.load_profile(profile_path, username)
                
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
                
                # Store ratings data
                if not analyzer_profile.ratings.empty:
                    ratings_data = []
                    for _, row in analyzer_profile.ratings.iterrows():
                        ratings_data.append({
                            'profile_id': profile.id,
                            'movie_title': row.get('Name', ''),
                            'movie_year': row.get('Year', None),
                            'rating': row.get('Rating', None),
                            'watched_date': parse_date_for_db(row.get('Watched Date', None)),
                            'is_rewatch': row.get('Rewatch', False)
                        })
                    rating_repo.bulk_create_ratings(ratings_data)
                
                # Store reviews data
                if not analyzer_profile.reviews.empty:
                    reviews_data = []
                    for _, row in analyzer_profile.reviews.iterrows():
                        reviews_data.append({
                            'profile_id': profile.id,
                            'movie_title': row.get('Name', ''),
                            'movie_year': row.get('Year', None),
                            'rating': row.get('Rating', None),
                            'review_text': row.get('Review', ''),
                            'published_date': parse_date_for_db(row.get('Watched Date', None)),
                        })
                    review_repo.bulk_create_reviews(reviews_data)
                
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
async def scrape_profile(username: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start scraping a Letterboxd profile."""
    profile_repo = ProfileRepository(db)
    job_repo = ScrapingJobRepository(db)
    
    # Create or get profile
    profile = profile_repo.get_profile_by_username(username)
    if not profile:
        profile = profile_repo.create_profile(username=username, scraping_status="queued")
    
    # Check for existing active job
    existing_job = job_repo.get_job_by_profile(profile.id)
    if existing_job and existing_job.status == "in_progress":
        raise HTTPException(status_code=409, detail="Scraping already in progress for this user.")
    
    # Create new scraping job
    job = job_repo.create_job(profile.id, job_type="full_scrape", status="queued")
    
    # Update profile status
    profile_repo.update_profile(profile.id, scraping_status="queued")
    
    # Start background scraping task
    background_tasks.add_task(run_scraping_task, job.id, username, db)
    
    return {
        "message": f"Started scraping profile for {username}",
        "job_id": job.id,
        "status": "queued",
        "check_status_url": f"/scrape/status/{username}"
    }

async def run_scraping_task(job_id: int, username: str, db: Session):
    """Background task to run the scraping process."""
    profile_repo = ProfileRepository(db)
    job_repo = ScrapingJobRepository(db)
    rating_repo = RatingRepository(db)
    review_repo = ReviewRepository(db)
    
    try:
        # Update job status
        job_repo.update_job_status(job_id, "in_progress", "Initializing scraper...", 0.0)
        
        profile = profile_repo.get_profile_by_username(username)
        profile_repo.update_profile(profile.id, scraping_status="in_progress")
        
        # Create temporary directory for this scraping session
        with tempfile.TemporaryDirectory() as temp_dir:
            scraper_output_dir = os.path.join(temp_dir, f"{username}_data")
            
            # Initialize scraper
            scraper = EnhancedLetterboxdScraper(username, scraper_output_dir, debug=False)
            
            # Run comprehensive scraping with progress updates
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
            
            # Load the scraped data into our analyzer
            job_repo.update_job_status(job_id, "in_progress", "Processing data...", 95.0)
            analyzer_profile = analyzer.load_profile(scraper_output_dir, username)
            
            # Update profile with new data
            profile_repo.update_profile(
                profile.id,
                avg_rating=analyzer_profile.avg_rating,
                total_reviews=analyzer_profile.total_reviews,
                join_date=analyzer_profile.join_date,
                last_scraped_at=datetime.utcnow(),
                scraping_status="completed"
            )
            
            # Store ratings and reviews data (clear old data first)
            rating_repo = RatingRepository(db)
            review_repo = ReviewRepository(db)
            
            # Clear existing data for this profile
            rating_repo.delete_ratings_by_profile(profile.id)
            review_repo.delete_reviews_by_profile(profile.id)
            
            # Store ratings data - prioritize all_films if available, fallback to ratings
            primary_dataset = None
            if hasattr(analyzer_profile, 'all_films') and not analyzer_profile.all_films.empty:
                primary_dataset = analyzer_profile.all_films
                print(f"Using comprehensive all_films dataset: {len(primary_dataset)} films")
            elif hasattr(analyzer_profile, 'ratings') and not analyzer_profile.ratings.empty:
                primary_dataset = analyzer_profile.ratings
                print(f"Using ratings dataset: {len(primary_dataset)} films")
                
            if primary_dataset is not None and not primary_dataset.empty:
                ratings_data = []
                for _, row in primary_dataset.iterrows():
                    # Handle different column names from different sources
                    movie_title = str(row.get('Name', row.get('Title', '')))
                    movie_year = row.get('Year', None)
                    if movie_year and str(movie_year).isdigit():
                        movie_year = int(movie_year)
                    else:
                        movie_year = None
                        
                    rating = row.get('Rating', None)
                    if rating:
                        rating = float(rating)
                    else:
                        rating = None
                        
                    # Parse watched_date properly
                    watched_date_raw = row.get('Watched Date', row.get('Date', None))
                    watched_date = None
                    if watched_date_raw:
                        try:
                            # Convert to pandas datetime then to Python date
                            parsed_date = pd.to_datetime(watched_date_raw, errors='coerce')
                            if not pd.isna(parsed_date):
                                watched_date = parsed_date.date()
                        except Exception as e:
                            print(f"Warning: Could not parse date '{watched_date_raw}': {e}")
                            watched_date = None
                    
                    is_rewatch = bool(row.get('Rewatch', row.get('Is_Rewatch', False)))
                    is_liked = bool(row.get('Is_Liked', False))
                    
                    rating_data = {
                        'profile_id': profile.id,
                        'movie_title': movie_title,
                        'movie_year': movie_year,
                        'rating': rating,
                        'watched_date': watched_date,
                        'is_rewatch': is_rewatch,
                        'is_liked': is_liked
                    }
                    ratings_data.append(rating_data)
                
                if ratings_data:
                    rating_repo.bulk_create_ratings(ratings_data)
                    
            # Also store likes data if available (separate from main dataset)
            if hasattr(analyzer_profile, 'likes') and not analyzer_profile.likes.empty:
                likes_data = []
                for _, row in analyzer_profile.likes.iterrows():
                    movie_title = str(row.get('Name', row.get('Title', '')))
                    movie_year = row.get('Year', None)
                    if movie_year and str(movie_year).isdigit():
                        movie_year = int(movie_year)
                    else:
                        movie_year = None
                        
                    likes_data.append({
                        'profile_id': profile.id,
                        'movie_title': movie_title,
                        'movie_year': movie_year,
                        'rating': None,  # Likes don't have ratings
                        'watched_date': None,  # Likes typically don't have watch dates
                        'is_rewatch': False,
                        'is_liked': True
                    })
                
                if likes_data:
                    print(f"Storing additional {len(likes_data)} liked films")
                    rating_repo.bulk_create_ratings(likes_data)
            
            # Store reviews data if available
            if hasattr(analyzer_profile, 'reviews') and not analyzer_profile.reviews.empty:
                reviews_data = []
                for _, row in analyzer_profile.reviews.iterrows():
                    review_data = {
                        'profile_id': profile.id,
                        'movie_title': str(row.get('Name', '')),
                        'movie_year': int(row.get('Year', 0)) if row.get('Year') and str(row.get('Year')).isdigit() else None,
                        'rating': float(row.get('Rating', 0)) if row.get('Rating') else None,
                        'review_text': str(row.get('Review', '')),
                        'published_date': row.get('Watched Date', None),
                        'likes_count': int(row.get('Likes', 0)) if row.get('Likes') else None
                    }
                    reviews_data.append(review_data)
                
                if reviews_data:
                    review_repo.bulk_create_reviews(reviews_data)
            
            # Copy data to permanent location
            permanent_dir = os.path.join(SCRAPED_DATA_DIR, username)
            os.makedirs(permanent_dir, exist_ok=True)
            shutil.copytree(scraper_output_dir, permanent_dir, dirs_exist_ok=True)
            
            # Update final job status
            job_repo.update_job_status(job_id, "completed", "Scraping completed successfully!", 100.0)
            
    except Exception as e:
        job_repo.update_job_status(job_id, "failed", f"Error occurred: {str(e)}", 0.0, str(e))
        profile_repo.update_profile(profile.id, scraping_status="error")

@app.get("/scrape/status/{username}")
async def get_scraping_status(username: str, db: Session = Depends(get_db)):
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

@app.get("/scrape/available")
async def get_available_profiles(db: Session = Depends(get_db)):
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
async def clear_scraped_data(username: str, db: Session = Depends(get_db)):
    """Clear scraped data for a user - alias for /profiles/{username}/data"""
    return await clear_profile_data(username, db)

# Analytics and Dashboard Endpoints

@app.get("/profiles/suggestions/update")
async def get_update_suggestions(db: Session = Depends(get_db)):
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
async def clear_profile_data(username: str, db: Session = Depends(get_db)):
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
async def get_comparative_analysis(usernames: str = "", db: Session = Depends(get_db)):
    """Get comparative analysis between multiple profiles"""
    if not usernames:
        raise HTTPException(status_code=400, detail="usernames parameter is required")
    
    # Parse usernames from query parameter (comma-separated or multiple params)
    username_list = [u.strip() for u in usernames.split(',') if u.strip()]
    
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
                    "rating": r.rating,
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
async def get_recommendations(username: str, db: Session = Depends(get_db)):
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
            "avg_rating": profile.avg_rating,
            "favorite_genres": []  # Could be enhanced with genre analysis
        },
        "recommendations": recommendations,
        "recommendation_type": "popular_unwatched",
        "total_recommendations": len(recommendations)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)