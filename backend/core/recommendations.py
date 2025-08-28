import json
from typing import Protocol, List, Dict
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.analyzer import ProfileData
from config import settings

class RecommendationEngine(Protocol):
    """Protocol for a recommendation engine."""

    def recommend(self, profile: ProfileData, count: int = 5) -> List[str]:
        """
        Generate movie recommendations for a given profile.

        Args:
            profile: The user's profile data.
            count: The number of recommendations to generate.

        Returns:
            A list of movie recommendations.
        """
        ...

class SimpleGenreBasedRecommendationEngine:
    """
    A simple recommendation engine based on the user's top genres.
    """
    def __init__(self):
        try:
            with open(settings.RECOMMENDATIONS_FILE_PATH, 'r') as f:
                self.recommendations_pool = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.recommendations_pool = {}

    def recommend(self, profile: ProfileData, analyzer, count: int = 5) -> List[str]:
        """
        Generate recommendations based on the user's top genres.
        """
        watched_movies = analyzer.get_watched_movies_set(profile)
        genres = analyzer.analyze_genre_preferences(profile)

        recommendations = []
        top_genres = sorted(genres.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:3]

        for genre, _ in top_genres:
            genre_key = genre.lower()
            if genre_key in self.recommendations_pool:
                for movie in self.recommendations_pool[genre_key]:
                    if movie not in watched_movies and movie not in recommendations:
                        recommendations.append(movie)
                        if len(recommendations) >= count:
                            break
            if len(recommendations) >= count:
                break

        return recommendations[:count]
