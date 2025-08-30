"""
LLM prompts for the Letterboxd Analyzer application.
"""
import pandas as pd

def get_profile_analysis_prompt(profile1, profile2, patterns1, patterns2, genres1, genres2, personality1, personality2, recs1, recs2, common_movies, compatibility, watched1, watched2):
    """Generates the prompt for comparing two profiles."""
    return f"""You are an expert film critic and psychologist analyzing two Letterboxd users. Provide a comprehensive, well-structured analysis of their movie taste compatibility.

## 🎬 USER PROFILES

**{profile1.username}:**
• {len(profile1.ratings)} movies rated (avg: {profile1.avg_rating:.2f}★) | {len(watched1)} total watched
• Personality: {personality1.get('type', 'unknown')} - {personality1.get('description', 'N/A')}
• Top genres: {', '.join([f"{g} ({d['avg_rating']:.1f}★)" for g, d in sorted(genres1.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:3]])}
• Rating style: {patterns1.get('harsh_critic_ratio', 0):.1%} harsh, {patterns1.get('generous_rater_ratio', 0):.1%} generous

**{profile2.username}:**
• {len(profile2.ratings)} movies rated (avg: {profile2.avg_rating:.2f}★) | {len(watched2)} total watched
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
{chr(10).join([f"• {movie}" for movie in recs1[:4]]) if recs1 else "• Custom recommendations needed"}

**For {profile2.username} (based on their tastes):**
{chr(10).join([f"• {movie}" for movie in recs2[:4]]) if recs2 else "• Custom recommendations needed"}

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


def get_individual_analysis_prompt(profile, patterns, genres, personality, detailed_prefs, watched_movies, watchlist, recommendations, top_rated, low_rated, recent_reviews):
    """Generates the prompt for analyzing a single profile."""
    return f"""Analyze this Letterboxd user's cinematic personality with deep psychological insights and detailed recommendations.

## 🎬 COMPREHENSIVE USER PROFILE: {profile.username}

### 📊 CORE STATISTICS
• **Total movies rated:** {len(profile.ratings)} | **Average rating:** {profile.avg_rating:.2f}★
• **Total reviews:** {profile.total_reviews}
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

def get_individual_analysis_prompt_safe(profile):
    """Generate a safer version of individual analysis that handles missing data"""
    try:
        # Safely get basic statistics
        total_movies = len(profile.ratings) if not profile.ratings.empty else 0
        avg_rating = profile.ratings['Rating'].mean() if not profile.ratings.empty else 0
        total_reviews = len(profile.reviews) if not profile.reviews.empty else 0

        # Safely get genre preferences (simplified version)
        genre_analysis = "Genre analysis requires additional processing"

        # Get top and low rated movies safely
        top_movies = []
        low_movies = []

        if not profile.ratings.empty:
            ratings_numeric = pd.to_numeric(profile.ratings['Rating'], errors='coerce')
            profile.ratings['Rating_Numeric'] = ratings_numeric

            high_rated = profile.ratings[profile.ratings['Rating_Numeric'] >= 4.5]
            if not high_rated.empty:
                top_movies = high_rated.head(5).apply(
                    lambda x: f"{x.get('Name', 'Unknown')} ({x.get('Year', 'N/A')}) - {x.get('Rating', 'N/A')}★",
                    axis=1
                ).tolist()

            low_rated = profile.ratings[profile.ratings['Rating_Numeric'] <= 2.0]
            if not low_rated.empty:
                low_movies = low_rated.head(3).apply(
                    lambda x: f"{x.get('Name', 'Unknown')} ({x.get('Year', 'N/A')}) - {x.get('Rating', 'N/A')}★",
                    axis=1
                ).tolist()

        # Create a simplified but comprehensive prompt
        return f"""Analyze this Letterboxd user's movie preferences and provide personality insights.

USER PROFILE: {profile.username}

CORE STATISTICS:
• Total movies rated: {total_movies}
• Average rating: {avg_rating:.2f}★
• Total reviews written: {total_reviews}


TOP RATED MOVIES (4.5+ stars):
{chr(10).join(['• ' + movie for movie in top_movies]) if top_movies else '• No highly rated movies found'}

MOVIES THEY DISLIKED (≤2 stars):
{chr(10).join(['• ' + movie for movie in low_movies]) if low_movies else '• No strongly disliked movies found'}

ANALYSIS REQUEST:
Provide a detailed personality analysis covering:

1. **Movie Taste Profile**: What do their preferences reveal about their personality?
2. **Critical Style**: Are they harsh, generous, or balanced in their ratings?
3. **Viewing Patterns**: What can you infer about their lifestyle and preferences?
4. **Personality Traits**: What psychological traits emerge from their movie choices?
5. **Recommendations**: Suggest 3-5 specific movies they might enjoy and explain why.

Be specific, insightful, and avoid generic observations. Use their actual ratings as evidence."""

    except Exception as e:
        return f"Error generating analysis prompt: {str(e)}"
