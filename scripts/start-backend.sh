#!/bin/bash

# Start Backend Server Script
echo "🎬 Starting Letterboxd Reviewer Backend..."

# Navigate to backend directory
cd "$(dirname "$0")/../backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r ../requirements.txt

# Create data directory if it doesn't exist
mkdir -p ../data/scraped ../data/exports ../data/backups

# Start the server
echo "🚀 Starting FastAPI server on port 8000..."
python3 -m uvicorn main:app --reload --port 8000