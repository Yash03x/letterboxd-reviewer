"""Create initial schema

Revision ID: 20260313_0001
Revises:
Create Date: 2026-03-13 14:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260313_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraping_status", sa.String(length=20), nullable=True),
        sa.Column("avg_rating", sa.Float(), nullable=True),
        sa.Column("total_reviews", sa.Integer(), nullable=True),
        sa.Column("join_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("profile_image_url", sa.String(length=500), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("website", sa.String(length=200), nullable=True),
        sa.Column("enhanced_metrics", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profiles_id"), "profiles", ["id"], unique=False)
    op.create_index(op.f("ix_profiles_username"), "profiles", ["username"], unique=True)

    op.create_table(
        "system_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("total_profiles", sa.Integer(), nullable=True),
        sa.Column("total_movies_tracked", sa.Integer(), nullable=True),
        sa.Column("total_reviews", sa.Integer(), nullable=True),
        sa.Column("avg_scraping_time", sa.Float(), nullable=True),
        sa.Column("active_scraping_jobs", sa.Integer(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_metrics_id"), "system_metrics", ["id"], unique=False)

    op.create_table(
        "movie_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=True),
        sa.Column("is_ranked", sa.Boolean(), nullable=True),
        sa.Column("movie_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("movies", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_movie_lists_id"), "movie_lists", ["id"], unique=False)

    op.create_table(
        "ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("movie_title", sa.String(length=300), nullable=False),
        sa.Column("movie_year", sa.Integer(), nullable=True),
        sa.Column("letterboxd_id", sa.String(length=100), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("watched_date", sa.Date(), nullable=True),
        sa.Column("is_rewatch", sa.Boolean(), nullable=True),
        sa.Column("is_liked", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("film_slug", sa.String(length=200), nullable=True),
        sa.Column("poster_url", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "movie_title", "movie_year", name="unique_user_movie_rating"),
    )
    op.create_index(op.f("ix_ratings_id"), "ratings", ["id"], unique=False)
    op.create_index(op.f("ix_ratings_letterboxd_id"), "ratings", ["letterboxd_id"], unique=False)

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("movie_title", sa.String(length=300), nullable=False),
        sa.Column("movie_year", sa.Integer(), nullable=True),
        sa.Column("letterboxd_id", sa.String(length=100), nullable=True),
        sa.Column("review_text", sa.Text(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("contains_spoilers", sa.Boolean(), nullable=True),
        sa.Column("likes_count", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reviews_id"), "reviews", ["id"], unique=False)
    op.create_index(op.f("ix_reviews_letterboxd_id"), "reviews", ["letterboxd_id"], unique=False)

    op.create_table(
        "scraping_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("progress_message", sa.Text(), nullable=True),
        sa.Column("progress_percentage", sa.Float(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(length=50), nullable=True),
        sa.Column("job_params", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scraping_jobs_id"), "scraping_jobs", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scraping_jobs_id"), table_name="scraping_jobs")
    op.drop_table("scraping_jobs")
    op.drop_index(op.f("ix_reviews_letterboxd_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_id"), table_name="reviews")
    op.drop_table("reviews")
    op.drop_index(op.f("ix_ratings_letterboxd_id"), table_name="ratings")
    op.drop_index(op.f("ix_ratings_id"), table_name="ratings")
    op.drop_table("ratings")
    op.drop_index(op.f("ix_movie_lists_id"), table_name="movie_lists")
    op.drop_table("movie_lists")
    op.drop_index(op.f("ix_system_metrics_id"), table_name="system_metrics")
    op.drop_table("system_metrics")
    op.drop_index(op.f("ix_profiles_username"), table_name="profiles")
    op.drop_index(op.f("ix_profiles_id"), table_name="profiles")
    op.drop_table("profiles")
