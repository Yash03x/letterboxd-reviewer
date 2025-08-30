from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_, String
from .models import Profile, Rating, Review, MovieList, ScrapingJob
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json

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
            Rating.rating.isnot(None)
        ).group_by(Rating.rating).all()
        
        return {str(rating): count for rating, count in results}
    
    def get_monthly_watch_stats(self, profile_id: int, months: int = 12) -> List[Dict]:
        """Get monthly watching statistics"""
        cutoff_date = datetime.utcnow().date() - timedelta(days=months * 30)
        
        results = self.db.query(
            func.strftime('%Y-%m', Rating.watched_date).label('month'),
            func.count(Rating.id).label('count'),
            func.avg(Rating.rating).label('avg_rating')
        ).filter(
            Rating.profile_id == profile_id,
            Rating.watched_date >= cutoff_date
        ).group_by(
            func.strftime('%Y-%m', Rating.watched_date)
        ).order_by('month').all()
        
        return [
            {
                'month': month,
                'movies_watched': count,
                'average_rating': round(avg_rating, 2) if avg_rating else None
            }
            for month, count, avg_rating in results
        ]

    def get_global_rating_distribution(self) -> Dict[str, int]:
        """Get rating distribution across all profiles"""
        results = self.db.query(
            Rating.rating,
            func.count(Rating.id).label('count')
        ).filter(
            Rating.rating.isnot(None)
        ).group_by(Rating.rating).all()

        return {str(rating): count for rating, count in results}
    
    def get_global_monthly_activity(self) -> List[Dict]:
        """Get monthly activity data across all profiles"""
        # Calculate cutoff month (12 months ago from current month)
        current_date = datetime.utcnow().date()
        cutoff_month = current_date.replace(day=1) - timedelta(days=365)
        cutoff_month = cutoff_month.replace(day=1)  # Start of the month
        
        results = self.db.query(
            func.strftime('%Y-%m', Rating.watched_date).label('month'),
            func.count(Rating.id).label('movies_watched'),
            func.avg(Rating.rating).label('avg_rating')
        ).filter(
            Rating.watched_date >= cutoff_month,
            Rating.watched_date.isnot(None)
        ).group_by(
            func.strftime('%Y-%m', Rating.watched_date)
        ).order_by('month').all()
        
        return [
            {
                'month': month,
                'movies_watched': count,
                'average_rating': round(avg_rating, 2) if avg_rating else None
            }
            for month, count, avg_rating in results
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
    
    def get_job_by_profile(self, profile_id: int) -> Optional[ScrapingJob]:
        return self.db.query(ScrapingJob).filter(
            ScrapingJob.profile_id == profile_id
        ).order_by(ScrapingJob.queued_at.desc()).first()

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
            Rating.rating.isnot(None)
        ).scalar() or 0.0
        
        # Calculate trends based on recent activity
        trends = self._calculate_trends()
        
        return {
            "total_profiles": total_profiles,
            "total_movies_tracked": total_unique_movies,
            "total_reviews": total_reviews,
            "active_scraping_jobs": active_jobs,
            "global_avg_rating": round(float(global_avg_rating), 2),
            "last_updated": datetime.utcnow().isoformat(),
            "trends": trends
        }
    
    def get_top_rated_movies(self, limit: int = 50) -> List[Dict]:
        """Get top-rated movies across all profiles"""
        results = self.db.query(
            Rating.movie_title,
            Rating.movie_year,
            func.avg(Rating.rating).label('avg_rating'),
            func.count(Rating.id).label('rating_count')
        ).filter(
            Rating.rating.isnot(None)
        ).group_by(
            Rating.movie_title, Rating.movie_year
        ).having(
            func.count(Rating.id) >= 3  # At least 3 ratings
        ).order_by(
            desc('avg_rating')
        ).limit(limit).all()
        
        return [
            {
                'title': title,
                'year': year,
                'average_rating': round(avg_rating, 2),
                'total_ratings': count
            }
            for title, year, avg_rating, count in results
        ]

    def _calculate_trends(self) -> Dict[str, Dict[str, Any]]:
        """Calculate trends based on recent activity (current month vs previous month)"""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        
        # Current month stats
        current_month_profiles = self.db.query(func.count(Profile.id)).filter(
            Profile.created_at >= current_month_start
        ).scalar()
        
        current_month_movies = self.db.query(func.count(Rating.id)).filter(
            Rating.created_at >= current_month_start
        ).scalar()
        
        current_month_reviews = self.db.query(func.count(Review.id)).filter(
            Review.created_at >= current_month_start
        ).scalar()
        
        # Previous month stats
        last_month_profiles = self.db.query(func.count(Profile.id)).filter(
            Profile.created_at >= last_month_start,
            Profile.created_at < current_month_start
        ).scalar()
        
        last_month_movies = self.db.query(func.count(Rating.id)).filter(
            Rating.created_at >= last_month_start,
            Rating.created_at < current_month_start
        ).scalar()
        
        last_month_reviews = self.db.query(func.count(Review.id)).filter(
            Review.created_at >= last_month_start,
            Review.created_at < current_month_start
        ).scalar()
        
        # Calculate percentage changes
        def calculate_percentage_change(current, previous):
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return ((current - previous) / previous) * 100
        
        trends = {
            "profiles": {
                "value": calculate_percentage_change(current_month_profiles, last_month_profiles),
                "is_positive": current_month_profiles >= last_month_profiles
            },
            "movies": {
                "value": calculate_percentage_change(current_month_movies, last_month_movies),
                "is_positive": current_month_movies >= last_month_movies
            },
            "reviews": {
                "value": calculate_percentage_change(current_month_reviews, last_month_reviews),
                "is_positive": current_month_reviews >= last_month_reviews
            }
        }
        
        return trends