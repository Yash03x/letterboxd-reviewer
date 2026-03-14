#!/usr/bin/env python3
"""
Letterboxd Profile Scraper — RSS-based

Fetches data from Letterboxd's public RSS feed, which is not behind
Cloudflare's bot challenge. Produces the same CSV output as the HTML
scraper (scraper_html.py) so the rest of the pipeline is unchanged.

Covers:
- All diary entries with ratings, watch dates, liked/rewatch flags
- Review text (entries that have written reviews)
- Computed profile stats (film count, avg rating, review count)

Does NOT cover (blocked by Cloudflare on VPS):
- Watchlist
- Custom lists
- Profile bio / location / avatar

For local development or environments where HTML scraping works,
see scraper_html.py.
"""

import csv
import os
import re
import requests
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional



@dataclass
class ProfileInfo:
    username: str
    display_name: str = ""
    bio: str = ""
    location: str = ""
    website: str = ""
    join_date: Optional[str] = None
    avatar_url: str = ""
    total_films: int = 0
    total_reviews: int = 0
    total_lists: int = 0
    following_count: int = 0
    followers_count: int = 0
    favorite_films: List[Dict] = None

    def __post_init__(self):
        if self.favorite_films is None:
            self.favorite_films = []


class EnhancedLetterboxdScraper:
    def __init__(self, username: str, output_dir: Optional[str] = None, debug: bool = False):
        self.username = username
        self.output_dir = output_dir or f"{username}_data"
        self.debug = debug

        os.makedirs(self.output_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        })

        self.profile_info = ProfileInfo(username=username)
        self.films_data: List[Dict] = []
        self.diary_entries: List[Dict] = []
        self.reviews_data: List[Dict] = []
        self.watchlist_data: List[Dict] = []
        self.lists_data: List[Dict] = []

    # ------------------------------------------------------------------
    # RSS scraping
    # ------------------------------------------------------------------

    def _fetch_rss_page(self, page: int) -> Optional[ET.Element]:
        url = f"https://letterboxd.com/{self.username}/rss/?page={page}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            return root
        except Exception as e:
            if self.debug:
                print(f"RSS fetch failed (page {page}): {e}")
            return None

    def _parse_description(self, description: str):
        """Parse RSS description CDATA. Returns (poster_url, review_text)."""
        if not description:
            return '', ''
        soup = BeautifulSoup(description, 'html.parser')
        # Extract poster URL from first <img>
        poster_url = ''
        for img_p in soup.find_all('p'):
            img = img_p.find('img')
            if img:
                poster_url = img.get('src', '')
                img_p.decompose()
                break
        text = soup.get_text(separator='\n').strip()
        # Letterboxd auto-generates "Watched on <day> <month> <year>." — discard it
        if re.match(r'^Watched on \w', text):
            text = ''
        return poster_url, text

    def scrape_via_rss(self) -> None:
        """Paginate through the RSS feed and populate films/diary/reviews."""
        print(f"📡 Scraping via RSS for {self.username}...")

        films: List[Dict] = []
        diary: List[Dict] = []
        reviews: List[Dict] = []
        seen_slugs: set = set()

        page = 1
        while True:
            root = self._fetch_rss_page(page)
            if root is None:
                break

            channel = root.find('channel')
            if channel is None:
                break

            items = channel.findall('item')
            if not items:
                break

            for item in items:
                try:
                    title = item.findtext('{https://letterboxd.com}filmTitle') or ''
                    year_text = item.findtext('{https://letterboxd.com}filmYear')
                    year = int(year_text) if year_text else None
                    film_url = item.findtext('link') or ''
                    slug = film_url.rstrip('/').split('/')[-1] if film_url else ''

                    rating_text = item.findtext('{https://letterboxd.com}memberRating')
                    rating = float(rating_text) if rating_text else None

                    watch_date = item.findtext('{https://letterboxd.com}watchedDate') or ''
                    is_liked = item.findtext('{https://letterboxd.com}memberLike') == 'Yes'
                    is_rewatch = item.findtext('{https://letterboxd.com}rewatch') == 'Yes'
                    tmdb_id = item.findtext('{https://themoviedb.org}movieId') or ''
                    pub_date = item.findtext('pubDate') or ''

                    poster_url, review_text = self._parse_description(item.findtext('description') or '')
                    has_review = bool(review_text)

                    # Diary entry — every RSS item is a diary/log entry
                    diary.append({
                        'title': title,
                        'year': year,
                        'watch_date': watch_date,
                        'rating': rating,
                        'is_rewatch': is_rewatch,
                        'is_liked': is_liked,
                        'has_review': has_review,
                        'film_url': film_url,
                    })

                    # Films — deduplicate by slug (keep most-recent watch)
                    if slug not in seen_slugs:
                        seen_slugs.add(slug)
                        films.append({
                            'title': title,
                            'year': year,
                            'rating': rating,
                            'film_id': tmdb_id,
                            'slug': slug,
                            'poster_url': poster_url,
                            'film_url': film_url,
                            'is_liked': is_liked,
                            'has_review': has_review,
                            'movie_id': tmdb_id,
                        })

                    if has_review:
                        reviews.append({
                            'title': title,
                            'year': year,
                            'rating': rating,
                            'review_text': review_text,
                            'review_date': pub_date,
                            'review_likes': 0,
                            'film_url': film_url,
                        })

                except Exception as e:
                    if self.debug:
                        print(f"Error processing RSS item: {e}")
                    continue

            page += 1
            time.sleep(0.3)

        self.films_data = films
        self.diary_entries = diary
        self.reviews_data = reviews
        print(f"✓ RSS: {len(films)} unique films, {len(diary)} diary entries, {len(reviews)} reviews")

    # ------------------------------------------------------------------
    # CSV helpers
    # ------------------------------------------------------------------

    def _write_csv(self, filename: str, data: List[Dict], fieldnames: List[str]):
        if not data:
            return
        path = os.path.join(self.output_dir, filename)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    def _save_profile_info(self):
        data = [{
            'Username': self.profile_info.username,
            'Display_Name': self.profile_info.display_name,
            'Bio': self.profile_info.bio,
            'Location': self.profile_info.location,
            'Website': self.profile_info.website,
            'Join_Date': self.profile_info.join_date,
            'Avatar_URL': self.profile_info.avatar_url,
            'Total_Films': len(self.films_data),
            'Total_Reviews': len(self.reviews_data),
            'Total_Lists': 0,
            'Following_Count': 0,
            'Followers_Count': 0,
        }]
        self._write_csv('profile.csv', data, list(data[0].keys()))

    def _save_diary_entries(self):
        data = [{
            'Name': e['title'], 'Year': e['year'], 'Watched Date': e['watch_date'],
            'Rating': e['rating'],
            'Is_Rewatch': 'Yes' if e['is_rewatch'] else 'No',
            'Is_Liked': 'Yes' if e['is_liked'] else 'No',
            'Has_Review': 'Yes' if e['has_review'] else 'No',
            'Film_URL': e['film_url'],
        } for e in self.diary_entries]
        self._write_csv('diary.csv', data, ['Name', 'Year', 'Watched Date', 'Rating', 'Is_Rewatch', 'Is_Liked', 'Has_Review', 'Film_URL'])

    def _save_reviews(self):
        data = [{
            'Name': r['title'], 'Year': r['year'], 'Rating': r['rating'],
            'Review': r['review_text'], 'Review_Date': r['review_date'],
            'Review_Likes': r['review_likes'], 'Film_URL': r['film_url'],
        } for r in self.reviews_data]
        self._write_csv('reviews.csv', data, ['Name', 'Year', 'Rating', 'Review', 'Review_Date', 'Review_Likes', 'Film_URL'])

    def _save_enriched_ratings(self) -> int:
        """Build ratings.csv from film data + diary fallback."""
        diary_lookup = {f"{e['title']}_{e['year'] or 'no_year'}": e for e in self.diary_entries if e['title']}

        all_ratings = []
        for film in self.films_data:
            if not film['title']:
                continue
            rating = film['rating']
            if not rating:
                key = f"{film['title']}_{film['year'] or 'no_year'}"
                diary_entry = diary_lookup.get(key)
                if diary_entry:
                    rating = diary_entry['rating']
            if rating:
                all_ratings.append({'Name': film['title'], 'Year': film['year'] or '', 'Rating': rating})

        self._write_csv('ratings.csv', all_ratings, ['Name', 'Year', 'Rating'])
        return len(all_ratings)

    def _save_likes(self):
        likes = [
            {'Name': f['title'], 'Year': f['year'] or '', 'Date': ''}
            for f in self.films_data if f.get('is_liked')
        ]
        self._write_csv('likes.csv', likes, ['Name', 'Year', 'Date'])

    def _save_comprehensive_films(self):
        data = [{
            'Title': f.get('title', ''), 'Year': f.get('year', ''),
            'Rating': f.get('rating', ''), 'Film_ID': f.get('film_id', ''),
            'Slug': f.get('slug', ''), 'Poster_URL': f.get('poster_url', ''),
            'Film_URL': f.get('film_url', ''),
            'Has_Review': 'Yes' if f.get('has_review') else 'No',
            'Movie_ID': f.get('movie_id', ''),
        } for f in self.films_data]
        self._write_csv('films_comprehensive.csv', data, ['Title', 'Year', 'Rating', 'Film_ID', 'Slug', 'Poster_URL', 'Film_URL', 'Has_Review', 'Movie_ID'])

    def save_all_data(self):
        print(f"💾 Saving all data to {self.output_dir}...")
        self._save_profile_info()
        self._save_diary_entries()
        self._save_reviews()
        rated_count = self._save_enriched_ratings()
        self._save_likes()
        self._save_comprehensive_films()
        print(f"✅ All data saved to {self.output_dir}/")
        print(f"   - Profile info, Diary, Reviews, Ratings, Likes, and Comprehensive films.")
        print(f"📊 Data Summary:")
        print(f"   - Total films discovered: {len(self.films_data)}")
        print(f"   - Films with ratings: {rated_count}")
        print(f"   - Diary entries: {len(self.diary_entries)}")
        print(f"   - Reviews: {len(self.reviews_data)}")

    # ------------------------------------------------------------------
    # Public API (same as scraper_html.py)
    # ------------------------------------------------------------------

    def scrape_all(self):
        print(f"🎬 Starting RSS scrape for {self.username}")
        print("=" * 50)
        self.scrape_via_rss()
        self.save_all_data()
        print("=" * 50)
        print(f"🎉 Scrape completed for {self.username}!")
        return {
            'profile': asdict(self.profile_info),
            'diary_entries': self.diary_entries,
            'reviews': self.reviews_data,
            'watchlist': self.watchlist_data,
            'lists': self.lists_data,
        }


def validate_username(username: str) -> bool:
    return bool(username and re.match(r'^[a-zA-Z0-9_-]+$', username))


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Letterboxd RSS Scraper')
    parser.add_argument('username')
    parser.add_argument('-o', '--output', default=None)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    if not validate_username(args.username):
        print("Error: invalid username")
        sys.exit(1)

    scraper = EnhancedLetterboxdScraper(args.username, args.output, args.debug)
    try:
        scraper.scrape_all()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)


if __name__ == '__main__':
    main()
