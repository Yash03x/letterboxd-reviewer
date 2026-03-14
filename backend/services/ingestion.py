from __future__ import annotations

import math
from sqlalchemy.orm import Session
import pandas as pd

from database.repository import RatingRepository, ReviewRepository


def parse_date_for_db(date_value):
    """Parse date string/object to Python date object for database storage."""
    if not date_value:
        return None
    try:
        parsed_date = pd.to_datetime(date_value, errors="coerce")
        if not pd.isna(parsed_date):
            return parsed_date.date()
    except Exception:
        pass
    return None


def parse_rating_value(value):
    """Parse rating values safely, returning None for NaN/Inf/invalid."""
    if value is None:
        return None

    if isinstance(value, str) and not value.strip():
        return None

    try:
        numeric = pd.to_numeric(value, errors="coerce")
    except Exception:
        return None

    if pd.isna(numeric):
        return None

    parsed = float(numeric)
    if not math.isfinite(parsed):
        return None
    return parsed


def parse_rewatch_status(rewatch_value):
    """Parse rewatch status from various formats (Yes/No, True/False, 1/0)."""
    if not rewatch_value:
        return False

    if pd.isna(rewatch_value):
        return False

    if isinstance(rewatch_value, bool):
        return rewatch_value

    if isinstance(rewatch_value, (int, float)):
        return bool(rewatch_value)

    rewatch_str = str(rewatch_value).lower().strip()
    return rewatch_str in ["yes", "true", "1", "y"]


def unified_data_loader(analyzer_profile, profile_id: int, db: Session):
    """
    Load all profile data with deduplication.
    Prevents duplicates regardless of source (upload vs scrape).
    """
    rating_repo = RatingRepository(db)
    review_repo = ReviewRepository(db)

    print(f"Clearing existing data for profile {profile_id}")
    rating_repo.delete_ratings_by_profile(profile_id)
    review_repo.delete_reviews_by_profile(profile_id)

    all_movies = {}

    if hasattr(analyzer_profile, "all_films") and not analyzer_profile.all_films.empty:
        print(f"Processing comprehensive films dataset: {len(analyzer_profile.all_films)} films")
        for _, row in analyzer_profile.all_films.iterrows():
            movie_title = str(row.get("Name", row.get("Title", "")))
            movie_year = row.get("Year", None)
            if movie_year and str(movie_year).isdigit():
                movie_year = int(movie_year)
            else:
                movie_year = None

            movie_key = (movie_title, movie_year)
            watched_date = None
            watched_date_raw = row.get("Watched Date", row.get("Date", None))
            if watched_date_raw:
                try:
                    parsed_date = pd.to_datetime(watched_date_raw, errors="coerce")
                    if not pd.isna(parsed_date):
                        watched_date = parsed_date.date()
                except Exception:
                    watched_date = None

            all_movies[movie_key] = {
                "profile_id": profile_id,
                "movie_title": movie_title,
                "movie_year": movie_year,
                "letterboxd_id": str(row.get("Film_ID", "")) if row.get("Film_ID") else None,
                "rating": parse_rating_value(row.get("Rating")),
                "watched_date": watched_date,
                "is_rewatch": parse_rewatch_status(row.get("Rewatch", row.get("Is_Rewatch", False))),
                "is_liked": False,
                "film_slug": str(row.get("Slug", "")) if row.get("Slug") else None,
                "poster_url": str(row.get("Poster_URL", "")) if row.get("Poster_URL") else None,
            }

    if hasattr(analyzer_profile, "diary") and not analyzer_profile.diary.empty:
        print(f"Merging diary data for watched dates: {len(analyzer_profile.diary)} entries")
        for _, row in analyzer_profile.diary.iterrows():
            movie_title = str(row.get("Name", ""))
            movie_year = row.get("Year", None)
            if movie_year and str(movie_year).isdigit():
                movie_year = int(movie_year)
            else:
                movie_year = None

            movie_key = (movie_title, movie_year)
            watched_date = None
            watched_date_raw = row.get("Watched Date", None)
            if watched_date_raw and str(watched_date_raw).strip():
                try:
                    parsed_date = pd.to_datetime(watched_date_raw, errors="coerce")
                    if not pd.isna(parsed_date):
                        watched_date = parsed_date.date()
                except Exception:
                    watched_date = None

            if movie_key in all_movies and watched_date and not all_movies[movie_key]["watched_date"]:
                all_movies[movie_key]["watched_date"] = watched_date

            if movie_key in all_movies and parse_rewatch_status(row.get("Is_Rewatch", False)):
                all_movies[movie_key]["is_rewatch"] = True

    elif hasattr(analyzer_profile, "ratings") and not analyzer_profile.ratings.empty:
        print(f"Processing ratings dataset: {len(analyzer_profile.ratings)} films")
        for _, row in analyzer_profile.ratings.iterrows():
            movie_title = str(row.get("Name", ""))
            movie_year = row.get("Year", None)
            if movie_year and str(movie_year).isdigit():
                movie_year = int(movie_year)
            else:
                movie_year = None

            movie_key = (movie_title, movie_year)
            all_movies[movie_key] = {
                "profile_id": profile_id,
                "movie_title": movie_title,
                "movie_year": movie_year,
                "letterboxd_id": str(row.get("Film_ID", "")) if row.get("Film_ID") else None,
                "rating": parse_rating_value(row.get("Rating")),
                "watched_date": parse_date_for_db(row.get("Watched Date", None)),
                "is_rewatch": parse_rewatch_status(row.get("Rewatch", False)),
                "is_liked": False,
                "film_slug": str(row.get("Slug", "")) if row.get("Slug") else None,
                "poster_url": str(row.get("Poster_URL", "")) if row.get("Poster_URL") else None,
            }

    if hasattr(analyzer_profile, "likes") and not analyzer_profile.likes.empty:
        print(f"Processing likes data: {len(analyzer_profile.likes)} films")
        for _, row in analyzer_profile.likes.iterrows():
            movie_title = str(row.get("Name", row.get("Title", "")))
            movie_year = row.get("Year", None)
            if movie_year and str(movie_year).isdigit():
                movie_year = int(movie_year)
            else:
                movie_year = None

            movie_key = (movie_title, movie_year)
            if movie_key in all_movies:
                all_movies[movie_key]["is_liked"] = True

    if all_movies:
        ratings_data = list(all_movies.values())
        try:
            rating_repo.bulk_create_ratings(ratings_data)
            print(f"Inserted {len(ratings_data)} unique movies (no duplicates)")
        except Exception as exc:
            print(f"Bulk insert failed ({exc}), trying individual inserts...")
            inserted_count = 0
            for rating_data in ratings_data:
                try:
                    rating_repo.create_rating(**rating_data)
                    inserted_count += 1
                except Exception:
                    pass
            print(f"Inserted {inserted_count} out of {len(ratings_data)} movies")

    if hasattr(analyzer_profile, "reviews") and not analyzer_profile.reviews.empty:
        print(f"Processing reviews data: {len(analyzer_profile.reviews)} reviews")
        reviews_data = []
        for _, row in analyzer_profile.reviews.iterrows():
            reviews_data.append(
                {
                    "profile_id": profile_id,
                    "movie_title": str(row.get("Name", row.get("Title", ""))),
                    "movie_year": int(row.get("Year")) if row.get("Year") and str(row.get("Year")).isdigit() else None,
                    "letterboxd_id": str(row.get("Film_ID", "")) if row.get("Film_ID") else None,
                    "review_text": str(row.get("Review", "")),
                    "rating": parse_rating_value(row.get("Rating")),
                    "published_date": parse_date_for_db(row.get("Review_Date", row.get("Date", None))),
                    "likes_count": int(row.get("Review_Likes", 0)) if row.get("Review_Likes") else 0,
                    "comments_count": int(row.get("Review_Comments", 0)) if row.get("Review_Comments") else 0,
                    "contains_spoilers": bool(row.get("Contains Spoilers", False)),
                }
            )

        if reviews_data:
            review_repo.bulk_create_reviews(reviews_data)
            print(f"Inserted {len(reviews_data)} reviews")

    return len(all_movies)
