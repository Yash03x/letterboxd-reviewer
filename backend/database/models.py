from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, Date, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any

Base = declarative_base()

class Profile(Base):
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    scraping_status = Column(String(20), default="pending")
    
    # Profile metrics
    total_movies = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    join_date = Column(Date, nullable=True)
    
    # Additional metadata
    is_active = Column(Boolean, default=True)
    profile_image_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    website = Column(String(200), nullable=True)
    
    # Enhanced metrics stored as JSON
    enhanced_metrics = Column(JSON, nullable=True)
    
    # Relationships
    ratings = relationship("Rating", back_populates="profile", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="profile", cascade="all, delete-orphan")
    scraping_jobs = relationship("ScrapingJob", back_populates="profile", cascade="all, delete-orphan")
    lists = relationship("MovieList", back_populates="profile", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            # total_movies removed - use calculated total_films instead
            "avg_rating": self.avg_rating,
            "total_reviews": self.total_reviews,
            "join_date": self.join_date.isoformat() if self.join_date else None,
            "last_scraped_at": self.last_scraped_at.isoformat() if self.last_scraped_at else None,
            "scraping_status": self.scraping_status,
            "profile_image_url": self.profile_image_url,
            "bio": self.bio,
            "location": self.location,
            "website": self.website,
            "enhanced_metrics": self.enhanced_metrics or {}
        }

class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    
    # Movie details
    movie_title = Column(String(300), nullable=False)
    movie_year = Column(Integer, nullable=True)
    letterboxd_id = Column(String(100), nullable=True, index=True)
    
    # Rating details
    rating = Column(Float, nullable=True)  # 0.5 to 5.0 stars
    watched_date = Column(Date, nullable=True)
    is_rewatch = Column(Boolean, default=False)
    is_liked = Column(Boolean, default=False)  # User liked this film
    
    # Additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    tags = Column(JSON, nullable=True)  # Array of tags
    
    # Relationships
    profile = relationship("Profile", back_populates="ratings")

class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    
    # Movie details
    movie_title = Column(String(300), nullable=False)
    movie_year = Column(Integer, nullable=True)
    letterboxd_id = Column(String(100), nullable=True, index=True)
    
    # Review content
    review_text = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    contains_spoilers = Column(Boolean, default=False)
    
    # Engagement metrics
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    
    # Timestamps
    published_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    profile = relationship("Profile", back_populates="reviews")

class MovieList(Base):
    __tablename__ = "movie_lists"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    
    # List details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=True)
    is_ranked = Column(Boolean, default=False)
    
    # List metadata
    movie_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Movies in the list (stored as JSON array)
    movies = Column(JSON, nullable=True)  # Array of movie objects
    
    # Relationships
    profile = relationship("Profile", back_populates="lists")

class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    
    # Job status
    status = Column(String(20), default="queued")  # queued, in_progress, completed, failed
    progress_message = Column(Text, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    
    # Timestamps
    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Job metadata
    job_type = Column(String(50), default="full_scrape")  # full_scrape, update_recent, etc.
    job_params = Column(JSON, nullable=True)
    
    # Relationships
    profile = relationship("Profile", back_populates="scraping_jobs")

class SystemMetrics(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # System stats
    total_profiles = Column(Integer, default=0)
    total_movies_tracked = Column(Integer, default=0)
    total_reviews = Column(Integer, default=0)
    
    # Performance metrics
    avg_scraping_time = Column(Float, default=0.0)  # in minutes
    active_scraping_jobs = Column(Integer, default=0)
    
    # Additional metrics as JSON
    metrics = Column(JSON, nullable=True)