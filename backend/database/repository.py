import math
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_, String, extract
from .models import Profile, Rating, Review, MovieList, ScrapingJob
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any


def _format_month_bucket(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


RATING_MIN = 0.0
RATING_MAX = 5.0


def _coerce_finite_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _safe_round(value: Any, digits: int = 2) -> Optional[float]:
    numeric = _coerce_finite_float(value)
    if numeric is None:
        return None
    return round(numeric, digits)

class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_profile_by_username(self, username: str) -> Optional[Profile]:
        return self.db.query(Profile).filter(Profile.username == username).first()
    
    def get_profile_by_id(self, profile_id: int) -> Optional[Profile]:
        return self.db.query(Profile).filter(Profile.id == profile_id).first()
    
    def get_all_profiles(self, active_only: bool = True) -> List[Profile]:
        query = self.db.query(Profile)
        if active_only:
            query = query.filter(Profile.is_active == True)
        return query.order_by(Profile.updated_at.desc()).all()
    
    def create_profile(self, username: str, **kwargs) -> Profile:
        profile = Profile(username=username, **kwargs)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile
    
    def update_profile(self, profile_id: int, **kwargs) -> Optional[Profile]:
        profile = self.get_profile_by_id(profile_id)
        if profile:
            for key, value in kwargs.items():
                setattr(profile, key, value)
            profile.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(profile)
        return profile
    
    def delete_profile(self, profile_id: int) -> bool:
        profile = self.get_profile_by_id(profile_id)
        if profile:
            self.db.delete(profile)
            self.db.commit()
            return True
        return False
    
    def get_profiles_requiring_update(self, hours: int = 24) -> List[Profile]:
        """Get profiles that haven't been updated in X hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return self.db.query(Profile).filter(
            or_(
                Profile.last_scraped_at == None,
                Profile.last_scraped_at < cutoff_time
            )
        ).all()

class RatingRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_ratings_by_profile(self, profile_id: int, limit: int = None) -> List[Rating]:
        query = self.db.query(Rating).filter(Rating.profile_id == profile_id)
        query = query.order_by(Rating.watched_date.desc())
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def create_rating(self, profile_id: int, **kwargs) -> Rating:
        rating = Rating(profile_id=profile_id, **kwargs)
        self.db.add(rating)
        self.db.commit()
        self.db.refresh(rating)
        return rating
    
    def bulk_create_ratings(self, ratings_data: List[Dict]) -> int:
        """Bulk insert ratings for better performance"""
        ratings = [Rating(**data) for data in ratings_data]
        self.db.add_all(ratings)
        self.db.commit()
        return len(ratings)
    
    def delete_ratings_by_profile(self, profile_id: int) -> int:
        """Delete all ratings for a profile"""
        count = self.db.query(Rating).filter(Rating.profile_id == profile_id).count()
        self.db.query(Rating).filter(Rating.profile_id == profile_id).delete()
        self.db.commit()
        return count
    
    def get_rating_distribution(self, profile_id: int) -> Dict[str, int]:
        """Get rating distribution for a profile"""
        results = self.db.query(
            Rating.rating,
            func.count(Rating.id).label('count')
        ).filter(
            Rating.profile_id == profile_id,
            Rating.rating.isnot(None),
            Rating.rating >= RATING_MIN,
            Rating.rating <= RATING_MAX,
        ).group_by(Rating.rating).all()
        
        return {str(rating): count for rating, count in results}
    
    def get_monthly_watch_stats(self, profile_id: int, months: int = 12) -> List[Dict]:
        """Get monthly watching statistics"""
        cutoff_date = datetime.utcnow().date() - timedelta(days=months * 30)
        year_bucket = extract('year', Rating.watched_date)
        month_bucket = extract('month', Rating.watched_date)

        results = self.db.query(
            year_bucket.label('year'),
            month_bucket.label('month'),
            func.count(Rating.id).label('count'),
            func.avg(Rating.rating).label('avg_rating')
        ).filter(
            Rating.profile_id == profile_id,
            Rating.watched_date >= cutoff_date,
            Rating.rating.is_(None) | and_(Rating.rating >= RATING_MIN, Rating.rating <= RATING_MAX),
        ).group_by(
            year_bucket,
            month_bucket
        ).order_by(year_bucket, month_bucket).all()
        
        return [
            {
                'month': _format_month_bucket(year, month),
                'movies_watched': count,
                'average_rating': _safe_round(avg_rating, 2)
            }
            for year, month, count, avg_rating in results
        ]

    def get_global_rating_distribution(self) -> Dict[str, int]:
        """Get rating distribution across all profiles"""
        results = self.db.query(
            Rating.rating,
            func.count(Rating.id).label('count')
        ).filter(
            Rating.rating.isnot(None),
            Rating.rating >= RATING_MIN,
            Rating.rating <= RATING_MAX,
        ).group_by(Rating.rating).all()

        return {str(rating): count for rating, count in results}
    
    def get_global_monthly_activity(self) -> List[Dict]:
        """Get monthly activity data across all profiles"""
        cutoff_date = datetime.now().date() - timedelta(days=365)
        year_bucket = extract('year', Rating.watched_date)
        month_bucket = extract('month', Rating.watched_date)

        results = self.db.query(
            year_bucket.label('year'),
            month_bucket.label('month'),
            func.count(Rating.id).label('movies_watched'),
            func.avg(Rating.rating).label('avg_rating')
        ).filter(
            Rating.watched_date >= cutoff_date,
            Rating.watched_date.isnot(None),
            Rating.rating.is_(None) | and_(Rating.rating >= RATING_MIN, Rating.rating <= RATING_MAX),
        ).group_by(
            year_bucket,
            month_bucket
        ).order_by(year_bucket, month_bucket).all()
        
        return [
            {
                'month': _format_month_bucket(year, month),
                'movies_watched': count,
                'average_rating': _safe_round(avg_rating, 2)
            }
            for year, month, count, avg_rating in results
        ]

class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_reviews_by_profile(self, profile_id: int, limit: int = None) -> List[Review]:
        query = self.db.query(Review).filter(Review.profile_id == profile_id)
        query = query.order_by(Review.published_date.desc())
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def create_review(self, profile_id: int, **kwargs) -> Review:
        review = Review(profile_id=profile_id, **kwargs)
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review
    
    def bulk_create_reviews(self, reviews_data: List[Dict]) -> int:
        """Bulk insert reviews for better performance"""
        reviews = [Review(**data) for data in reviews_data]
        self.db.add_all(reviews)
        self.db.commit()
        return len(reviews)
    
    def delete_reviews_by_profile(self, profile_id: int) -> int:
        """Delete all reviews for a profile"""
        count = self.db.query(Review).filter(Review.profile_id == profile_id).count()
        self.db.query(Review).filter(Review.profile_id == profile_id).delete()
        self.db.commit()
        return count

class ScrapingJobRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create_job(self, profile_id: int, job_type: str = "full_scrape", **kwargs) -> ScrapingJob:
        job = ScrapingJob(profile_id=profile_id, job_type=job_type, **kwargs)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def update_job_status(self, job_id: int, status: str, progress_message: str = None, 
                         progress_percentage: float = None, error_message: str = None) -> Optional[ScrapingJob]:
        job = self.db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if job:
            job.status = status
            if progress_message:
                job.progress_message = progress_message
            if progress_percentage is not None:
                job.progress_percentage = progress_percentage
            if error_message:
                job.error_message = error_message
            
            if status == "in_progress" and not job.started_at:
                job.started_at = datetime.utcnow()
            elif status in ["completed", "failed"]:
                job.completed_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(job)
        return job
    
    def get_active_jobs(self) -> List[ScrapingJob]:
        return self.db.query(ScrapingJob).filter(
            ScrapingJob.status.in_(["queued", "in_progress"])
        ).order_by(ScrapingJob.queued_at).all()

    def get_job_by_id(self, job_id: int) -> Optional[ScrapingJob]:
        return (
            self.db.query(ScrapingJob)
            .filter(ScrapingJob.id == job_id)
            .populate_existing()
            .first()
        )
    
    def get_job_by_profile(self, profile_id: int) -> Optional[ScrapingJob]:
        return self.db.query(ScrapingJob).filter(
            ScrapingJob.profile_id == profile_id
        ).order_by(ScrapingJob.queued_at.desc()).first()

    def get_jobs_by_profile(self, profile_id: int, limit: int = 20) -> List[ScrapingJob]:
        return (
            self.db.query(ScrapingJob)
            .filter(ScrapingJob.profile_id == profile_id)
            .order_by(ScrapingJob.queued_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent_jobs_with_profile(self, limit: int = 50):
        # Subquery: latest job id per profile
        latest_ids = (
            self.db.query(func.max(ScrapingJob.id).label("max_id"))
            .group_by(ScrapingJob.profile_id)
            .subquery()
        )
        return (
            self.db.query(ScrapingJob, Profile.username)
            .join(Profile, Profile.id == ScrapingJob.profile_id)
            .filter(ScrapingJob.id.in_(latest_ids))
            .order_by(ScrapingJob.queued_at.desc())
            .limit(limit)
            .all()
        )

    def get_active_jobs_for_profile(self, profile_id: int, exclude_job_id: Optional[int] = None) -> List[ScrapingJob]:
        query = self.db.query(ScrapingJob).filter(
            ScrapingJob.profile_id == profile_id,
            ScrapingJob.status.in_(["queued", "in_progress"]),
        )
        if exclude_job_id is not None:
            query = query.filter(ScrapingJob.id != exclude_job_id)
        return query.order_by(ScrapingJob.queued_at.desc()).all()

class AnalyticsRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall system statistics"""
        total_profiles = self.db.query(func.count(Profile.id)).scalar()
        
        # Count unique movies across all profiles (not sum of ratings)
        # Use subquery to count distinct movie combinations
        from sqlalchemy import distinct
        unique_movies_subquery = self.db.query(
            distinct(Rating.movie_title), 
            distinct(Rating.movie_year)
        ).subquery()
        
        # Simpler approach: just count distinct movie_title, movie_year pairs
        total_unique_movies = self.db.query(Rating.movie_title, Rating.movie_year).distinct().count()
        
        total_reviews = self.db.query(func.count(Review.id)).scalar()
        
        # Active scraping jobs
        active_jobs = self.db.query(func.count(ScrapingJob.id)).filter(
            ScrapingJob.status.in_(["queued", "in_progress"])
        ).scalar()
        
        # Global average rating across all ratings
        global_avg_rating = self.db.query(func.avg(Rating.rating)).filter(
            Rating.rating.isnot(None),
            Rating.rating >= RATING_MIN,
            Rating.rating <= RATING_MAX,
        ).scalar() or 0.0
        
        return {
            "total_profiles": total_profiles,
            "total_movies_tracked": total_unique_movies,
            "total_reviews": total_reviews,
            "active_scraping_jobs": active_jobs,
            "global_avg_rating": _safe_round(global_avg_rating, 2) or 0.0,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def get_top_rated_movies(self, limit: int = 50) -> List[Dict]:
        """Get top-rated movies across all profiles"""
        results = self.db.query(
            Rating.movie_title,
            Rating.movie_year,
            func.avg(Rating.rating).label('avg_rating'),
            func.count(Rating.id).label('rating_count')
        ).filter(
            Rating.rating.isnot(None),
            Rating.rating >= RATING_MIN,
            Rating.rating <= RATING_MAX,
        ).group_by(
            Rating.movie_title, Rating.movie_year
        ).having(
            func.count(Rating.id) >= 3  # At least 3 ratings
        ).order_by(
            desc('avg_rating')
        ).limit(limit).all()
        
        movies: List[Dict[str, Any]] = []
        for title, year, avg_rating, count in results:
            safe_avg = _safe_round(avg_rating, 2)
            if safe_avg is None:
                continue
            movies.append(
                {
                    "title": title,
                    "year": year,
                    "average_rating": safe_avg,
                    "total_ratings": count,
                }
            )
        return movies
