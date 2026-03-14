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

# Recommendation settings
RECOMMENDATIONS_FILE_PATH = os.path.join(BASE_DIR, "core", "recommendations.json")
