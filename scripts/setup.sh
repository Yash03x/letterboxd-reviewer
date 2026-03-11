#!/bin/bash

# Project Setup Script
echo "🎬 Setting up Spyboxd..."

# Make scripts executable
chmod +x scripts/*.sh

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/scraped data/exports data/backups

# Backend setup
echo "🐍 Setting up backend..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r ../requirements.txt
cd ..

# Frontend setup
echo "🎨 Setting up frontend..."
cd frontend
npm install
cd ..

echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  Backend:  ./scripts/start-backend.sh"
echo "  Frontend: ./scripts/start-frontend.sh"
echo ""
echo "Or use: ./scripts/start-all.sh to start both servers"