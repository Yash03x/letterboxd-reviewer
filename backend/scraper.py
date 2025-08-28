#!/usr/bin/env python3
"""
Enhanced Letterboxd Profile Scraper

A comprehensive scraper for Letterboxd user profiles that extracts:
- Complete film data (ratings, reviews, watchlist, diary)
- Profile information and statistics
- Social connections and activity
- Custom lists and detailed metadata
- Advanced analytics and viewing patterns
"""

import requests
import csv
import json
import argparse
import time
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re
from dataclasses import dataclass, asdict


@dataclass
class ProfileInfo:
    """Profile information structure"""
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


@dataclass
class FilmEntry:
    """Enhanced film entry structure"""
    title: str
    year: Optional[int] = None
    rating: Optional[float] = None
    watch_date: Optional[str] = None
    review_text: str = ""
    is_rewatch: bool = False
    is_liked: bool = False
    tags: List[str] = None
    viewing_context: str = ""  # theater, home, etc.
    film_id: str = ""
    slug: str = ""
    poster_url: str = ""
    has_review: bool = False
    review_likes: int = 0
    lists_containing: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.lists_containing is None:
            self.lists_containing = []


class EnhancedLetterboxdScraper:
    def __init__(self, username: str, output_dir: Optional[str] = None, debug: bool = False):
        self.username = username
        self.output_dir = output_dir or f"{username}_data"
        self.debug = debug
        
        # Create output directory structure
        os.makedirs(self.output_dir, exist_ok=True)
        
        # URL structure for different sections
        self.urls = {
            'profile': f"https://letterboxd.com/{username}/",
            'films': f"https://letterboxd.com/{username}/films/",
            'diary': f"https://letterboxd.com/{username}/films/diary/",
            'reviews': f"https://letterboxd.com/{username}/films/reviews/",
            'watchlist': f"https://letterboxd.com/{username}/watchlist/",
            'lists': f"https://letterboxd.com/{username}/lists/",
            'following': f"https://letterboxd.com/{username}/following/",
            'followers': f"https://letterboxd.com/{username}/followers/",
            'stats': f"https://letterboxd.com/{username}/films/stats/",
        }
        
        # Session setup
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Data storage
        self.profile_info = ProfileInfo(username=username)
        self.films_data = []
        self.diary_entries = []
        self.reviews_data = []
        self.watchlist_data = []
        self.lists_data = []
        self.social_data = {
            'following': [],
            'followers': [],
            'activity': []
        }
        self.movies_seen = set()  # To track duplicates
    
    def fetch_with_retry(self, url: str, max_retries: int = 5) -> Optional[requests.Response]:
        """Fetch URL with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=15)
                
                # Handle rate limiting specifically
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 10  # Much longer wait for rate limiting
                    print(f"Rate limited (429) on attempt {attempt + 1} for {url}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                wait_time = (2 ** attempt) + 1  # Exponential backoff
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                
                if attempt < max_retries - 1:
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed to fetch {url} after {max_retries} attempts")
                    return None
    
    def scrape_profile_info(self) -> ProfileInfo:
        """Scrape basic profile information and statistics."""
        print(f"🔍 Scraping profile info for {self.username}...")
        
        response = self.fetch_with_retry(self.urls['profile'])
        if not response:
            return self.profile_info
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract profile information
        try:
            # Display name
            profile_name = soup.find('h1', class_='title-1')
            if profile_name:
                self.profile_info.display_name = profile_name.get_text().strip()
            
            # Bio
            bio_element = soup.find('div', class_='profile-text')
            if bio_element:
                self.profile_info.bio = bio_element.get_text().strip()
            
            # Location and website
            profile_metadata = soup.find('section', class_='profile-metadata')
            if profile_metadata:
                location = profile_metadata.find('span', class_='location')
                if location:
                    self.profile_info.location = location.get_text().strip()
                
                website = profile_metadata.find('a', class_='url')
                if website:
                    self.profile_info.website = website.get('href', '')
            
            # Avatar URL
            avatar = soup.find('img', class_='avatar')
            if avatar:
                self.profile_info.avatar_url = avatar.get('src', '')
            
            # Statistics from profile page
            stats = soup.find_all('a', class_='has-icon')
            for stat in stats:
                stat_text = stat.get_text().strip()
                if 'films' in stat_text.lower():
                    # Extract number from text like "1,234 films"
                    numbers = re.findall(r'[\d,]+', stat_text)
                    if numbers:
                        self.profile_info.total_films = int(numbers[0].replace(',', ''))
                elif 'reviews' in stat_text.lower():
                    numbers = re.findall(r'[\d,]+', stat_text)
                    if numbers:
                        self.profile_info.total_reviews = int(numbers[0].replace(',', ''))
                elif 'lists' in stat_text.lower():
                    numbers = re.findall(r'[\d,]+', stat_text)
                    if numbers:
                        self.profile_info.total_lists = int(numbers[0].replace(',', ''))
            
            # Favorite films (top 4)
            favorite_films = soup.find_all('li', class_='poster-container')[:4]
            for film in favorite_films:
                film_link = film.find('a')
                if film_link:
                    film_img = film.find('img')
                    if film_img:
                        self.profile_info.favorite_films.append({
                            'title': film_img.get('alt', ''),
                            'url': film_link.get('href', ''),
                            'poster': film_img.get('src', '')
                        })
            
        except Exception as e:
            print(f"Error scraping profile info: {e}")
        
        return self.profile_info
    
    def scrape_diary_entries(self) -> List[Dict]:
        """Scrape complete diary entries with watch dates."""
        print(f"📅 Scraping diary entries for {self.username}...")
        
        diary_entries = []
        page_num = 1
        
        while True:
            if page_num == 1:
                page_url = self.urls['diary']
            else:
                page_url = f"{self.urls['diary']}page/{page_num}/"
            
            response = self.fetch_with_retry(page_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find diary table rows (new structure)
            diary_table = soup.find('table', class_='diary-table')
            if not diary_table:
                break
                
            diary_rows = diary_table.find_all('tr', class_='diary-entry-row')
            
            if not diary_rows:
                break
            
            for row in diary_rows:
                try:
                    # Extract month and day
                    month_cell = row.find('td', class_='col-monthdate')
                    day_cell = row.find('td', class_='col-daydate')
                    
                    watch_date = ''
                    if month_cell and day_cell:
                        month_text = month_cell.get_text().strip()
                        day_text = day_cell.get_text().strip()
                        # Try to construct a date string
                        if month_text and day_text:
                            watch_date = f"{month_text} {day_text}"
                    
                    # Extract film info from production cell
                    production_cell = row.find('td', class_='col-production')
                    if not production_cell:
                        continue
                    
                    # Find film link and title
                    film_link = production_cell.find('a')
                    if not film_link:
                        continue
                    
                    title = film_link.get_text().strip()
                    href = film_link.get('href', '')
                    
                    # Extract year from release year cell
                    year_cell = row.find('td', class_='col-releaseyear')
                    year = None
                    if year_cell:
                        year_text = year_cell.get_text().strip()
                        if year_text.isdigit():
                            year = int(year_text)
                    
                    # Extract rating
                    rating_cell = row.find('td', class_='col-rating')
                    rating = None
                    if rating_cell:
                        rating_elem = rating_cell.find('span', class_='rating')
                        if rating_elem:
                            stars_text = rating_elem.get_text()
                            rating = self.convert_stars_to_rating(stars_text)
                    
                    # Check for rewatch
                    rewatch_cell = row.find('td', class_='col-rewatch')
                    is_rewatch = False
                    if rewatch_cell and 'icon-status-off' not in rewatch_cell.get('class', []):
                        is_rewatch = True
                    
                    # Check for like
                    like_cell = row.find('td', class_='col-like')
                    is_liked = False
                    if like_cell:
                        like_icon = like_cell.find('span', class_='icon-liked')
                        is_liked = like_icon is not None
                    
                    # Check for review
                    review_cell = row.find('td', class_='col-review')
                    has_review = False
                    if review_cell:
                        review_link = review_cell.find('a')
                        has_review = review_link is not None
                    
                    diary_entry = {
                        'title': title,
                        'year': year,
                        'watch_date': watch_date,
                        'rating': rating,
                        'is_rewatch': is_rewatch,
                        'is_liked': is_liked,
                        'has_review': has_review,
                        'film_url': href
                    }
                    
                    diary_entries.append(diary_entry)
                    
                except Exception as e:
                    if self.debug:
                        print(f"Error processing diary entry: {e}")
                    continue
            
            # Check for next page
            next_link = soup.find('a', class_='next')
            if not next_link:
                break
                
            page_num += 1
            time.sleep(1)  # Be respectful
        
        self.diary_entries = diary_entries
        print(f"✓ Found {len(diary_entries)} diary entries")
        return diary_entries
    
    def scrape_reviews(self) -> List[Dict]:
        """Scrape all reviews with full text content."""
        print(f"📝 Scraping reviews for {self.username}...")
        
        reviews = []
        page_num = 1
        
        while True:
            if page_num == 1:
                page_url = self.urls['reviews']
            else:
                page_url = f"{self.urls['reviews']}page/{page_num}/"
            
            response = self.fetch_with_retry(page_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find review articles (new structure)
            review_elements = soup.find_all('article', class_='production-viewing')
            
            if not review_elements:
                break
            
            for review_elem in review_elements:
                try:
                    # Film title and year
                    film_link = review_elem.find('h2').find('a') if review_elem.find('h2') else None
                    if not film_link:
                        continue
                    
                    title = film_link.get_text().strip()
                    href = film_link.get('href', '')
                    
                    # Extract year
                    year_match = re.search(r'/(\d{4})/', href)
                    year = int(year_match.group(1)) if year_match else None
                    
                    # Rating
                    rating_elem = review_elem.find('span', class_='rating')
                    rating = None
                    if rating_elem:
                        stars_text = rating_elem.get_text()
                        rating = self.convert_stars_to_rating(stars_text)
                    
                    # Review text
                    review_text_elem = review_elem.find('div', class_='body-text')
                    review_text = ""
                    if review_text_elem:
                        # Remove any nested elements and get clean text
                        for script in review_text_elem(["script", "style"]):
                            script.decompose()
                        review_text = review_text_elem.get_text().strip()
                    
                    # Review date
                    date_elem = review_elem.find('span', class_='date')
                    review_date = date_elem.get_text().strip() if date_elem else ""
                    
                    # Check for likes
                    likes_elem = review_elem.find('span', class_='like-link-target')
                    review_likes = 0
                    if likes_elem:
                        likes_text = likes_elem.get_text()
                        likes_match = re.search(r'(\d+)', likes_text)
                        if likes_match:
                            review_likes = int(likes_match.group(1))
                    
                    review_data = {
                        'title': title,
                        'year': year,
                        'rating': rating,
                        'review_text': review_text,
                        'review_date': review_date,
                        'review_likes': review_likes,
                        'film_url': href
                    }
                    
                    reviews.append(review_data)
                    
                except Exception as e:
                    if self.debug:
                        print(f"Error processing review: {e}")
                    continue
            
            # Check for next page
            next_link = soup.find('a', class_='next')
            if not next_link:
                break
                
            page_num += 1
            time.sleep(1)  # Be respectful
        
        self.reviews_data = reviews
        print(f"✓ Found {len(reviews)} reviews")
        return reviews
    
    def scrape_watchlist(self) -> List[Dict]:
        """Scrape complete watchlist."""
        print(f"📋 Scraping watchlist for {self.username}...")
        
        watchlist = []
        page_num = 1
        
        while True:
            if page_num == 1:
                page_url = self.urls['watchlist']
            else:
                page_url = f"{self.urls['watchlist']}page/{page_num}/"
            
            response = self.fetch_with_retry(page_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find film posters
            film_elements = soup.find_all('li', class_='poster-container')
            
            if not film_elements:
                break
            
            for film_elem in film_elements:
                try:
                    film_link = film_elem.find('a')
                    if not film_link:
                        continue
                    
                    # Get film info from poster
                    img = film_elem.find('img')
                    if not img:
                        continue
                    
                    title = img.get('alt', '').strip()
                    href = film_link.get('href', '')
                    poster_url = img.get('src', '')
                    
                    # Extract year from URL
                    year_match = re.search(r'/(\d{4})/', href)
                    year = int(year_match.group(1)) if year_match else None
                    
                    watchlist_item = {
                        'title': title,
                        'year': year,
                        'film_url': href,
                        'poster_url': poster_url
                    }
                    
                    watchlist.append(watchlist_item)
                    
                except Exception as e:
                    if self.debug:
                        print(f"Error processing watchlist item: {e}")
                    continue
            
            # Check for next page
            next_link = soup.find('a', class_='next')
            if not next_link:
                break
                
            page_num += 1
            time.sleep(1)  # Be respectful
        
        self.watchlist_data = watchlist
        print(f"✓ Found {len(watchlist)} watchlist items")
        return watchlist
    
    def scrape_custom_lists(self) -> List[Dict]:
        """Scrape user's custom lists."""
        print(f"📝 Scraping custom lists for {self.username}...")
        
        lists = []
        
        response = self.fetch_with_retry(self.urls['lists'])
        if not response:
            return lists
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find list elements
        list_elements = soup.find_all('section', class_='list-set')
        
        for list_elem in list_elements:
            try:
                # List title and URL
                title_elem = list_elem.find('h2', class_='title')
                if not title_elem:
                    continue
                
                list_link = title_elem.find('a')
                if not list_link:
                    continue
                
                list_title = list_link.get_text().strip()
                list_url = list_link.get('href', '')
                
                # List description
                desc_elem = list_elem.find('div', class_='body-text')
                description = desc_elem.get_text().strip() if desc_elem else ""
                
                # Film count
                count_elem = list_elem.find('span', class_='list-count')
                film_count = 0
                if count_elem:
                    count_text = count_elem.get_text()
                    count_match = re.search(r'(\d+)', count_text)
                    if count_match:
                        film_count = int(count_match.group(1))
                
                list_data = {
                    'title': list_title,
                    'description': description,
                    'film_count': film_count,
                    'url': list_url
                }
                
                lists.append(list_data)
                
            except Exception as e:
                if self.debug:
                    print(f"Error processing list: {e}")
                continue
        
        self.lists_data = lists
        print(f"✓ Found {len(lists)} custom lists")
        return lists
    
    def save_all_data(self):
        """Save all scraped data to CSV files in organized structure."""
        print(f"💾 Saving all data to {self.output_dir}...")
        
        # Save profile info
        profile_file = os.path.join(self.output_dir, "profile.csv")
        with open(profile_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Username', 'Display_Name', 'Bio', 'Location', 'Website', 'Join_Date',
                'Avatar_URL', 'Total_Films', 'Total_Reviews', 'Total_Lists',
                'Following_Count', 'Followers_Count'
            ])
            writer.writeheader()
            writer.writerow({
                'Username': self.profile_info.username,
                'Display_Name': self.profile_info.display_name,
                'Bio': self.profile_info.bio,
                'Location': self.profile_info.location,
                'Website': self.profile_info.website,
                'Join_Date': self.profile_info.join_date,
                'Avatar_URL': self.profile_info.avatar_url,
                'Total_Films': self.profile_info.total_films,
                'Total_Reviews': self.profile_info.total_reviews,
                'Total_Lists': self.profile_info.total_lists,
                'Following_Count': self.profile_info.following_count,
                'Followers_Count': self.profile_info.followers_count
            })
        
        # Save diary entries
        if self.diary_entries:
            diary_file = os.path.join(self.output_dir, "diary.csv")
            with open(diary_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Name', 'Year', 'Watched Date', 'Rating', 'Is_Rewatch', 'Is_Liked', 'Has_Review', 'Film_URL'
                ])
                writer.writeheader()
                for entry in self.diary_entries:
                    writer.writerow({
                        'Name': entry['title'],
                        'Year': entry['year'],
                        'Watched Date': entry['watch_date'],
                        'Rating': entry['rating'],
                        'Is_Rewatch': 'Yes' if entry['is_rewatch'] else 'No',
                        'Is_Liked': 'Yes' if entry['is_liked'] else 'No',
                        'Has_Review': 'Yes' if entry['has_review'] else 'No',
                        'Film_URL': entry['film_url']
                    })
        
        # Save reviews
        if self.reviews_data:
            reviews_file = os.path.join(self.output_dir, "reviews.csv")
            with open(reviews_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Name', 'Year', 'Rating', 'Review', 'Review_Date', 'Review_Likes', 'Film_URL'
                ])
                writer.writeheader()
                for review in self.reviews_data:
                    writer.writerow({
                        'Name': review['title'],
                        'Year': review['year'],
                        'Rating': review['rating'],
                        'Review': review['review_text'],
                        'Review_Date': review['review_date'],
                        'Review_Likes': review['review_likes'],
                        'Film_URL': review['film_url']
                    })
        
        # Save watchlist
        if self.watchlist_data:
            watchlist_file = os.path.join(self.output_dir, "watchlist.csv")
            with open(watchlist_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Name', 'Year', 'Film_URL', 'Poster_URL'
                ])
                writer.writeheader()
                for item in self.watchlist_data:
                    writer.writerow({
                        'Name': item['title'],
                        'Year': item['year'],
                        'Film_URL': item['film_url'],
                        'Poster_URL': item['poster_url']
                    })
        
        # Save lists info
        if self.lists_data:
            lists_file = os.path.join(self.output_dir, "lists.csv")
            with open(lists_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Title', 'Description', 'Film_Count', 'URL'
                ])
                writer.writeheader()
                for list_item in self.lists_data:
                    writer.writerow({
                        'Title': list_item['title'],
                        'Description': list_item['description'],
                        'Film_Count': list_item['film_count'],
                        'URL': list_item['url']
                    })
        
        # Create a ratings file with ONLY films that have actual ratings
        ratings_file = os.path.join(self.output_dir, "ratings.csv")
        all_ratings = []
        
        # UNIVERSAL SET: All films from /films/ pages
        # Ratings file: SUBSET containing only films with actual ratings
        # Diary and reviews are SUBSETS that provide additional metadata
        
        # Create lookup dictionaries for enrichment
        diary_lookup = {}
        for entry in self.diary_entries:
            if entry['title']:
                # Better key handling for films without years
                key = f"{entry['title']}_{entry['year'] or 'no_year'}"
                diary_lookup[key] = entry
        
        review_lookup = {}
        for review in self.reviews_data:
            if review['title']:
                key = f"{review['title']}_{review['year'] or 'no_year'}"
                review_lookup[key] = review
        
        # Start with films_data as the UNIVERSAL SET and enrich with diary/review data
        for film in self.films_data:
            if film['title']:
                key = f"{film['title']}_{film['year'] or 'no_year'}"
                
                # Start with film data
                rating_entry = {
                    'Name': film['title'],
                    'Year': film['year'] or '',
                    'Rating': film['rating'] or ''
                }
                
                # Enrich with diary data if available (diary has priority for ratings/dates)
                if key in diary_lookup:
                    diary_entry = diary_lookup[key]
                    if diary_entry['rating'] and not rating_entry['Rating']:
                        rating_entry['Rating'] = diary_entry['rating']
                
                # Enrich with review data if available
                if key in review_lookup:
                    review_entry = review_lookup[key]
                    if review_entry['rating'] and not rating_entry['Rating']:
                        rating_entry['Rating'] = review_entry['rating']
                
                # Only add to ratings.csv if the film actually has a rating
                if rating_entry['Rating'] and str(rating_entry['Rating']).strip():
                    all_ratings.append(rating_entry)
        
        if all_ratings:
            with open(ratings_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['Name', 'Year', 'Rating'])
                writer.writeheader()
                for rating in all_ratings:
                    writer.writerow(rating)
        
        # Create likes.csv file for films that are liked but not necessarily rated
        likes_file = os.path.join(self.output_dir, "likes.csv")
        all_likes = []
        
        # Extract likes from films_data
        for film in self.films_data:
            if film['title'] and film.get('is_liked', False):
                like_entry = {
                    'Name': film['title'],
                    'Year': film['year'] or '',
                    'Date': ''  # Likes don't typically have dates in basic film data
                }
                all_likes.append(like_entry)
        
        # Also check diary entries for additional likes
        for entry in self.diary_entries:
            if entry['title'] and entry.get('is_liked', False):
                # Avoid duplicates
                like_key = f"{entry['title']}_{entry['year'] or 'no_year'}"
                film_key = f"{film.get('title', '')}_{film.get('year', 'no_year') or 'no_year'}"
                
                # Only add if not already in likes from films_data
                if not any(like_key == f"{like['Name']}_{like['Year'] or 'no_year'}" for like in all_likes):
                    like_entry = {
                        'Name': entry['title'],
                        'Year': entry['year'] or '',
                        'Date': entry.get('watch_date', '')
                    }
                    all_likes.append(like_entry)
        
        if all_likes:
            with open(likes_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['Name', 'Year', 'Date'])
                writer.writeheader()
                for like in all_likes:
                    writer.writerow(like)
        
        # Save comprehensive films data with ALL metadata
        if self.films_data:
            films_file = os.path.join(self.output_dir, "films_comprehensive.csv")
            with open(films_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'Title', 'Year', 'Rating', 'Film_ID', 'Slug', 'Poster_URL', 
                    'Film_URL', 'Has_Review', 'Movie_ID'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for film in self.films_data:
                    writer.writerow({
                        'Title': film.get('title', ''),
                        'Year': film.get('year', ''),
                        'Rating': film.get('rating', ''),
                        'Film_ID': film.get('film_id', ''),
                        'Slug': film.get('slug', ''),
                        'Poster_URL': film.get('poster_url', ''),
                        'Film_URL': film.get('film_url', ''),
                        'Has_Review': 'Yes' if film.get('has_review') else 'No',
                        'Movie_ID': film.get('movie_id', '')
                    })
        
        print(f"✅ All data saved to {self.output_dir}/")
        print(f"   📋 Profile info: profile.csv")
        print(f"   🎬 All films: films_comprehensive.csv ({len(self.films_data)} films)")
        print(f"   📅 Diary entries: diary.csv ({len(self.diary_entries)} entries)")
        print(f"   📝 Reviews: reviews.csv ({len(self.reviews_data)} reviews)")
        print(f"   📋 Watchlist: watchlist.csv ({len(self.watchlist_data)} items)")
        print(f"   📚 Lists: lists.csv ({len(self.lists_data)} lists)")
        print(f"   ⭐ Ratings: ratings.csv ({len(all_ratings)} rated films - filtered from {len(self.films_data)} total films)")
        print(f"")
        print(f"📊 Data Summary:")
        print(f"   • Total films discovered: {len(self.films_data)}")
        print(f"   • Films with ratings: {len(all_ratings)}")
        print(f"   • Diary entries: {len(self.diary_entries)}")
        print(f"   • Reviews: {len(self.reviews_data)}")
    
    def scrape_all(self):
        """Main method to scrape all available data."""
        print(f"🎬 Starting comprehensive scrape for {self.username}")
        print("=" * 50)
        
        # Scrape all sections
        self.scrape_profile_info()
        self.scrape_diary_entries()
        self.scrape_reviews()
        self.scrape_watchlist()
        self.scrape_custom_lists()
        
        # Save all data
        self.save_all_data()
        
        print("=" * 50)
        print(f"🎉 Comprehensive scrape completed for {self.username}!")
        return {
            'profile': asdict(self.profile_info),
            'diary_entries': self.diary_entries,
            'reviews': self.reviews_data,
            'watchlist': self.watchlist_data,
            'lists': self.lists_data
        }
        
    def convert_stars_to_rating(self, stars_text: str) -> Optional[float]:
        """Convert star rating text to decimal value."""
        if not stars_text:
            return None
            
        # Count full stars and half stars
        full_stars = stars_text.count('★')
        half_stars = stars_text.count('½')
        
        rating = full_stars + (half_stars * 0.5)
        return rating if rating > 0 else None
    
    def extract_movie_data_legacy(self, movie_element) -> Optional[Dict]:
        """Extract movie data from a single movie tile element."""
        try:
            # Debug: Print the HTML structure to understand what we're working with
            if self.debug:
                print(f"DEBUG HTML: {movie_element}")
                print("=" * 80)
            
            # Get title from multiple possible sources
            title = None
            
            # Method 1: From img alt attribute
            title_element = movie_element.find('img')
            if title_element:
                title = title_element.get('alt', '').strip()
            
            # Method 2: From data attributes
            if not title:
                title = movie_element.get('data-film-name', '').strip()
            
            # Method 3: From film link (look for user-specific film URLs)
            if not title:
                film_links = movie_element.find_all('a')
                for link in film_links:
                    href = link.get('href', '')
                    if '/film/' in href:
                        import re
                        # Look for pattern like /username/film/movie-name/
                        title_match = re.search(r'/film/([^/]+)/?', href)
                        if title_match:
                            title = title_match.group(1).replace('-', ' ').title()
                            break
            
            # Method 4: From any text content
            if not title:
                try:
                    text_content = movie_element.get_text().strip()
                    if text_content and len(text_content) < 100:  # Reasonable title length
                        title = text_content
                except AttributeError:
                    pass
                
            if not title:
                if self.debug:
                    print("No title found, skipping element")
                return None
            
            # Extract year - Try multiple approaches
            year = None
            
            # Method 1: Look for year in data attributes (most reliable)
            react_component = movie_element.find('div', class_='react-component')
            if react_component:
                full_name = react_component.get('data-item-full-display-name', '')
                if full_name:
                    import re
                    year_match = re.search(r'\((\d{4})\)', full_name)
                    if year_match:
                        year = int(year_match.group(1))
                        if self.debug:
                            print(f"Found year in data attribute: {full_name} -> {year}")
            
            # Method 2: Look for year in poster URL or data attributes  
            if not year and title_element:
                poster_url = title_element.get('src', '') or title_element.get('data-src', '')
                if poster_url:
                    import re
                    year_match = re.search(r'/(\d{4})/', poster_url)
                    if year_match:
                        year = int(year_match.group(1))
            
            # Method 3: Look for year in film slug/URL
            if not year:
                # Look for any link that contains /film/
                film_links = movie_element.find_all('a', href=lambda x: x and '/film/' in x)
                for film_link in film_links:
                    href = film_link.get('href')
                    import re
                    # Letterboxd URLs often contain year: /film/movie-name-year/
                    year_match = re.search(r'/film/[^/]+-(\d{4})/?', href)
                    if year_match:
                        year = int(year_match.group(1))
                        break
                    # Also try without the dash requirement
                    year_match = re.search(r'/film/.*?(\d{4})/?', href)
                    if year_match:
                        year = int(year_match.group(1))
                        break
            
            # Method 4: Extract from title if in parentheses
            if not year and title:
                import re
                year_match = re.search(r'\((\d{4})\)', title)
                if year_match:
                    year = int(year_match.group(1))
                    # Remove year from title
                    title = re.sub(r'\s*\(\d{4}\)\s*', '', title).strip()
            
            # Extract rating (stars) - Look for the specific rating structure
            rating = None
            
            # Method 1: Look for span with rating class (most common)
            rating_element = movie_element.find('span', class_=lambda x: x and 'rating' in x)
            if rating_element:
                stars_text = rating_element.get_text()
                rating = self.convert_stars_to_rating(stars_text)
                if self.debug and rating:
                    print(f"Found rating in span: {stars_text} -> {rating}")
            
            # Method 2: Look for any element with rating class
            if not rating:
                rating_element = movie_element.find(class_=lambda x: x and 'rating' in x.lower())
                if rating_element:
                    stars_text = rating_element.get_text()
                    rating = self.convert_stars_to_rating(stars_text)
                    if self.debug and rating:
                        print(f"Found rating in element: {stars_text} -> {rating}")
            
            # Method 3: Look for stars in any text content
            if not rating:
                all_text = movie_element.get_text()
                if '★' in all_text or '☆' in all_text:
                    rating = self.convert_stars_to_rating(all_text)
                    if self.debug and rating:
                        print(f"Found rating in text: {all_text} -> {rating}")
            
            # Create unique identifier to avoid duplicates
            # Be more permissive with movies that don't have years to avoid false positives
            if year:
                movie_id = f"{title}_{year}"
            else:
                # For movies without years, make each one unique by adding position info
                import time
                movie_id = f"{title}_no_year_{int(time.time() * 1000000) % 1000000}"
            
            # Extract ALL possible metadata
            film_id = None
            slug = None
            poster_url = None
            film_link = None
            has_review = False
            full_display_name = None
            item_name = None
            details_endpoint = None
            cache_busting_key = None
            component_class = None
            empty_poster_src = None
            has_default_poster = None
            image_height = None
            image_width = None
            is_linked = None
            is_likeable = None
            is_rateable = None
            is_watchable = None
            request_poster_metadata = None
            show_menu = None
            target_link = None
            postered_identifier = None
            item_uid = None
            rating_class = None
            
            if react_component:
                # Basic film data
                film_id = react_component.get('data-film-id')
                slug = react_component.get('data-item-slug')
                poster_url = react_component.get('data-poster-url')
                film_link = react_component.get('data-item-link')
                full_display_name = react_component.get('data-item-full-display-name')
                item_name = react_component.get('data-item-name')
                target_link = react_component.get('data-target-link')
                
                # Technical metadata
                details_endpoint = react_component.get('data-details-endpoint')
                cache_busting_key = react_component.get('data-cache-busting-key')
                component_class = react_component.get('data-component-class')
                empty_poster_src = react_component.get('data-empty-poster-src')
                postered_identifier = react_component.get('data-postered-identifier')
                
                # Image dimensions
                image_height = react_component.get('data-image-height')
                image_width = react_component.get('data-image-width')
                
                # Boolean flags (convert to Yes/No)
                has_default_poster = react_component.get('data-has-default-poster') == 'true'
                is_linked = react_component.get('data-is-linked') == 'true'
                is_likeable = react_component.get('data-likeable') == 'true'
                is_rateable = react_component.get('data-rateable') == 'true'
                is_watchable = react_component.get('data-watchable') == 'true'
                request_poster_metadata = react_component.get('data-request-poster-metadata') == 'true'
                show_menu = react_component.get('data-show-menu') == 'true'
            
            # Check for review
            review_link = movie_element.find('a', class_='review-micro')
            has_review = review_link is not None
            
            # Extract viewing data
            viewing_data = movie_element.find('p', class_='poster-viewingdata')
            if viewing_data:
                item_uid = viewing_data.get('data-item-uid')
                
                # Get rating class for more detailed rating info
                rating_span = viewing_data.find('span', class_=lambda x: x and 'rating' in x)
                if rating_span:
                    rating_class = ' '.join(rating_span.get('class', []))
            
            if self.debug:
                print(f"EXTRACTED: Title='{title}', Year={year}, Rating={rating}")
                print(f"  Extra: ID={film_id}, Slug={slug}, HasReview={has_review}")
                print("-" * 40)
            
            return {
                'title': title,
                'year': year,
                'rating': rating,
                'id': movie_id,
                'film_id': film_id,
                'slug': slug,
                'poster_url': poster_url,
                'film_link': film_link,
                'has_review': has_review,
                'full_display_name': full_display_name,
                'item_name': item_name,
                'target_link': target_link,
                'details_endpoint': details_endpoint,
                'cache_busting_key': cache_busting_key,
                'component_class': component_class,
                'empty_poster_src': empty_poster_src,
                'postered_identifier': postered_identifier,
                'image_height': image_height,
                'image_width': image_width,
                'has_default_poster': has_default_poster,
                'is_linked': is_linked,
                'is_likeable': is_likeable,
                'is_rateable': is_rateable,
                'is_watchable': is_watchable,
                'request_poster_metadata': request_poster_metadata,
                'show_menu': show_menu,
                'item_uid': item_uid,
                'rating_class': rating_class
            }
            
        except Exception as e:
            print(f"Error extracting movie data: {e}")
            return None
    
    def get_page_movies(self, page_url: str) -> Tuple[List[Dict], bool]:
        """Fetch and parse movies from a single page."""
        movies = []
        has_next_page = False
        
        try:
            response = self.fetch_with_retry(page_url)
            if not response:
                return movies, has_next_page
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find movie containers based on the actual Letterboxd structure
            movie_containers = []
            
            # Method 1: Look for poster-viewingdata containers (these contain ratings and film links)
            poster_data_containers = soup.find_all('p', class_='poster-viewingdata')
            
            # For each poster-viewingdata, find its associated film poster
            for data_container in poster_data_containers:
                # Find the parent that contains both the poster and the data
                parent = data_container.parent
                if parent:
                    movie_containers.append(parent)
            
            # Method 2: If no viewingdata found, look for direct film links and their containers
            if not movie_containers:
                film_links = soup.find_all('a', href=lambda x: x and '/film/' in x)
                for link in film_links:
                    # Get the container that has both the link and potential poster
                    container = link.parent
                    while container and container.name in ['span', 'p', 'a']:
                        container = container.parent
                    if container and container not in movie_containers:
                        movie_containers.append(container)
            
            for container in movie_containers:
                movie_data = self.extract_movie_data(container)
                if movie_data:
                    if movie_data['id'] not in self.movies_seen:
                        movies.append(movie_data)
                        self.movies_seen.add(movie_data['id'])
                    # Note: We used to skip duplicates here, but now allow them for movies without years
            
            # Check for next page
            next_link = soup.find('a', class_='next') or soup.find('a', string='Next')
            has_next_page = next_link is not None
            
        except Exception as e:
            print(f"Error processing page {page_url}: {e}")
            
        return movies, has_next_page
    
    def fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Fetch URL with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                wait_time = (2 ** attempt) + 1  # Exponential backoff
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                
                if attempt < max_retries - 1:
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed to fetch {url} after {max_retries} attempts")
                    return None
    
    def extract_enhanced_movie_data(self, movie_element) -> Optional[Dict]:
        """Extract comprehensive movie data using enhanced methods."""
        try:
            # Get title from multiple possible sources
            title = None
            
            # Method 1: From img alt attribute
            title_element = movie_element.find('img')
            if title_element:
                title = title_element.get('alt', '').strip()
            
            # Method 2: From data attributes
            if not title:
                title = movie_element.get('data-film-name', '').strip()
            
            # Method 3: From film link
            if not title:
                film_links = movie_element.find_all('a')
                for link in film_links:
                    href = link.get('href', '')
                    if '/film/' in href:
                        import re
                        title_match = re.search(r'/film/([^/]+)/?', href)
                        if title_match:
                            title = title_match.group(1).replace('-', ' ').title()
                            break
                
            if not title:
                return None
            
            # Extract year - Multiple approaches
            year = None
            
            # Method 1: Look for year in data attributes
            react_component = movie_element.find('div', class_='react-component')
            if react_component:
                full_name = react_component.get('data-item-full-display-name', '')
                if full_name:
                    import re
                    year_match = re.search(r'\((\d{4})\)', full_name)
                    if year_match:
                        year = int(year_match.group(1))
            
            # Method 2: Look for year in film slug/URL
            if not year:
                film_links = movie_element.find_all('a', href=lambda x: x and '/film/' in x)
                for film_link in film_links:
                    href = film_link.get('href')
                    import re
                    year_match = re.search(r'/film/[^/]+-(\d{4})/?', href)
                    if year_match:
                        year = int(year_match.group(1))
                        break
            
            # Method 3: Extract from title if in parentheses
            if not year and title:
                import re
                year_match = re.search(r'\((\d{4})\)', title)
                if year_match:
                    year = int(year_match.group(1))
                    title = re.sub(r'\s*\(\d{4}\)\s*', '', title).strip()
            
            # Extract rating (comprehensive)
            rating = None
            rating_element = movie_element.find('span', class_=lambda x: x and 'rating' in x)
            if rating_element:
                stars_text = rating_element.get_text()
                rating = self.convert_stars_to_rating(stars_text)
            
            # Extract comprehensive metadata
            film_id = None
            slug = None
            poster_url = None
            film_link = None
            has_review = False
            
            if react_component:
                film_id = react_component.get('data-film-id')
                slug = react_component.get('data-item-slug') 
                poster_url = react_component.get('data-poster-url')
                film_link = react_component.get('data-item-link')
            
            # Check for review
            review_link = movie_element.find('a', class_='review-micro')
            has_review = review_link is not None
            
            # Create unique identifier
            if year:
                movie_id = f"{title}_{year}"
            else:
                import time
                movie_id = f"{title}_no_year_{int(time.time() * 1000000) % 1000000}"
            
            return {
                'title': title,
                'year': year,
                'rating': rating,
                'film_id': film_id,
                'slug': slug,
                'poster_url': poster_url,
                'film_url': film_link,
                'has_review': has_review,
                'movie_id': movie_id,
                'review_text': '',
                'is_rewatch': False,
                'is_liked': False,
                'watch_date': None
            }
            
        except Exception as e:
            if self.debug:
                print(f"Error extracting enhanced movie data: {e}")
            return None

    def scrape_all_films(self) -> List[Dict]:
        """Scrape all films from all pages using enhanced extraction."""
        print(f"🎬 Scraping all films for {self.username}...")
        
        all_films = []
        page_num = 1
        movies_seen = set()
        
        while True:
            # Construct page URL
            if page_num == 1:
                page_url = self.urls['films']
            else:
                page_url = f"{self.urls['films']}page/{page_num}/"
            
            response = self.fetch_with_retry(page_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Enhanced container detection
            movie_containers = []
            
            # Method 1: Look for poster-viewingdata containers
            poster_data_containers = soup.find_all('p', class_='poster-viewingdata')
            for data_container in poster_data_containers:
                parent = data_container.parent
                if parent:
                    movie_containers.append(parent)
            
            # Method 2: Fallback to grid items
            if not movie_containers:
                movie_containers = soup.find_all('li', class_='griditem')
            
            if not movie_containers:
                break
            
            page_films = []
            for container in movie_containers:
                movie_data = self.extract_enhanced_movie_data(container)
                if movie_data and movie_data['movie_id'] not in movies_seen:
                    page_films.append(movie_data)
                    movies_seen.add(movie_data['movie_id'])
            
            if page_films:
                all_films.extend(page_films)
                print(f"  Page {page_num}: {len(page_films)} films (Total: {len(all_films)})")
            else:
                print(f"  Page {page_num}: No films found")
                break
            
            # Check for next page
            next_link = soup.find('a', class_='next')
            if not next_link:
                break
                
            page_num += 1
            
            # Aggressive rate limiting
            if page_num <= 5:
                time.sleep(2)
            elif page_num <= 10:
                time.sleep(5)
            else:
                time.sleep(8)
        
        self.films_data = all_films
        print(f"✓ Found {len(all_films)} total films")
        return all_films
    
    def save_to_csv(self, movies: List[Dict]) -> None:
        """Save movies data to CSV file with ALL available fields."""
        try:
            with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
                # ALL possible fieldnames - always include everything
                fieldnames = [
                    'Title', 'Year', 'Rating', 'Film_ID', 'Slug', 'Poster_URL', 'Film_Link', 'Has_Review',
                    'Full_Display_Name', 'Item_Name', 'Target_Link', 'Details_Endpoint', 
                    'Cache_Busting_Key', 'Component_Class', 'Empty_Poster_Src', 'Postered_Identifier',
                    'Image_Height', 'Image_Width', 'Has_Default_Poster', 'Is_Linked', 'Is_Likeable',
                    'Is_Rateable', 'Is_Watchable', 'Request_Poster_Metadata', 'Show_Menu', 
                    'Item_UID', 'Rating_Class'
                ]
                    
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for movie in movies:
                    writer.writerow({
                        'Title': movie['title'],
                        'Year': movie['year'] if movie['year'] else '',
                        'Rating': movie['rating'] if movie['rating'] else '',
                        'Film_ID': movie.get('film_id', ''),
                        'Slug': movie.get('slug', ''),
                        'Poster_URL': movie.get('poster_url', ''),
                        'Film_Link': movie.get('film_link', ''),
                        'Has_Review': 'Yes' if movie.get('has_review') else 'No',
                        'Full_Display_Name': movie.get('full_display_name', ''),
                        'Item_Name': movie.get('item_name', ''),
                        'Target_Link': movie.get('target_link', ''),
                        'Details_Endpoint': movie.get('details_endpoint', ''),
                        'Cache_Busting_Key': movie.get('cache_busting_key', ''),
                        'Component_Class': movie.get('component_class', ''),
                        'Empty_Poster_Src': movie.get('empty_poster_src', ''),
                        'Postered_Identifier': movie.get('postered_identifier', ''),
                        'Image_Height': movie.get('image_height', ''),
                        'Image_Width': movie.get('image_width', ''),
                        'Has_Default_Poster': 'Yes' if movie.get('has_default_poster') else 'No',
                        'Is_Linked': 'Yes' if movie.get('is_linked') else 'No',
                        'Is_Likeable': 'Yes' if movie.get('is_likeable') else 'No',
                        'Is_Rateable': 'Yes' if movie.get('is_rateable') else 'No',
                        'Is_Watchable': 'Yes' if movie.get('is_watchable') else 'No',
                        'Request_Poster_Metadata': 'Yes' if movie.get('request_poster_metadata') else 'No',
                        'Show_Menu': 'Yes' if movie.get('show_menu') else 'No',
                        'Item_UID': movie.get('item_uid', ''),
                        'Rating_Class': movie.get('rating_class', '')
                    })
                    
            print(f"Successfully saved {len(movies)} movies to {self.output_file}")
            
        except Exception as e:
            print(f"Error saving to CSV: {e}")
    
    def run(self) -> None:
        """Main execution method."""
        movies = self.scrape_all_films()
        
        if movies:
            self.save_to_csv(movies)
        else:
            print("No movies were scraped. Please check the username and try again.")


def validate_username(username: str) -> bool:
    """Validate that the username is reasonable."""
    if not username:
        return False
    
    # Basic validation - letterboxd usernames are alphanumeric with some special chars
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False
        
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Enhanced Letterboxd Profile Scraper - Extract comprehensive profile data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python letterboxd_scraper.py username
  python letterboxd_scraper.py username -o username_data
  python letterboxd_scraper.py username --debug
  
Features:
  - Complete profile information and statistics
  - All rated films with enhanced metadata
  - Full diary entries with watch dates
  - Complete reviews with text content
  - Watchlist data
  - Custom lists information
  - Organized CSV export structure
        """
    )
    
    parser.add_argument('username', 
                       help='Letterboxd username (e.g., "username" for https://letterboxd.com/username/)')
    parser.add_argument('-o', '--output', 
                       default=None,
                       help='Output directory name (default: username_data)')
    parser.add_argument('--debug', 
                       action='store_true',
                       help='Enable debug output to see HTML structure')
    parser.add_argument('--profile-only', 
                       action='store_true',
                       help='Scrape only basic profile info (faster)')
    parser.add_argument('--no-reviews', 
                       action='store_true',
                       help='Skip scraping reviews (faster)')
    
    args = parser.parse_args()
    
    # Validate username
    if not validate_username(args.username):
        print("Error: Please provide a valid Letterboxd username")
        print("Username should contain only letters, numbers, underscores, and hyphens")
        print("Example: python letterboxd_scraper.py username")
        sys.exit(1)
    
    # Create and run enhanced scraper
    scraper = EnhancedLetterboxdScraper(args.username, args.output, args.debug)
    
    try:
        if args.profile_only:
            print("🎬 Running profile-only scrape...")
            scraper.scrape_profile_info()
            scraper.save_all_data()
        else:
            print("🎬 Running comprehensive scrape...")
            scraper.scrape_all()
            
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
