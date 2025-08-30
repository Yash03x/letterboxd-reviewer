#!/usr/bin/env python3
"""
Unified Letterboxd Profile Analyzer
Complete analysis system with local LLM support (Ollama/LM Studio) and OpenAI fallback
"""

import pandas as pd
import json
import os
import re
import requests
from typing import Dict, List, Optional
import numpy as np
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from textblob import TextBlob
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px

from config import settings, prompts

@dataclass
class ProfileData:
    """Structure to hold all profile data"""
    username: str
    profile_info: Dict
    ratings: pd.DataFrame
    reviews: pd.DataFrame
    watched: pd.DataFrame
    diary: pd.DataFrame
    watchlist: pd.DataFrame
    comments: pd.DataFrame
    lists: List[pd.DataFrame]
    likes: pd.DataFrame = None
    all_films: pd.DataFrame = None
    
    def __post_init__(self):
        """Process data after initialization"""
        self.total_movies = len(self.ratings)
        self.avg_rating = self.ratings['Rating'].mean() if not self.ratings.empty else 0
        self.total_reviews = len(self.reviews)


class LocalLLMInterface:
    """Interface for local LLM services (Ollama/LM Studio)"""
    
    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.lm_studio_url = settings.LM_STUDIO_URL
        self.available_service = self._detect_service()
    
    def _detect_service(self):
        """Detect which local LLM service is available"""
        # Try Ollama first
        try:
            response = requests.get(settings.OLLAMA_API_TAGS_URL, timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                if models:
                    print(f"✓ Ollama detected with {len(models)} models")
                    return 'ollama'
        except:
            pass
        
        # Try LM Studio
        try:
            response = requests.post(
                self.lm_studio_url,
                json={"messages": [{"role": "user", "content": "test"}], "max_tokens": 1},
                timeout=2
            )
            if response.status_code in [200, 400]:  # 400 might be expected for test message
                print("✓ LM Studio detected")
                return 'lm_studio'
        except:
            pass
        
        print("⚠️  No local LLM service detected")
        return None
    
    def generate_response(self, prompt: str, max_tokens: int = 1500) -> str:
        """Generate response using available local LLM"""
        if not self.available_service:
            return "Error: No local LLM service available"
        
        if self.available_service == 'ollama':
            return self._ollama_generate(prompt, max_tokens)
        elif self.available_service == 'lm_studio':
            return self._lm_studio_generate(prompt, max_tokens)
    
    def _ollama_generate(self, prompt: str, max_tokens: int) -> str:
        """Generate using Ollama"""
        try:
            payload = {
                "model": "deepseek-r1:32b",  # Using available model
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.8,  # More creative
                    "top_p": 0.9,
                    "top_k": 40,
                    "repeat_penalty": 1.1,
                    "presence_penalty": 0.1,
                    "frequency_penalty": 0.1
                }
            }
            
            response = requests.post(self.ollama_url, json=payload, timeout=240)  # Longer timeout for detailed analysis
            if response.status_code == 200:
                result = response.json().get('response', 'No response generated')
                return result.strip()
            else:
                return f"Ollama error: HTTP {response.status_code} - {response.text}"
        except Exception as e:
            return f"Ollama error: {str(e)}"
    
    def _lm_studio_generate(self, prompt: str, max_tokens: int) -> str:
        """Generate using LM Studio with improved error handling"""
        try:
            # System prompt optimized for qwen3-32b reasoning model
            system_prompt = """You are a film critic and analyst. When analyzing movie preferences, think through your analysis but then provide a clear, direct response. 

Format your response as:
Analysis: [your direct insights about the person's movie taste and personality]

Do not include thinking tags in your final response."""
            
            # Truncate very long prompts
            if len(prompt) > 3000:
                prompt = prompt[:3000] + "... [truncated for processing]"
            
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": min(max_tokens, 1500),  # Increased token limit
                "temperature": 0.7,
                "stream": False
                # Removed stop tokens to let the model complete its reasoning
            }
            
            # Increased timeout and retry logic
            for attempt in range(2):
                try:
                    timeout = 300 if attempt == 0 else 420  # Longer timeouts for 32B model
                    response = requests.post(self.lm_studio_url, json=payload, timeout=timeout)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'choices' in result and len(result['choices']) > 0:
                            content = result['choices'][0]['message']['content']
                            if content:
                                content = content.strip()
                                
                                # Extract the analysis part if it follows our format
                                if "Analysis:" in content:
                                    # Extract everything after "Analysis:"
                                    analysis_start = content.find("Analysis:") + 9
                                    content = content[analysis_start:].strip()
                                
                                # Clean up any remaining thinking artifacts
                                import re
                                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
                                content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL | re.IGNORECASE)
                                content = content.strip()
                                
                                return content if content else "Model completed but provided no analysis content"
                            else:
                                return "No response content generated"
                        else:
                            return "No response generated by LM Studio"
                    else:
                        if attempt == 0:  # Retry once
                            continue
                        return f"LM Studio error: HTTP {response.status_code} - {response.text[:200]}"
                        
                except requests.exceptions.Timeout:
                    if attempt == 0:
                        print(f"LM Studio timeout on attempt {attempt + 1}, retrying with longer timeout...")
                        continue
                    return "LM Studio timeout - the qwen3-32b model is very large and slow. Consider switching to the devstral-small-2505 model for faster responses."
                except requests.exceptions.ConnectionError:
                    return "Cannot connect to LM Studio. Make sure it's running on localhost:1234"
                    
        except Exception as e:
            return f"LM Studio error: {str(e)}"
    
    def test_connection(self) -> str:
        """Test local LLM connection with a simple prompt"""
        if not self.available_service:
            return "❌ No local LLM service detected"
        
        test_prompt = "Hello! Please respond with 'LLM is working' if you can process this message."
        
        try:
            response = self.generate_response(test_prompt, max_tokens=50)
            if "error" in response.lower():
                return f"❌ Error testing {self.available_service}: {response}"
            else:
                return f"✅ {self.available_service} is working: {response[:100]}..."
        except Exception as e:
            return f"❌ Test failed: {str(e)}"


# from core.recommendations import SimpleGenreBasedRecommendationEngine

class UnifiedLetterboxdAnalyzer:
    """Complete Letterboxd analyzer with all features"""
    
    def __init__(self, openai_api_key: Optional[str] = None, use_local_llm: bool = True):
        """Initialize analyzer with LLM options"""
        self.profiles = {}
        self.use_local_llm = use_local_llm
        self.local_llm = LocalLLMInterface() if use_local_llm else None
        self.openai_enabled = False
        # self.recommendation_engine = SimpleGenreBasedRecommendationEngine()
        
        if openai_api_key:
            try:
                import openai
                openai.api_key = openai_api_key
                self.openai_enabled = True
                print("✓ OpenAI API configured")
            except ImportError:
                print("⚠️  OpenAI package not available")
        
        self.llm_available = (self.local_llm and self.local_llm.available_service) or self.openai_enabled
        
        if not self.llm_available:
            print("⚠️  No LLM service available (local or OpenAI)")
    
    def load_profile(self, profile_path: str, username: str) -> ProfileData:
        """Load a Letterboxd profile from extracted data"""
        print(f"Loading profile for {username}...")
        
        try:
            # Load basic profile info
            profile_csv = os.path.join(profile_path, 'profile.csv')
            if os.path.exists(profile_csv):
                profile_df = pd.read_csv(profile_csv)
                profile_info = profile_df.iloc[0].to_dict()
            else:
                profile_info = {}

            # Load all CSV files - including likes data
            files_to_load = ['ratings', 'reviews', 'watched', 'diary', 'watchlist', 'comments', 'likes']
            data = {}

            for file_name in files_to_load:
                file_path = os.path.join(profile_path, f'{file_name}.csv')
                if os.path.exists(file_path):
                    try:
                        data[file_name] = pd.read_csv(file_path)
                        print(f"✓ Loaded {file_name}.csv: {len(data[file_name])} entries")
                    except Exception as e:
                        print(f"Error loading {file_name}.csv: {e}")
                        data[file_name] = pd.DataFrame()
                else:
                    print(f"Warning: {file_name}.csv not found for {username}")
                    data[file_name] = pd.DataFrame()
                    
            # Also check for films.csv or all_films.csv (comprehensive film data)
            comprehensive_files = ['films.csv', 'all_films.csv', 'films_comprehensive.csv']
            for comp_file in comprehensive_files:
                file_path = os.path.join(profile_path, comp_file)
                if os.path.exists(file_path):
                    try:
                        data['all_films'] = pd.read_csv(file_path)
                        print(f"✓ Loaded {comp_file}: {len(data['all_films'])} films")
                        break
                    except Exception as e:
                        print(f"Error loading {comp_file}: {e}")
            
            if 'all_films' not in data:
                data['all_films'] = pd.DataFrame()

            # Load lists from both lists.csv and lists/ directory
            lists = []
            
            # First check for lists.csv (summary file)
            lists_csv = os.path.join(profile_path, 'lists.csv')
            if os.path.exists(lists_csv):
                try:
                    lists_summary = pd.read_csv(lists_csv)
                    if not lists_summary.empty:
                        print(f"✓ Loaded lists.csv: {len(lists_summary)} lists")
                        # Store as a summary DataFrame
                        data['lists_summary'] = lists_summary
                except Exception as e:
                    print(f"Error loading lists.csv: {e}")
                    
            # Then check for individual list files in lists/ directory
            lists_dir = os.path.join(profile_path, 'lists')
            if os.path.exists(lists_dir):
                print(f"Loading individual lists from {lists_dir}/")
                for list_file in os.listdir(lists_dir):
                    if list_file.endswith('.csv'):
                        try:
                            list_df = pd.read_csv(os.path.join(lists_dir, list_file))
                            list_df['list_name'] = list_file.replace('.csv', '')
                            lists.append(list_df)
                            print(f"  ✓ Loaded {list_file}: {len(list_df)} items")
                        except Exception as e:
                            print(f"  Error loading {list_file}: {e}")

            profile = ProfileData(
                username=username,
                profile_info=profile_info,
                ratings=data['ratings'],
                reviews=data['reviews'],
                watched=data['watched'],
                diary=data['diary'],
                watchlist=data['watchlist'],
                comments=data['comments'],
                lists=lists,
                likes=data.get('likes', pd.DataFrame()),
                all_films=data.get('all_films', pd.DataFrame())
            )

            self.profiles[username] = profile
            print(f"✓ Loaded {username}: {profile.total_movies} rated movies, {profile.total_reviews} reviews")
            return profile

        except Exception as e:
            print(f"Error loading profile {username}: {e}")
            raise
    
    def extract_viewing_patterns(self, profile: ProfileData) -> Dict:
        """Extract comprehensive viewing patterns"""
        patterns = {}
        
        # Rating distribution and preferences
        if not profile.ratings.empty:
            rating_dist = profile.ratings['Rating'].value_counts().sort_index()
            patterns['rating_distribution'] = rating_dist.to_dict()
            patterns['avg_rating'] = profile.avg_rating
            patterns['rating_std'] = profile.ratings['Rating'].std()
            patterns['most_common_rating'] = rating_dist.idxmax()
            patterns['harsh_critic_ratio'] = (profile.ratings['Rating'] <= 2).sum() / len(profile.ratings)
            patterns['generous_rater_ratio'] = (profile.ratings['Rating'] >= 4).sum() / len(profile.ratings)
            patterns['extremes_ratio'] = ((profile.ratings['Rating'] <= 1) | (profile.ratings['Rating'] >= 4.5)).sum() / len(profile.ratings)
            
            # Top and bottom movies
            ratings_sorted = profile.ratings.copy()
            ratings_sorted['Rating'] = pd.to_numeric(ratings_sorted['Rating'], errors='coerce')
            
            high_rated = ratings_sorted[ratings_sorted['Rating'] >= 4.5]
            if not high_rated.empty:
                # Sort by rating descending
                sorted_indices = high_rated['Rating'].values.argsort()[::-1]
                top_rated = high_rated.iloc[sorted_indices].head(10)
            else:
                top_rated = pd.DataFrame()
                
            low_rated = ratings_sorted[ratings_sorted['Rating'] <= 2]
            if not low_rated.empty:
                # Sort by rating ascending for bottom movies
                sorted_indices = low_rated['Rating'].values.argsort()
                bottom_rated = low_rated.iloc[sorted_indices].head(10)
            else:
                bottom_rated = pd.DataFrame()
                
            patterns['top_rated_movies'] = top_rated[['Name', 'Year', 'Rating']].to_dict('records') if not top_rated.empty else []
            patterns['bottom_rated_movies'] = bottom_rated[['Name', 'Year', 'Rating']].to_dict('records') if not bottom_rated.empty else []
        
        # Review analysis
        if not profile.reviews.empty and 'Review' in profile.reviews.columns:
            reviews_text = profile.reviews['Review'].dropna()
            if not reviews_text.empty:
                # Sentiment analysis
                sentiments = [TextBlob(str(review)).sentiment.polarity for review in reviews_text]
                patterns['review_sentiment_avg'] = np.mean(sentiments)
                patterns['review_sentiment_std'] = np.std(sentiments)
                patterns['positive_reviews_ratio'] = sum(1 for s in sentiments if s > 0.1) / len(sentiments)
                
                # Review length analysis
                review_lengths = [len(str(review)) for review in reviews_text]
                patterns['avg_review_length'] = np.mean(review_lengths)
                patterns['review_engagement_score'] = min(1.0, np.mean(review_lengths) / 500)
        
        # Temporal patterns
        if not profile.diary.empty and 'Watched Date' in profile.diary.columns:
            diary_dates = pd.to_datetime(profile.diary['Watched Date'], errors='coerce').dropna()
            if not diary_dates.empty:
                patterns['viewing_span_days'] = (diary_dates.max() - diary_dates.min()).days
                patterns['total_diary_entries'] = len(diary_dates)
                if patterns['viewing_span_days'] > 0:
                    patterns['avg_movies_per_month'] = len(diary_dates) / (patterns['viewing_span_days'] / 30)
                
                # Day preferences
                day_counts = diary_dates.dt.day_name().value_counts()
                patterns['favorite_viewing_day'] = day_counts.idxmax()
                patterns['day_distribution'] = day_counts.to_dict()
                
                # Binge watching
                daily_counts = diary_dates.dt.date.value_counts()
                patterns['binge_sessions'] = (daily_counts > 1).sum()
                patterns['max_movies_one_day'] = daily_counts.max()
        
        return patterns
    
    def analyze_genre_preferences(self, profile: ProfileData) -> Dict:
        """Analyze genre preferences from movie titles"""
        genre_keywords = {
            'horror': ['horror', 'scary', 'nightmare', 'evil', 'dead', 'ghost', 'zombie', 'saw', 'exorcist', 'conjuring', 'hereditary', 'midsommar', 'thing', 'alien'],
            'comedy': ['comedy', 'funny', 'humor', 'silly', 'american pie', 'hangover', 'anchorman', 'step brothers', 'superbad', 'booksmart', 'snatch'],
            'action': ['action', 'fight', 'war', 'mission', 'combat', 'fast', 'furious', 'john wick', 'die hard', 'terminator', 'mad max', 'gladiator'],
            'drama': ['drama', 'life', 'story', 'emotion', 'family', 'goodfellas', 'godfather', 'schindler', 'forrest gump', 'parasite'],
            'romance': ['love', 'romance', 'wedding', 'romantic', 'before sunrise', 'la la land', 'eternal sunshine', 'portrait of a lady on fire'],
            'thriller': ['thriller', 'suspense', 'mystery', 'danger', 'se7en', 'silence of the lambs', 'zodiac', 'gone girl', 'prisoners'],
            'sci-fi': ['space', 'future', 'alien', 'star', 'mars', 'interstellar', 'matrix', 'blade runner', '2001', 'dune', 'arrival', 'ex machina'],
            'animated': ['animation', 'pixar', 'disney', 'gibli', 'spirited away', 'spider-verse', 'toy story', 'akira'],
            'superhero': ['batman', 'superman', 'spider-man', 'marvel', 'avengers', 'x-men', 'iron man', 'wonder woman', 'dark knight'],
            'crime': ['crime', 'gangster', 'mafia', 'detective', 'police', 'pulp fiction', 'goodfellas', 'godfather', 'departed', 'heat']
        }
        
        genre_scores = defaultdict(list)
        
        for _, movie in profile.ratings.iterrows():
            title = str(movie['Name']).lower()
            rating = movie['Rating']
            
            for genre, keywords in genre_keywords.items():
                if any(keyword in title for keyword in keywords):
                    genre_scores[genre].append(rating)
        
        # Calculate preferences
        genre_analysis = {}
        for genre, ratings in genre_scores.items():
            if ratings:
                genre_analysis[genre] = {
                    'avg_rating': np.mean(ratings),
                    'count': len(ratings),
                    'preference_score': np.mean(ratings) * np.log(len(ratings) + 1)  # Weight by frequency
                }
        
        return genre_analysis
    
    def generate_personality_profile(self, profile: ProfileData) -> Dict:
        """Generate personality insights from viewing data"""
        patterns = self.extract_viewing_patterns(profile)
        
        # Determine personality type based on rating patterns
        harsh_ratio = patterns.get('harsh_critic_ratio', 0)
        generous_ratio = patterns.get('generous_rater_ratio', 0)
        engagement = patterns.get('review_engagement_score', 0)
        
        if harsh_ratio > 0.25:
            personality_type = 'discerning_critic'
            description = "High standards and critical eye for quality"
        elif generous_ratio > 0.4:
            personality_type = 'enthusiastic_fan'  
            description = "Finds joy in most films, generous and positive viewer"
        elif engagement > 0.5:
            personality_type = 'thoughtful_reviewer'
            description = "Balanced viewer who enjoys analyzing and discussing films"
        else:
            personality_type = 'casual_viewer'
            description = "Balanced approach to film consumption and rating"
        
        return {
            'type': personality_type,
            'description': description,
            'traits': {},
            'viewing_style': {},
            'critical_approach': {}
        }
    
    def find_common_movies(self, profile1: ProfileData, profile2: ProfileData) -> List[Dict]:
        """Find and analyze common movies between profiles"""
        if profile1.ratings.empty or profile2.ratings.empty:
            return []
        
        # Merge on name and year
        common = pd.merge(
            profile1.ratings[['Name', 'Year', 'Rating']],
            profile2.ratings[['Name', 'Year', 'Rating']],
            on=['Name', 'Year'],
            suffixes=(f'_{profile1.username}', f'_{profile2.username}')
        )
        
        common_list = []
        for _, row in common.iterrows():
            rating1 = row[f'Rating_{profile1.username}']
            rating2 = row[f'Rating_{profile2.username}']
            common_list.append({
                'movie': row['Name'],
                'year': row['Year'],
                f'{profile1.username}_rating': rating1,
                f'{profile2.username}_rating': rating2,
                'difference': abs(rating1 - rating2),
                'both_loved': rating1 >= 4 and rating2 >= 4,
                'both_hated': rating1 <= 2 and rating2 <= 2,
                'disagreement': abs(rating1 - rating2) >= 2
            })
        
        return sorted(common_list, key=lambda x: x['difference'])
    
    def calculate_compatibility(self, profile1: ProfileData, profile2: ProfileData) -> Dict:
        """Calculate comprehensive compatibility metrics"""
        common_movies = self.find_common_movies(profile1, profile2)
        patterns1 = self.extract_viewing_patterns(profile1)
        patterns2 = self.extract_viewing_patterns(profile2)
        genres1 = self.analyze_genre_preferences(profile1)
        genres2 = self.analyze_genre_preferences(profile2)
        personality1 = self.generate_personality_profile(profile1)
        personality2 = self.generate_personality_profile(profile2)
        
        compatibility = {}
        
        # Rating agreement
        if common_movies:
            avg_difference = np.mean([m['difference'] for m in common_movies])
            agreement_score = max(0, (5 - avg_difference) / 5)
            both_loved = sum(1 for m in common_movies if m['both_loved'])
            both_hated = sum(1 for m in common_movies if m['both_hated'])
            major_disagreements = sum(1 for m in common_movies if m['disagreement'])
            
            compatibility['rating_agreement'] = {
                'score': agreement_score,
                'avg_difference': avg_difference,
                'both_loved_count': both_loved,
                'both_hated_count': both_hated,
                'major_disagreements': major_disagreements,
                'common_movies_count': len(common_movies)
            }
        else:
            compatibility['rating_agreement'] = {'score': 0, 'common_movies_count': 0}
        
        # Pattern similarity (simplified)
        pattern_similarity = 0.5  # Default moderate similarity
        if patterns1.get('rating_distribution') and patterns2.get('rating_distribution'):
            dist1 = patterns1['rating_distribution']
            dist2 = patterns2['rating_distribution']
            
            # Simple correlation approach
            common_ratings = set(dist1.keys()) & set(dist2.keys())
            if common_ratings:
                correlations = []
                for rating in common_ratings:
                    prop1 = dist1[rating] / sum(dist1.values())
                    prop2 = dist2[rating] / sum(dist2.values())
                    correlations.append(1 - abs(prop1 - prop2))
                pattern_similarity = np.mean(correlations) if correlations else 0.5
        
        compatibility['pattern_similarity'] = pattern_similarity
        
        # Genre compatibility
        common_genres = set(genres1.keys()) & set(genres2.keys())
        if common_genres:
            genre_agreements = []
            for genre in common_genres:
                diff = abs(genres1[genre]['avg_rating'] - genres2[genre]['avg_rating'])
                genre_agreements.append(max(0, (5 - diff) / 5))
            compatibility['genre_compatibility'] = np.mean(genre_agreements) if genre_agreements else 0
        else:
            compatibility['genre_compatibility'] = 0
        
        # Personality compatibility
        personality_match = 0.5  # Base score
        if personality1['type'] == personality2['type']:
            personality_match = 0.9
        elif ('critic' in personality1['type'] and 'critic' in personality2['type']) or \
             ('fan' in personality1['type'] and 'fan' in personality2['type']):
            personality_match = 0.7
        
        compatibility['personality_match'] = personality_match
        
        # Overall score
        weights = {
            'rating_agreement': 0.35,
            'pattern_similarity': 0.25,
            'genre_compatibility': 0.20,
            'personality_match': 0.20
        }
        
        overall = 0
        for metric, weight in weights.items():
            if metric in compatibility:
                if metric == 'rating_agreement':
                    overall += compatibility[metric]['score'] * weight
                else:
                    overall += compatibility[metric] * weight
        
        compatibility['overall_score'] = overall
        compatibility['recommendation'] = self._get_recommendation(overall)
        
        return compatibility

    def create_multi_profile_rating_chart(self, profiles):
        """Create rating distribution comparison chart for multiple profiles"""
        if not profiles:
            return None

        fig = go.Figure()
        colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd']

        for i, profile in enumerate(profiles):
            ratings = profile.ratings['Rating'].value_counts().sort_index()
            all_ratings = sorted(ratings.index)

            fig.add_trace(go.Bar(
                x=all_ratings,
                y=[ratings.get(r, 0) for r in all_ratings],
                name=profile.username,
                marker_color=colors[i % len(colors)],
                opacity=0.7
            ))

        fig.update_layout(
            title="Rating Distribution Comparison",
            xaxis_title="Rating",
            yaxis_title="Number of Movies",
            barmode='group',
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        return fig

    def create_rating_trend_chart(self, profiles):
        """Create rating trends over time"""
        fig = go.Figure()
        colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd']

        for i, profile in enumerate(profiles):
            if not profile.diary.empty and 'Date' in profile.diary.columns:
                diary_df = profile.diary.copy()
                diary_df['Date'] = pd.to_datetime(diary_df['Date'], errors='coerce')
                diary_df = diary_df.dropna(subset=['Date'])

                if not diary_df.empty and 'Rating' in diary_df.columns:
                    diary_df['Rating'] = pd.to_numeric(diary_df['Rating'], errors='coerce')
                    diary_df = diary_df.dropna(subset=['Rating'])

                    if not diary_df.empty:
                        # Calculate monthly averages
                        diary_df['YearMonth'] = diary_df['Date'].dt.to_period('M')
                        monthly_avg = diary_df.groupby('YearMonth')['Rating'].mean().reset_index()
                        monthly_avg['Date'] = monthly_avg['YearMonth'].dt.to_timestamp()

                        fig.add_trace(go.Scatter(
                            x=monthly_avg['Date'],
                            y=monthly_avg['Rating'],
                            mode='lines+markers',
                            name=profile.username,
                            line=dict(color=colors[i % len(colors)], width=3),
                            marker=dict(size=6)
                        ))

        fig.update_layout(
            title="Rating Trends Over Time (Monthly Averages)",
            xaxis_title="Date",
            yaxis_title="Average Rating",
            height=400,
            hovermode='x unified'
        )

        return fig

    def create_common_movies_chart(self, common_movies):
        """Create chart showing rating differences for common movies"""
        if not common_movies or len(common_movies) < 2:
            return None

        df = pd.DataFrame(common_movies[:20])  # Top 20

        # For 2 profiles, create scatter plot
        if len(df.columns) == 5:  # movie, year, rating1, rating2, difference
            fig = px.scatter(
                df,
                x=df.columns[2],  # First user's rating
                y=df.columns[3],  # Second user's rating
                hover_data=['movie', 'year'],
                title="Rating Comparison for Common Movies",
                labels={
                    df.columns[2]: f"{df.columns[2].replace('_rating', '')} Rating",
                    df.columns[3]: f"{df.columns[3].replace('_rating', '')} Rating"
                }
            )

            # Add diagonal line for perfect agreement
            fig.add_trace(go.Scatter(
                x=[0.5, 5],
                y=[0.5, 5],
                mode='lines',
                line=dict(dash='dash', color='red'),
                name='Perfect Agreement',
                showlegend=True
            ))

            fig.update_layout(height=500)
            return fig

        return None

    def get_advanced_statistics(self, profiles):
        """Get advanced statistical analysis for profiles"""
        stats_data = []
        for profile in profiles:
            if not profile.ratings.empty:
                ratings = pd.to_numeric(profile.ratings['Rating'], errors='coerce').dropna()

                # Calculate advanced metrics
                rating_std = ratings.std()
                rating_skew = stats.skew(ratings)
                rating_kurtosis = stats.kurtosis(ratings)
                rating_median = ratings.median()
                rating_mode = ratings.mode().iloc[0] if not ratings.mode().empty else 0

                # Rating distribution percentiles
                p25 = ratings.quantile(0.25)
                p75 = ratings.quantile(0.75)
                iqr = p75 - p25

                # Activity metrics
                total_reviews = len(profile.reviews)
                review_rate = (total_reviews / len(ratings) * 100) if len(ratings) > 0 else 0

                # Year span analysis
                if 'Year' in profile.ratings.columns:
                    years = pd.to_numeric(profile.ratings['Year'], errors='coerce').dropna()
                    year_span = years.max() - years.min() if len(years) > 0 else 0
                    avg_year = years.mean() if len(years) > 0 else 0
                else:
                    year_span = 0
                    avg_year = 0

                stats_data.append({
                    "👤 Username": profile.username,
                    "🎬 Total Movies": len(ratings),
                    "⭐ Avg Rating": f"{ratings.mean():.2f}",
                    "📊 Std Dev": f"{rating_std:.2f}",
                    "📈 Skewness": f"{rating_skew:.2f}",
                    "📉 Kurtosis": f"{rating_kurtosis:.2f}",
                    "🎯 Median": f"{rating_median:.1f}",
                    "🏆 Mode": f"{rating_mode:.1f}",
                    "📏 IQR": f"{iqr:.2f}",
                    "✍️ Review Rate": f"{review_rate:.1f}%",
                    "📅 Year Span": f"{int(year_span)}",
                    "🗓️ Avg Year": f"{int(avg_year)}"
                })

        return pd.DataFrame(stats_data)

    def get_enhanced_profile_metrics(self, profile):
        """Create enhanced metrics for a profile"""
        metrics = {}

        if not profile.ratings.empty:
            ratings = pd.to_numeric(profile.ratings['Rating'], errors='coerce').dropna()

            # Basic metrics
            metrics['total_movies'] = len(ratings)
            metrics['avg_rating'] = ratings.mean()
            metrics['median_rating'] = ratings.median()
            metrics['std_rating'] = ratings.std()

            # Advanced metrics
            metrics['rating_skew'] = stats.skew(ratings)
            metrics['rating_kurtosis'] = stats.kurtosis(ratings)

            # Rating distribution
            metrics['five_star_pct'] = (ratings == 5.0).sum() / len(ratings) * 100
            metrics['four_plus_pct'] = (ratings >= 4.0).sum() / len(ratings) * 100
            metrics['three_minus_pct'] = (ratings <= 3.0).sum() / len(ratings) * 100

            # Consistency metrics
            metrics['rating_variance'] = ratings.var()

            # Year analysis
            if 'Year' in profile.ratings.columns:
                years = pd.to_numeric(profile.ratings['Year'], errors='coerce').dropna()
                if len(years) > 0:
                    metrics['oldest_movie'] = int(years.min())
                    metrics['newest_movie'] = int(years.max())
                    metrics['avg_movie_year'] = years.mean()

        # Review metrics
        metrics['total_reviews'] = len(profile.reviews)
        metrics['review_rate'] = (metrics['total_reviews'] / metrics.get('total_movies', 1)) * 100

        return metrics

    def generate_safe_individual_analysis(self, profile):
        """Generate a safer version of individual analysis that handles missing data"""
        try:
            if not self.llm_available:
                return "LLM analysis not available"

            prompt = prompts.get_individual_analysis_prompt_safe(profile)

            # Use available LLM service
            if hasattr(self, 'local_llm') and self.local_llm and self.local_llm.available_service:
                return self.local_llm.generate_response(prompt, 2000)
            elif self.openai_enabled:
                try:
                    import openai
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",  # Use more reliable model
                        messages=[
                            {"role": "system", "content": "You are an expert film critic and personality analyst. Provide detailed, specific insights based on movie preferences."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=2000,
                        temperature=0.8
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    return f"OpenAI error: {str(e)}"
            else:
                return "No LLM service available"

        except Exception as e:
            return f"Error generating analysis: {str(e)}"
    def _get_recommendation(self, score: float) -> str:
        """Get recommendation based on compatibility score"""
        if score >= 0.8:
            return "Perfect movie night partners! You'll love watching and discussing films together."
        elif score >= 0.65:
            return "Great compatibility! You'll enjoy most movies together with interesting discussions."
        elif score >= 0.45:
            return "Good compatibility with some differences. Great for expanding each other's horizons."
        elif score >= 0.25:
            return "Different tastes but valuable perspectives. Perfect for challenging discussions."
        else:
            return "Very different tastes - fascinating to explore each other's favorites!"
    
    def llm_analyze_profiles(self, profile1: ProfileData, profile2: ProfileData) -> str:
        """Generate LLM analysis of the two profiles"""
        if not self.llm_available:
            return "LLM analysis not available"
        
        # Prepare comprehensive data for LLM
        patterns1 = self.extract_viewing_patterns(profile1)
        patterns2 = self.extract_viewing_patterns(profile2)
        genres1 = self.analyze_genre_preferences(profile1)
        genres2 = self.analyze_genre_preferences(profile2)
        personality1 = self.generate_personality_profile(profile1)
        personality2 = self.generate_personality_profile(profile2)
        common_movies = self.find_common_movies(profile1, profile2)
        compatibility = self.calculate_compatibility(profile1, profile2)
        
        # Get filtered recommendations for both users
        watched1 = self.get_watched_movies_set(profile1)
        watched2 = self.get_watched_movies_set(profile2)
        
        recs1 = self.get_similar_movies_recommendations(profile1, 4)
        recs2 = self.get_similar_movies_recommendations(profile2, 4)
        
        prompt = prompts.get_profile_analysis_prompt(
            profile1, profile2, patterns1, patterns2, genres1, genres2,
            personality1, personality2, recs1, recs2, common_movies, compatibility, watched1, watched2
        )

        # Use local LLM or OpenAI
        if self.local_llm and self.local_llm.available_service:
            print("🤖 Generating analysis with local LLM...")
            return self.local_llm.generate_response(prompt, 2000)
        elif self.openai_enabled:
            print("🤖 Generating analysis with OpenAI...")
            try:
                import openai
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert film critic and psychologist."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2000,
                    temperature=0.7
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"OpenAI error: {str(e)}"
        else:
            return "No LLM service available"
    
    def llm_analyze_individual_profile(self, profile: ProfileData) -> str:
        """Generate LLM analysis of a single profile"""
        if not self.llm_available:
            return "LLM analysis not available"
        
        patterns = self.extract_viewing_patterns(profile)
        genres = self.analyze_genre_preferences(profile)
        personality = self.generate_personality_profile(profile)
        detailed_prefs = self.analyze_detailed_preferences(profile)
        watched_movies = self.get_watched_movies_set(profile)
        watchlist = self.get_watchlist_movies(profile)
        recommendations = self.get_similar_movies_recommendations(profile, 6)
        
        # Get some specific movie examples
        top_rated = profile.ratings[profile.ratings['Rating'] >= 4.5].head(8) if not profile.ratings.empty else pd.DataFrame()
        low_rated = profile.ratings[profile.ratings['Rating'] <= 2.0].head(5) if not profile.ratings.empty else pd.DataFrame()
        recent_reviews = profile.reviews.head(5) if not profile.reviews.empty else pd.DataFrame()
        
        prompt = prompts.get_individual_analysis_prompt(
            profile, patterns, genres, personality, detailed_prefs,
            watched_movies, watchlist, recommendations, top_rated, low_rated, recent_reviews
        )

        # Use local LLM or OpenAI
        if self.local_llm and self.local_llm.available_service:
            print(f"🤖 Generating comprehensive analysis for {profile.username}...")
            return self.local_llm.generate_response(prompt, 3500)
        elif self.openai_enabled:
            print(f"🤖 Generating comprehensive analysis for {profile.username} with OpenAI...")
            try:
                import openai
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert film critic and psychologist specializing in deep personality analysis through cinematic preferences. Provide comprehensive, specific, and actionable insights."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=3500,
                    temperature=0.8
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"OpenAI error: {str(e)}"
        else:
            return "No LLM service available"
    
    def get_watched_movies_set(self, profile: ProfileData) -> set:
        """Get set of all movies the user has watched (from ratings, watched, and diary)"""
        watched_movies = set()
        
        # Add from ratings
        if not profile.ratings.empty:
            for _, row in profile.ratings.iterrows():
                watched_movies.add(f"{row['Name']} ({row['Year']})")
        
        # Add from watched list
        if not profile.watched.empty:
            for _, row in profile.watched.iterrows():
                watched_movies.add(f"{row['Name']} ({row['Year']})")
        
        # Add from diary
        if not profile.diary.empty:
            for _, row in profile.diary.iterrows():
                watched_movies.add(f"{row['Name']} ({row['Year']})")
        
        return watched_movies

    def get_watchlist_movies(self, profile: ProfileData) -> list:
        """Get user's watchlist for better recommendations"""
        watchlist = []
        
        # Handle both old and new watchlist format
        if hasattr(profile, 'watchlist') and not profile.watchlist.empty:
            for _, row in profile.watchlist.iterrows():
                title = row.get('Name', row.get('Title', 'Unknown'))
                year = row.get('Year', '')
                if year:
                    watchlist.append(f"{title} ({year})")
                else:
                    watchlist.append(title)
        return watchlist

    def analyze_detailed_preferences(self, profile: ProfileData) -> Dict:
        """Extract detailed preference analysis"""
        analysis = {}
        
        if profile.ratings.empty:
            return analysis
        
        ratings_df = profile.ratings.copy()
        ratings_df['Rating'] = pd.to_numeric(ratings_df['Rating'], errors='coerce')
        
        # Decade preferences
        if 'Year' in ratings_df.columns:
            ratings_df['Decade'] = (ratings_df['Year'] // 10) * 10
            decade_ratings = ratings_df.groupby('Decade')['Rating'].agg(['mean', 'count']).reset_index()
            decade_ratings = decade_ratings[decade_ratings['count'] >= 3]  # At least 3 movies
            analysis['decade_preferences'] = decade_ratings.sort_values('mean', ascending=False).head(3).to_dict('records')
        
        # Rating distribution insights
        rating_dist = ratings_df['Rating'].value_counts().sort_index()
        analysis['rating_distribution'] = rating_dist.to_dict()
        analysis['rating_variance'] = ratings_df['Rating'].var()
        analysis['most_common_rating'] = ratings_df['Rating'].mode().iloc[0] if not ratings_df['Rating'].mode().empty else 3.0
        
        # High and low rated analysis
        high_rated = ratings_df[ratings_df['Rating'] >= 4.5]
        low_rated = ratings_df[ratings_df['Rating'] <= 2.0]
        
        analysis['high_rated_count'] = len(high_rated)
        analysis['low_rated_count'] = len(low_rated)
        analysis['high_rated_percentage'] = len(high_rated) / len(ratings_df) * 100
        analysis['low_rated_percentage'] = len(low_rated) / len(ratings_df) * 100
        
        # Recent watching patterns (if diary available)
        if not profile.diary.empty:
            diary_df = profile.diary.copy()
            if 'Watched Date' in diary_df.columns:
                diary_df['Watched Date'] = pd.to_datetime(diary_df['Watched Date'], errors='coerce')
                recent_movies = diary_df.dropna(subset=['Watched Date']).tail(10)
                analysis['recent_watching_trend'] = recent_movies[['Name', 'Year', 'Watched Date']].to_dict('records')
        
        return analysis

    def get_similar_movies_recommendations(self, profile: ProfileData, count: int = 5) -> list:
        """Generate movie recommendations based on user's preferences, excluding already watched"""
        return self.recommendation_engine.recommend(profile, self, count)
