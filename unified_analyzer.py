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
    
    def __post_init__(self):
        """Process data after initialization"""
        self.total_movies = len(self.ratings)
        self.avg_rating = self.ratings['Rating'].mean() if not self.ratings.empty else 0
        self.total_reviews = len(self.reviews)
        self.join_date = pd.to_datetime(self.profile_info.get('Date Joined', '')) if self.profile_info.get('Date Joined') else None


class LocalLLMInterface:
    """Interface for local LLM services (Ollama/LM Studio)"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.lm_studio_url = "http://localhost:1234/v1/chat/completions"
        self.available_service = self._detect_service()
    
    def _detect_service(self):
        """Detect which local LLM service is available"""
        # Try Ollama first
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
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
                "model": "llama3.2:latest",
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


class UnifiedLetterboxdAnalyzer:
    """Complete Letterboxd analyzer with all features"""
    
    def __init__(self, openai_api_key: Optional[str] = None, use_local_llm: bool = True):
        """Initialize analyzer with LLM options"""
        self.profiles = {}
        self.use_local_llm = use_local_llm
        self.local_llm = LocalLLMInterface() if use_local_llm else None
        self.openai_enabled = False
        
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
        
        # Load basic profile info
        profile_csv = os.path.join(profile_path, 'profile.csv')
        if os.path.exists(profile_csv):
            profile_df = pd.read_csv(profile_csv)
            profile_info = profile_df.iloc[0].to_dict()
        else:
            profile_info = {}
        
        # Load all CSV files
        files_to_load = ['ratings', 'reviews', 'watched', 'diary', 'watchlist', 'comments']
        data = {}
        
        for file_name in files_to_load:
            file_path = os.path.join(profile_path, f'{file_name}.csv')
            data[file_name] = pd.read_csv(file_path) if os.path.exists(file_path) else pd.DataFrame()
        
        # Load lists
        lists_dir = os.path.join(profile_path, 'lists')
        lists = []
        if os.path.exists(lists_dir):
            for list_file in os.listdir(lists_dir):
                if list_file.endswith('.csv'):
                    list_df = pd.read_csv(os.path.join(lists_dir, list_file))
                    list_df['list_name'] = list_file.replace('.csv', '')
                    lists.append(list_df)
        
        profile = ProfileData(
            username=username,
            profile_info=profile_info,
            ratings=data['ratings'],
            reviews=data['reviews'],
            watched=data['watched'],
            diary=data['diary'],
            watchlist=data['watchlist'],
            comments=data['comments'],
            lists=lists
        )
        
        self.profiles[username] = profile
        print(f"✓ Loaded {username}: {profile.total_movies} rated movies, {profile.total_reviews} reviews")
        return profile
    
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
            'horror': ['horror', 'scary', 'nightmare', 'evil', 'dead', 'ghost', 'zombie', 'saw'],
            'comedy': ['comedy', 'funny', 'humor', 'silly', 'american pie', 'hangover'],
            'action': ['action', 'fight', 'war', 'mission', 'combat', 'fast', 'furious', 'john wick'],
            'drama': ['drama', 'life', 'story', 'emotion', 'family'],
            'romance': ['love', 'romance', 'wedding', 'romantic'],
            'thriller': ['thriller', 'suspense', 'mystery', 'danger'],
            'sci-fi': ['space', 'future', 'alien', 'star', 'mars', 'interstellar', 'matrix'],
            'animated': ['animation', 'pixar', 'disney'],
            'superhero': ['batman', 'superman', 'spider', 'marvel', 'avengers'],
            'crime': ['crime', 'gangster', 'mafia', 'detective', 'police']
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
        combined_watched = watched1.union(watched2)
        
        recs1 = self.get_similar_movies_recommendations(profile1, 4)
        recs2 = self.get_similar_movies_recommendations(profile2, 4)
        
        # Filter recommendations to exclude movies either user has seen
        filtered_recs1 = [movie for movie in recs1 if movie not in combined_watched]
        filtered_recs2 = [movie for movie in recs2 if movie not in combined_watched]
        
        prompt = f"""You are an expert film critic and psychologist analyzing two Letterboxd users. Provide a comprehensive, well-structured analysis of their movie taste compatibility.

## 🎬 USER PROFILES

**{profile1.username}:**
• {profile1.total_movies} movies rated (avg: {profile1.avg_rating:.2f}★) | {len(watched1)} total watched
• Personality: {personality1.get('type', 'unknown')} - {personality1.get('description', 'N/A')}
• Top genres: {', '.join([f"{g} ({d['avg_rating']:.1f}★)" for g, d in sorted(genres1.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:3]])}
• Rating style: {patterns1.get('harsh_critic_ratio', 0):.1%} harsh, {patterns1.get('generous_rater_ratio', 0):.1%} generous

**{profile2.username}:**
• {profile2.total_movies} movies rated (avg: {profile2.avg_rating:.2f}★) | {len(watched2)} total watched
• Personality: {personality2.get('type', 'unknown')} - {personality2.get('description', 'N/A')}
• Top genres: {', '.join([f"{g} ({d['avg_rating']:.1f}★)" for g, d in sorted(genres2.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:3]])}
• Rating style: {patterns2.get('harsh_critic_ratio', 0):.1%} harsh, {patterns2.get('generous_rater_ratio', 0):.1%} generous

## 📊 COMPATIBILITY METRICS
• **Overlap**: {len(common_movies)} movies both have watched
• **Overall compatibility**: {compatibility.get('overall_score', 0):.1%}
• **Rating agreement**: Avg difference {compatibility.get('rating_agreement', {}).get('avg_difference', 'N/A')}
• **Shared loves**: {compatibility.get('rating_agreement', {}).get('both_loved_count', 0)} movies both rated 4+★
• **Major disagreements**: {compatibility.get('rating_agreement', {}).get('major_disagreements', 0)} movies

## 🎯 UNWATCHED RECOMMENDATIONS
**For {profile1.username} (based on their tastes):**
{chr(10).join([f"• {movie}" for movie in filtered_recs1[:4]]) if filtered_recs1 else "• Custom recommendations needed"}

**For {profile2.username} (based on their tastes):**
{chr(10).join([f"• {movie}" for movie in filtered_recs2[:4]]) if filtered_recs2 else "• Custom recommendations needed"}

## 🔍 COMPREHENSIVE ANALYSIS FRAMEWORK

Provide detailed analysis in these sections:

### 🧠 **DEEP PERSONALITY INSIGHTS**
- How do their core personalities complement or clash based on movie preferences?
- What do their different rating styles reveal about their approaches to criticism and life?
- How do their preferred genres reflect their values, emotional needs, and worldviews?

### 🎭 **TASTE COMPATIBILITY ANALYSIS**
- Where do they align cinematically and why? What creates harmony?
- What are their key differences and how might these create interesting tensions?
- How do their preferences for mainstream vs. art house films compare?

### 💬 **DISCUSSION & DEBATE DYNAMICS**
- What film topics would generate passionate discussions between them?
- Where would they find common ground vs. respectful disagreement?
- How would their different critical approaches lead to interesting conversations?

### 🎬 **JOINT VIEWING PREDICTIONS**
- How would their movie nights play out? Who would typically choose?
- What compromises would they need to make for enjoyable shared viewing?
- What genres or types of films would work best for both?

### 📝 **BRIDGE RECOMMENDATIONS**
- Analyze the provided recommendations and suggest 3-4 additional specific unwatched films that would appeal to BOTH users
- Explain exactly WHY each recommendation bridges their different tastes
- Consider films that challenge both users while staying within their comfort zones

### 🔮 **RELATIONSHIP COMPATIBILITY FORECAST**
- How could their different film perspectives strengthen their relationship long-term?
- What blind spots could each help the other overcome in their cinematic journey?
- How would they influence each other's taste evolution over time?

### 💡 **ACTIONABLE INSIGHTS**
- Specific strategies for successful movie discussions and choices
- How to leverage their differences for mutual growth and discovery
- Warning signs of potential film-related conflicts and how to avoid them

Use specific examples from their actual viewing data. Be detailed, insightful, and practical in your analysis."""

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
        
        prompt = f"""Analyze this Letterboxd user's cinematic personality with deep psychological insights and detailed recommendations.

## 🎬 COMPREHENSIVE USER PROFILE: {profile.username}

### 📊 CORE STATISTICS
• **Total movies rated:** {profile.total_movies} | **Average rating:** {profile.avg_rating:.2f}★
• **Total reviews:** {profile.total_reviews} | **Join date:** {profile.join_date.strftime('%B %Y') if profile.join_date else 'Unknown'}
• **Movies watched:** {len(watched_movies)} total entries
• **Watchlist items:** {len(watchlist)} movies queued

### 🎭 PERSONALITY & PSYCHOLOGY
• **Type:** {personality.get('type', 'Unknown')}
• **Core traits:** {personality.get('description', 'N/A')}

### 🎯 DETAILED RATING PATTERNS
• **Rating variance:** {detailed_prefs.get('rating_variance', 0):.2f} (consistency measure)
• **Most common rating:** {detailed_prefs.get('most_common_rating', 3.0)}★
• **High ratings (4.5+):** {detailed_prefs.get('high_rated_percentage', 0):.1f}% of all movies
• **Low ratings (≤2.0):** {detailed_prefs.get('low_rated_percentage', 0):.1f}% of all movies
• **Harsh critic ratio:** {patterns.get('harsh_critic_ratio', 0):.1%}
• **Generous rater ratio:** {patterns.get('generous_rater_ratio', 0):.1%}

### 🎬 GENRE DEEP DIVE
**Top 5 Genre Preferences:**
{chr(10).join([f"• **{g}**: {d['avg_rating']:.1f}★ avg • {d['movie_count']} films • {d['preference_score']:.1f} preference score" for g, d in sorted(genres.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:5]])}

### ⭐ MOVIE TASTE ANALYSIS
**ABSOLUTE FAVORITES (4.5-5★):**
{chr(10).join([f"• {row['Name']} ({row['Year']}) - {row['Rating']}★" for _, row in top_rated.iterrows()]) if not top_rated.empty else '• No 5-star ratings found'}

**STRONG DISLIKES (≤2★):**
{chr(10).join([f"• {row['Name']} ({row['Year']}) - {row['Rating']}★" for _, row in low_rated.iterrows()]) if not low_rated.empty else '• No strong dislikes recorded'}

### 📝 RECENT ACTIVITY
{f"**Watchlist preview:** {', '.join(watchlist[:5])}" if watchlist else "**Watchlist:** Empty or not available"}
{f"**Recent reviews:** {len(recent_reviews)} written" if not recent_reviews.empty else "**Recent reviews:** None available"}

### 🎯 FILTERED RECOMMENDATIONS (UNWATCHED FILMS)
**Curated for {profile.username}:**
{chr(10).join([f"• {movie}" for movie in recommendations]) if recommendations else '• Analysis-based recommendations available'}

## � COMPREHENSIVE ANALYSIS REQUEST

Provide an in-depth psychological and cinematic analysis covering:

### 🧠 **DEEP PERSONALITY INSIGHTS**
- What do their specific movie preferences reveal about their worldview, emotional needs, and life philosophy?
- How do their rating patterns reflect their personality traits and critical thinking style?
- What psychological themes do they gravitate toward in cinema?

### � **AESTHETIC & NARRATIVE PREFERENCES**
- What visual styles, storytelling approaches, and thematic elements do they prefer?
- How sophisticated vs. accessible are their tastes? Art house vs. mainstream balance?
- What does their genre distribution reveal about their emotional and intellectual needs?

### � **CRITICAL ANALYSIS STYLE**
- How do their rating patterns compare to typical users? Are they harsh, generous, or balanced?
- What does their rating variance suggest about their critical consistency?
- How do they use the full rating scale? What does their most common rating reveal?

### 💭 **EMOTIONAL & INTELLECTUAL PROFILE**
- What emotions do they seek from cinema? Escapism, catharsis, intellectual stimulation, nostalgia?
- How do they balance entertainment vs. artistic merit in their choices?
- What life experiences might their preferences reflect?

### 🎬 **SPECIFIC RECOMMENDATIONS & REASONING**
- Analyze the provided unwatched recommendations and explain WHY each would appeal to them
- Suggest 3-4 additional specific films (that they haven't seen) with detailed reasoning
- Consider their watchlist and explain what patterns you see in their planned viewing

### 🔮 **LIFESTYLE & RELATIONSHIP INSIGHTS**
- What might their cinema habits suggest about their lifestyle, social preferences, and relationships?
- How would they behave in group movie settings? Solo viewing vs. social watching?
- What kind of film discussions would they excel in or avoid?

### 📈 **VIEWING EVOLUTION & GROWTH**
- How might their tastes be evolving based on recent activity?
- What blind spots exist in their viewing that could expand their horizons?
- How adventurous vs. comfort-zone-focused are they in their choices?

Be extremely specific, avoid generic observations, and use their actual data as evidence. Provide actionable insights about their cinematic personality."""

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
    
    def generate_complete_analysis(self, username1: str, username2: str) -> Dict:
        """Generate the complete analysis report"""
        if username1 not in self.profiles or username2 not in self.profiles:
            return {"error": "Profiles not loaded"}
        
        profile1 = self.profiles[username1]
        profile2 = self.profiles[username2]
        
        print("🔍 Performing complete analysis...")
        
        # All analysis components
        patterns1 = self.extract_viewing_patterns(profile1)
        patterns2 = self.extract_viewing_patterns(profile2)
        genres1 = self.analyze_genre_preferences(profile1)
        genres2 = self.analyze_genre_preferences(profile2)
        personality1 = self.generate_personality_profile(profile1)
        personality2 = self.generate_personality_profile(profile2)
        common_movies = self.find_common_movies(profile1, profile2)
        compatibility = self.calculate_compatibility(profile1, profile2)
        
        # LLM analysis
        llm_analysis = self.llm_analyze_profiles(profile1, profile2) if self.llm_available else "LLM analysis not available"
        
        return {
            'analysis_date': datetime.now().isoformat(),
            'users': [username1, username2],
            'profiles': {
                username1: {
                    'stats': {
                        'total_movies': profile1.total_movies,
                        'avg_rating': profile1.avg_rating,
                        'total_reviews': profile1.total_reviews
                    },
                    'patterns': patterns1,
                    'genres': genres1,
                    'personality': personality1
                },
                username2: {
                    'stats': {
                        'total_movies': profile2.total_movies,
                        'avg_rating': profile2.avg_rating,
                        'total_reviews': profile2.total_reviews
                    },
                    'patterns': patterns2,
                    'genres': genres2,
                    'personality': personality2
                }
            },
            'common_movies': common_movies,
            'compatibility': compatibility,
            'llm_analysis': llm_analysis,
            'summary': {
                'compatibility_score': compatibility.get('overall_score', 0),
                'recommendation': compatibility.get('recommendation', ''),
                'common_movies_count': len(common_movies),
                'llm_enabled': self.llm_available
            }
        }
    
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
        if not profile.watchlist.empty:
            for _, row in profile.watchlist.iterrows():
                watchlist.append(f"{row['Name']} ({row['Year']})")
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
        watched_movies = self.get_watched_movies_set(profile)
        genres = self.analyze_genre_preferences(profile)
        patterns = self.extract_viewing_patterns(profile)
        
        # Get top-rated movies by user for pattern analysis
        high_rated = profile.ratings[profile.ratings['Rating'] >= 4.5]['Name'].tolist() if not profile.ratings.empty else []
        
        # Create a curated list based on preferences (this would ideally come from a movie database)
        # For now, using a sample of acclaimed movies per genre
        recommendations_pool = {
            'drama': ['Parasite (2019)', 'Nomadland (2020)', 'Moonlight (2016)', 'Call Me by Your Name (2017)', 'Manchester by the Sea (2016)'],
            'thriller': ['Prisoners (2013)', 'Zodiac (2007)', 'Gone Girl (2014)', 'Nightcrawler (2014)', 'Sicario (2015)'],
            'comedy': ['The Grand Budapest Hotel (2014)', 'In Bruges (2008)', 'Hunt for the Wilderpeople (2016)', 'What We Do in the Shadows (2014)'],
            'horror': ['Hereditary (2018)', 'The Babadook (2014)', 'A Quiet Place (2018)', 'Midsommar (2019)', 'The Witch (2015)'],
            'sci-fi': ['Arrival (2016)', 'Ex Machina (2014)', 'Blade Runner 2049 (2017)', 'Her (2013)', 'Annihilation (2018)'],
            'action': ['Mad Max: Fury Road (2015)', 'John Wick (2014)', 'Mission: Impossible - Fallout (2018)', 'The Raid (2011)'],
            'romance': ['The Before Trilogy', 'Lost in Translation (2003)', 'Her (2013)', 'The Shape of Water (2017)'],
            'animation': ['Spider-Man: Into the Spider-Verse (2018)', 'Coco (2017)', 'Inside Out (2015)', 'Spirited Away (2001)']
        }
        
        # Select recommendations based on top genres
        recommendations = []
        top_genres = sorted(genres.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:3]
        
        for genre, _ in top_genres:
            genre_key = genre.lower()
            if genre_key in recommendations_pool:
                for movie in recommendations_pool[genre_key]:
                    if movie not in watched_movies and movie not in recommendations:
                        recommendations.append(movie)
                        if len(recommendations) >= count:
                            break
            if len(recommendations) >= count:
                break
        
        return recommendations[:count]
    

def print_analysis_report(analysis: Dict):
    """Print a beautiful analysis report"""
    print("\n" + "="*100)
    print(" 🎬 COMPLETE LETTERBOXD PROFILE ANALYSIS 🎬 ".center(100, "="))
    print("="*100)
    
    users = analysis['users']
    profiles = analysis['profiles']
    compatibility = analysis['compatibility']
    common_movies = analysis['common_movies']
    
    # Header
    print(f"\n📊 PROFILE OVERVIEW")
    print("-" * 50)
    for user in users:
        stats = profiles[user]['stats']
        personality = profiles[user]['personality']
        print(f"👤 {user}:")
        print(f"   📽️  {stats['total_movies']} movies rated (avg: {stats['avg_rating']:.2f}⭐)")
        print(f"   📝 {stats['total_reviews']} reviews written")
        print(f"   🎭 {personality.get('type', 'unknown').replace('_', ' ').title()}")
        print(f"   💭 {personality.get('description', 'N/A')}")
        print()
    
    # Compatibility
    print(f"🤝 COMPATIBILITY ANALYSIS")
    print("-" * 50)
    score = compatibility.get('overall_score', 0)
    print(f"Overall Compatibility: {score:.1%} {'🟢' if score > 0.7 else '🟡' if score > 0.5 else '🔴'}")
    print(f"Recommendation: {compatibility.get('recommendation', 'N/A')}")
    print()
    
    # Detailed metrics
    rating_agreement = compatibility.get('rating_agreement', {})
    print(f"📈 Detailed Metrics:")
    print(f"   Common movies: {rating_agreement.get('common_movies_count', 0)}")
    if rating_agreement.get('avg_difference'):
        print(f"   Average rating difference: {rating_agreement['avg_difference']:.2f}⭐")
        print(f"   Movies both loved (4⭐+): {rating_agreement.get('both_loved_count', 0)}")
        print(f"   Movies both disliked (≤2⭐): {rating_agreement.get('both_hated_count', 0)}")
        print(f"   Major disagreements (≥2⭐ diff): {rating_agreement.get('major_disagreements', 0)}")
    
    if 'pattern_similarity' in compatibility:
        print(f"   Rating pattern similarity: {compatibility['pattern_similarity']:.1%}")
    if 'genre_compatibility' in compatibility:
        print(f"   Genre taste alignment: {compatibility['genre_compatibility']:.1%}")
    print(f"   Personality match: {compatibility.get('personality_match', 0):.1%}")
    print()
    
    # Genre preferences
    print(f"🎭 GENRE PREFERENCES")
    print("-" * 50)
    for user in users:
        genres = profiles[user]['genres']
        print(f"{user}'s top genres:")
        top_genres = sorted(genres.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:5]
        for genre, data in top_genres:
            print(f"   {genre.title()}: {data['avg_rating']:.1f}⭐ ({data['count']} movies)")
        print()
    
    # Common movies highlights
    if common_movies:
        print(f"🎯 MOVIE AGREEMENT HIGHLIGHTS")
        print("-" * 50)
        
        # Perfect agreements
        perfect = [m for m in common_movies if m['difference'] == 0 and m['both_loved']]
        if perfect:
            print("🎉 Perfect agreements (both loved):")
            for movie in perfect[:5]:
                rating = movie[f"{users[0]}_rating"]
                print(f"   {movie['movie']} ({movie['year']}) - Both rated {rating}⭐")
        
        # Biggest disagreements
        disagreements = sorted(common_movies, key=lambda x: x['difference'], reverse=True)[:5]
        if disagreements and disagreements[0]['difference'] > 0:
            print(f"\n💥 Biggest disagreements:")
            for movie in disagreements:
                if movie['difference'] > 0:
                    print(f"   {movie['movie']} ({movie['year']}): {movie[f'{users[0]}_rating']}⭐ vs {movie[f'{users[1]}_rating']}⭐")
        print()
    
    # LLM Analysis
    if analysis.get('llm_analysis') and analysis['llm_analysis'] != "LLM analysis not available":
        print(f"🤖 AI DEEP ANALYSIS")
        print("-" * 50)
        print(analysis['llm_analysis'])
        print()
    
    print("="*100)


def main():
    """Main execution function"""
    print("🎬 Unified Letterboxd Profile Analyzer")
    print("=" * 60)
    
    # Initialize analyzer
    openai_key = os.getenv('OPENAI_API_KEY')
    analyzer = UnifiedLetterboxdAnalyzer(openai_api_key=openai_key, use_local_llm=True)
    
    # Profile paths (update these for your data)
    profile1_path = "/Users/mailyas/Downloads/letterboxd/hashtag7781/letterboxd-hashtag7781-2025-06-13-22-11-utc"
    profile2_path = "/Users/mailyas/Downloads/letterboxd/whiteknight03x"
    
    # Load profiles
    print("\n📂 Loading profiles...")
    try:
        profile1 = analyzer.load_profile(profile1_path, "hashtag7781")
        profile2 = analyzer.load_profile(profile2_path, "whiteknight03x")
    except Exception as e:
        print(f"❌ Error loading profiles: {e}")
        return
    
    # Generate complete analysis
    analysis = analyzer.generate_complete_analysis("hashtag7781", "whiteknight03x")
    
    # Print report
    print_analysis_report(analysis)
    
    # Save option
    save = input("💾 Save complete analysis to JSON? (y/n): ").lower().strip()
    if save == 'y':
        filename = f"complete_letterboxd_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"✅ Analysis saved to {filename}")


if __name__ == "__main__":
    main()
