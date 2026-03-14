# Database Schema

PostgreSQL database used by the FastAPI backend. Managed via Alembic migrations.

---

## Tables

### `profiles`
One row per tracked Letterboxd user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer PK | Auto-increment |
| `username` | varchar(50) UNIQUE | Letterboxd username |
| `created_at` | timestamptz | When profile was added to Spyboxd |
| `updated_at` | timestamptz | Last DB update |
| `last_scraped_at` | timestamptz | When the last successful scrape ran |
| `scraping_status` | varchar(20) | `pending` / `in_progress` / `completed` / `error` |
| `avg_rating` | float | Computed from `ratings` table after each scrape |
| `total_reviews` | integer | Count of rows in `reviews` table for this profile |
| `join_date` | date | Letterboxd join date (from profile page, nullable) |
| `is_active` | boolean | Soft-delete flag |
| `profile_image_url` | varchar(500) | Avatar URL (from profile page, nullable) |
| `bio` | text | Profile bio (from profile page, nullable) |
| `location` | varchar(100) | Location (from profile page, nullable) |
| `website` | varchar(200) | Website (from profile page, nullable) |
| `enhanced_metrics` | JSON | Reserved for future computed analytics |

> **Note:** `bio`, `location`, `website`, `profile_image_url`, and `join_date` are populated by the HTML scraper (`scraper_html.py`). The RSS scraper cannot access these (Cloudflare blocks the profile page from VPS). They will be `null` for VPS-scraped profiles.

---

### `ratings`
One row per film watched by a user. This is the core data table — every film the user has logged in their Letterboxd diary ends up here.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer PK | Auto-increment |
| `profile_id` | integer FK → `profiles.id` | Owner |
| `movie_title` | varchar(300) | Film title |
| `movie_year` | integer | Release year (nullable) |
| `letterboxd_id` | varchar(100) | TMDB movie ID (from RSS `tmdb:movieId`) |
| `rating` | float | 0.5–5.0 in 0.5 increments, or `null` if unrated |
| `watched_date` | date | Date the user watched the film (from `letterboxd:watchedDate`) |
| `is_rewatch` | boolean | Whether this was a rewatch (`letterboxd:rewatch`) |
| `is_liked` | boolean | Whether the user liked the film (`letterboxd:memberLike`) |
| `film_slug` | varchar(200) | Letterboxd URL slug (e.g. `the-godfather`) |
| `poster_url` | varchar(500) | Film poster image URL (extracted from RSS description `<img>`) |
| `tags` | JSON | Reserved (not populated by RSS scraper) |
| `created_at` | timestamptz | Row insert time |

**Unique constraint:** `(profile_id, movie_title, movie_year)` — prevents duplicate entries for the same film per user.

> **RSS coverage:** All diary entries are captured. Films rated without a diary date get `watched_date = null`. Rewatches each appear as a separate diary entry but are deduplicated to one row here (most recent watch is kept).

---

### `reviews`
One row per written review. A user can have a rating without a review; a review always has at least a film title.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer PK | Auto-increment |
| `profile_id` | integer FK → `profiles.id` | Owner |
| `movie_title` | varchar(300) | Film title |
| `movie_year` | integer | Release year (nullable) |
| `letterboxd_id` | varchar(100) | TMDB movie ID |
| `review_text` | text | Full review text (from RSS description CDATA, HTML stripped) |
| `rating` | float | Rating at time of review (nullable) |
| `contains_spoilers` | boolean | Always `false` (not detectable from RSS) |
| `likes_count` | integer | Always `0` (not in RSS feed) |
| `comments_count` | integer | Always `0` (not in RSS feed) |
| `published_date` | date | Review publish date (from RSS `pubDate`) |
| `created_at` | timestamptz | Row insert time |

---

### `movie_lists`
Custom Letterboxd lists. Not populated by the RSS scraper (list pages are Cloudflare-blocked on VPS). Reserved for future use or manual upload.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer PK | Auto-increment |
| `profile_id` | integer FK → `profiles.id` | Owner |
| `name` | varchar(200) | List name |
| `description` | text | List description (nullable) |
| `is_public` | boolean | Always `true` |
| `is_ranked` | boolean | Whether the list is ranked |
| `movie_count` | integer | Number of films in the list |
| `movies` | JSON | Array of movie objects |
| `created_at` / `updated_at` | timestamptz | Timestamps |

---

### `scraping_jobs`
Audit log of every scrape attempt.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer PK | Auto-increment |
| `profile_id` | integer FK → `profiles.id` | Target profile |
| `status` | varchar(20) | `queued` / `in_progress` / `completed` / `failed` |
| `progress_message` | text | Human-readable status update (streamed via SSE) |
| `progress_percentage` | float | 0–100 |
| `queued_at` | timestamptz | When job was created |
| `started_at` | timestamptz | When Celery worker picked it up |
| `completed_at` | timestamptz | When job finished |
| `error_message` | text | Exception message if failed |
| `retry_count` | integer | Number of retries attempted |
| `job_type` | varchar(50) | Always `full_scrape` currently |
| `job_params` | JSON | Reserved |

---

### `system_metrics`
Periodic snapshots of system-wide stats. Not actively written yet — reserved for future scheduled metric collection.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer PK | Auto-increment |
| `timestamp` | timestamptz | Snapshot time |
| `total_profiles` | integer | Profile count |
| `total_movies_tracked` | integer | Unique film count |
| `total_reviews` | integer | Review count |
| `avg_scraping_time` | float | Minutes |
| `active_scraping_jobs` | integer | Jobs in flight |
| `metrics` | JSON | Additional metrics |

---

## Relationships

```
profiles
  ├── ratings         (one-to-many, cascade delete)
  ├── reviews         (one-to-many, cascade delete)
  ├── movie_lists     (one-to-many, cascade delete)
  └── scraping_jobs   (one-to-many, cascade delete)
```

---

## Data Pipeline

```
Letterboxd RSS feed  ──►  scraper.py  ──►  CSV files (temp dir)
                                                  │
                                                  ▼
                                      services/profile_loader.py
                                      (loads CSVs into DataFrames)
                                                  │
                                                  ▼
                                      services/ingestion.py
                                      (writes to DB via repositories)
                                                  │
                              ┌───────────────────┼───────────────────┐
                              ▼                   ▼                   ▼
                          ratings             reviews           profiles
                          (film data)         (review text)     (avg_rating,
                                                                 total_reviews)
```

### What the RSS scraper captures

| Data | Source field | Stored in |
|------|-------------|-----------|
| Film title | `letterboxd:filmTitle` | `ratings.movie_title` |
| Release year | `letterboxd:filmYear` | `ratings.movie_year` |
| Star rating | `letterboxd:memberRating` | `ratings.rating` |
| Watch date | `letterboxd:watchedDate` | `ratings.watched_date` |
| Liked | `letterboxd:memberLike` | `ratings.is_liked` |
| Rewatch | `letterboxd:rewatch` | `ratings.is_rewatch` |
| TMDB ID | `tmdb:movieId` | `ratings.letterboxd_id` |
| Poster URL | `<img>` in description | `ratings.poster_url` |
| Review text | description CDATA (text) | `reviews.review_text` |
| Review date | `pubDate` | `reviews.published_date` |
| Film slug | URL path segment | `ratings.film_slug` |

### What's NOT captured (Cloudflare-blocked on VPS)

- Profile bio, location, avatar, join date, website
- Watchlist
- Custom lists
- Films rated without a diary entry (edge case: user rates a film but doesn't log a watch date)

---

## Computed values

`profiles.avg_rating` and `profiles.total_reviews` are **recomputed after every scrape** from the `ratings` and `reviews` tables respectively — they are not read from the RSS feed directly.

`total_films` shown in the UI is computed on-the-fly via `SELECT COUNT(*) FROM ratings WHERE profile_id = ?` — it is not stored in the `profiles` table.
