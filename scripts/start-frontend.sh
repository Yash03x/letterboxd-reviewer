#!/bin/bash

# Start Frontend Development Server Script
echo "🎨 Starting Letterboxd Reviewer Frontend..."

# Navigate to frontend directory
cd "$(dirname "$0")/../frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the development server
echo "🚀 Starting React development server on port 3000..."
npm start