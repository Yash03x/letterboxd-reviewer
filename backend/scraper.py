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
    
    def scrape_all_films(self) -> List[Dict]:
        """Scrape all films from the user's films page."""
        print(f"🎬 Scraping all films for {self.username}...")
        
        films = []
        page_num = 1
        
        while True:
            if page_num == 1:
                page_url = self.urls['films']
            else:
                page_url = f"{self.urls['films']}page/{page_num}/"
            
            response = self.fetch_with_retry(page_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find film poster containers (using correct selector)
            # Films are in li.griditem elements, each containing a div.poster.film-poster
            film_elements = soup.find_all('li', class_='griditem')
            
            if not film_elements:
                break
            
            for film_elem in film_elements:
                try:
                    # Find the poster div within the griditem
                    poster_div = film_elem.find('div', class_='poster film-poster')
                    if not poster_div:
                        continue
                    
                    # Get film info from poster
                    img = poster_div.find('img')
                    if not img:
                        continue
                    
                    # Get the link from the react-component div
                    react_component = film_elem.find('div', class_='react-component')
                    if not react_component:
                        continue
                    
                    # Extract film data from data attributes
                    film_link = react_component.get('data-item-link', '')
                    if not film_link:
                        continue
                    
                    title = img.get('alt', '').strip()
                    href = film_link  # film_link is already the href string
                    poster_url = img.get('src', '')
                    
                    # Extract year from data-item-name attribute (e.g., "Weapons (2025)")
                    item_name = react_component.get('data-item-name', '')
                    year_match = re.search(r'\((\d{4})\)', item_name)
                    year = int(year_match.group(1)) if year_match else None
                    
                    # Extract film ID and slug from data attributes
                    film_id = react_component.get('data-film-id', '')
                    slug = react_component.get('data-item-slug', '')
                    
                    # Check for rating and review status in poster-viewingdata
                    rating = None
                    is_liked = False
                    has_review = False
                    
                    viewing_data = film_elem.find('p', class_='poster-viewingdata')
                    if viewing_data:
                        # Check for rating
                        rating_elem = viewing_data.find('span', class_='rating')
                        if rating_elem:
                            stars_text = rating_elem.get_text()
                            rating = self.convert_stars_to_rating(stars_text)
                        
                        # Check for like status
                        like_elem = viewing_data.find('span', class_='like')
                        is_liked = like_elem is not None
                        
                        # Check for review status
                        review_elem = viewing_data.find('a', class_='review-micro')
                        has_review = review_elem is not None
                    
                    film_data = {
                        'title': title,
                        'year': year,
                        'rating': rating,
                        'film_id': film_id,
                        'slug': slug,
                        'poster_url': poster_url,
                        'film_url': href,
                        'is_liked': is_liked,
                        'has_review': has_review,
                        'movie_id': film_id  # For compatibility
                    }
                    
                    films.append(film_data)
                    
                except Exception as e:
                    if self.debug:
                        print(f"Error processing film: {e}")
                    continue
            
            # Check for next page
            next_link = soup.find('a', class_='next')
            if not next_link:
                break
                
            page_num += 1
            time.sleep(1)  # Be respectful
        
        self.films_data = films
        print(f"✓ Found {len(films)} films")
        return films

    def scrape_diary_entries(self) -> List[Dict]:
        """Scrape complete diary entries with watch dates."""
        print(f"📅 Scraping diary entries for {self.username}...")
        
        diary_entries = []
        page_num = 1
        current_month = None
        current_year = None
        
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
                    # Extract month, year, and day from date cells
                    month_cell = row.find('td', class_='col-monthdate')
                    day_cell = row.find('td', class_='col-daydate')
                    
                    # Check if month_cell has month/year info (not empty)
                    month_link = month_cell.find('a', class_='month') if month_cell else None
                    year_link = month_cell.find('a', class_='year') if month_cell else None
                    day_link = day_cell.find('a', class_='daydate') if day_cell else None
                    
                    # Update current month/year if new month info is found
                    if month_link and year_link:
                        current_month = month_link.get_text().strip()
                        current_year = year_link.get_text().strip()
                    
                    # Create watch date using current month/year and day
                    watch_date = ''
                    if current_month and current_year and day_link:
                        day_text = day_link.get_text().strip()
                        if day_text:
                            watch_date = f"{current_month} {current_year} {day_text}"
                    
                    # Extract film info from production cell
                    production_cell = row.find('td', class_='col-production')
                    if not production_cell:
                        continue
                    
                    # Find react-component for film data
                    react_component = production_cell.find('div', class_='react-component')
                    if not react_component:
                        continue
                    
                    # Extract title and year from data attributes
                    item_name = react_component.get('data-item-name', '')
                    title = item_name.split(' (')[0] if ' (' in item_name else ''
                    href = react_component.get('data-item-link', '')
                    
                    # Extract year from data-item-name attribute (e.g., "Together (2025)")
                    year = None
                    if item_name:
                        year_match = re.search(r'\((\d{4})\)', item_name)
                        year = int(year_match.group(1)) if year_match else None
                    
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
                    # Film title and year from react-component data
                    react_component = review_elem.find('div', class_='react-component')
                    if not react_component:
                        continue
                    
                    title = react_component.get('data-item-name', '').split(' (')[0]  # Remove year from title
                    href = react_component.get('data-item-link', '')
                    
                    # Extract year from data-item-name attribute (e.g., "Together (2025)")
                    item_name = react_component.get('data-item-name', '')
                    year_match = re.search(r'\((\d{4})\)', item_name)
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
                    
                    # Review date from timestamp
                    date_elem = review_elem.find('time', class_='timestamp')
                    review_date = date_elem.get('datetime', '') if date_elem else ""
                    if not review_date:
                        # Fallback to text content
                        date_elem = review_elem.find('span', class_='date')
                        review_date = date_elem.get_text().strip() if date_elem else ""
                    
                    # Check for likes from data-count attribute
                    likes_elem = review_elem.find('p', class_='like-link-target')
                    review_likes = 0
                    if likes_elem:
                        likes_count = likes_elem.get('data-count', '0')
                        review_likes = int(likes_count) if likes_count.isdigit() else 0
                    
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
                    
                    # Extract year from data-item-name if available
                    react_component = film_elem.find('div', class_='react-component')
                    year = None
                    if react_component:
                        item_name = react_component.get('data-item-name', '')
                        year_match = re.search(r'\((\d{4})\)', item_name)
                        year = int(year_match.group(1)) if year_match else None
                    
                    # Fallback to URL extraction
                    if year is None:
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
    
    def _write_csv(self, file_path: str, data: List[Dict], fieldnames: List[str]):
        """Helper function to write data to a CSV file."""
        if not data:
            return
        
        full_path = os.path.join(self.output_dir, file_path)
        with open(full_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    def _save_profile_info(self):
        """Saves the main profile information."""
        fieldnames = [
            'Username', 'Display_Name', 'Bio', 'Location', 'Website', 'Join_Date',
            'Avatar_URL', 'Total_Films', 'Total_Reviews', 'Total_Lists',
            'Following_Count', 'Followers_Count'
        ]
        data = [{
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
        }]
        self._write_csv("profile.csv", data, fieldnames)

    def _save_diary_entries(self):
        """Saves diary entries."""
        fieldnames = ['Name', 'Year', 'Watched Date', 'Rating', 'Is_Rewatch', 'Is_Liked', 'Has_Review', 'Film_URL']
        data = [{
            'Name': entry['title'], 'Year': entry['year'], 'Watched Date': entry['watch_date'],
            'Rating': entry['rating'], 'Is_Rewatch': 'Yes' if entry['is_rewatch'] else 'No',
            'Is_Liked': 'Yes' if entry['is_liked'] else 'No', 'Has_Review': 'Yes' if entry['has_review'] else 'No',
            'Film_URL': entry['film_url']
        } for entry in self.diary_entries]
        self._write_csv("diary.csv", data, fieldnames)

    def _save_reviews(self):
        """Saves reviews."""
        fieldnames = ['Name', 'Year', 'Rating', 'Review', 'Review_Date', 'Review_Likes', 'Film_URL']
        data = [{
            'Name': review['title'], 'Year': review['year'], 'Rating': review['rating'],
            'Review': review['review_text'], 'Review_Date': review['review_date'],
            'Review_Likes': review['review_likes'], 'Film_URL': review['film_url']
        } for review in self.reviews_data]
        self._write_csv("reviews.csv", data, fieldnames)

    def _save_watchlist(self):
        """Saves the watchlist."""
        fieldnames = ['Name', 'Year', 'Film_URL', 'Poster_URL']
        data = [{
            'Name': item['title'], 'Year': item['year'], 'Film_URL': item['film_url'],
            'Poster_URL': item['poster_url']
        } for item in self.watchlist_data]
        self._write_csv("watchlist.csv", data, fieldnames)

    def _save_custom_lists(self):
        """Saves custom lists."""
        fieldnames = ['Title', 'Description', 'Film_Count', 'URL']
        data = [{
            'Title': li['title'], 'Description': li['description'],
            'Film_Count': li['film_count'], 'URL': li['url']
        } for li in self.lists_data]
        self._write_csv("lists.csv", data, fieldnames)

    def _save_enriched_ratings(self) -> int:
        """Enriches and saves the ratings file, returning the count of rated films."""
        diary_lookup = {f"{e['title']}_{e['year'] or 'no_year'}": e for e in self.diary_entries if e['title']}
        review_lookup = {f"{r['title']}_{r['year'] or 'no_year'}": r for r in self.reviews_data if r['title']}
        
        all_ratings = []
        for film in self.films_data:
            if not film['title']:
                continue

            key = f"{film['title']}_{film['year'] or 'no_year'}"
            rating_entry = {'Name': film['title'], 'Year': film['year'] or '', 'Rating': film['rating'] or ''}

            diary_entry = diary_lookup.get(key)
            if diary_entry and diary_entry['rating'] and not rating_entry['Rating']:
                rating_entry['Rating'] = diary_entry['rating']

            review_entry = review_lookup.get(key)
            if review_entry and review_entry['rating'] and not rating_entry['Rating']:
                rating_entry['Rating'] = review_entry['rating']

            if rating_entry['Rating'] and str(rating_entry['Rating']).strip():
                all_ratings.append(rating_entry)
        
        self._write_csv("ratings.csv", all_ratings, ['Name', 'Year', 'Rating'])
        return len(all_ratings)

    def _save_likes(self):
        """Saves liked films."""
        all_likes = []
        seen_likes = set()

        for film in self.films_data:
            if film['title'] and film.get('is_liked', False):
                like_key = f"{film['title']}_{film['year'] or 'no_year'}"
                if like_key not in seen_likes:
                    all_likes.append({'Name': film['title'], 'Year': film['year'] or '', 'Date': ''})
                    seen_likes.add(like_key)

        for entry in self.diary_entries:
            if entry['title'] and entry.get('is_liked', False):
                like_key = f"{entry['title']}_{entry['year'] or 'no_year'}"
                if like_key not in seen_likes:
                    all_likes.append({'Name': entry['title'], 'Year': entry['year'] or '', 'Date': entry.get('watch_date', '')})
                    seen_likes.add(like_key)
        
        self._write_csv("likes.csv", all_likes, ['Name', 'Year', 'Date'])

    def _save_comprehensive_films(self):
        """Saves the comprehensive film data."""
        fieldnames = ['Title', 'Year', 'Rating', 'Film_ID', 'Slug', 'Poster_URL', 'Film_URL', 'Has_Review', 'Movie_ID']
        data = [{
            'Title': film.get('title', ''), 'Year': film.get('year', ''), 'Rating': film.get('rating', ''),
            'Film_ID': film.get('film_id', ''), 'Slug': film.get('slug', ''),
            'Poster_URL': film.get('poster_url', ''), 'Film_URL': film.get('film_url', ''),
            'Has_Review': 'Yes' if film.get('has_review') else 'No', 'Movie_ID': film.get('movie_id', '')
        } for film in self.films_data]
        self._write_csv("films_comprehensive.csv", data, fieldnames)

    def save_all_data(self):
        """Save all scraped data to CSV files in an organized structure."""
        print(f"💾 Saving all data to {self.output_dir}...")
        
        self._save_profile_info()
        self._save_diary_entries()
        self._save_reviews()
        self._save_watchlist()
        self._save_custom_lists()
        rated_films_count = self._save_enriched_ratings()
        self._save_likes()
        self._save_comprehensive_films()
        
        print(f"✅ All data saved to {self.output_dir}/")
        print(f"   - Profile info, Diary, Reviews, Watchlist, Lists, Ratings, Likes, and Comprehensive films.")
        print(f"📊 Data Summary:")
        print(f"   - Total films discovered: {len(self.films_data)}")
        print(f"   - Films with ratings: {rated_films_count}")
        print(f"   - Diary entries: {len(self.diary_entries)}")
        print(f"   - Reviews: {len(self.reviews_data)}")
    
    def scrape_all(self):
        """Main method to scrape all available data."""
        print(f"🎬 Starting comprehensive scrape for {self.username}")
        print("=" * 50)
        
        # Scrape all sections
        self.scrape_profile_info()
        self.scrape_all_films()  # Add this line to scrape films
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
