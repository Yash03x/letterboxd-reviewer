"""
Configuration settings for the Letterboxd Analyzer application.
"""
import os

# Base directory for the application
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Path for temporary file extraction
# Leaving this commented out as we will use tempfile.mkdtemp() for better security
# TEMP_DIR = os.path.join(BASE_DIR, "temp_data")

# Local data path (example, should be configured by user or discovered)
# This is an example and should not be hardcoded in a production app
# A better approach is to let the user specify it in the UI
DEFAULT_LOCAL_DATA_PATH = os.path.expanduser("~/Downloads/letterboxd")

# LLM settings
OLLAMA_URL = "http://localhost:11434/api/generate"
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
OLLAMA_API_TAGS_URL = "http://localhost:11434/api/tags"

# Recommendation settings
RECOMMENDATIONS_FILE_PATH = os.path.join(BASE_DIR, "core", "recommendations.json")
