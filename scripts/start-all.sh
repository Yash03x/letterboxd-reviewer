#!/bin/bash

# Start Both Backend and Frontend Script
echo "🎬 Starting Letterboxd Reviewer (Full Stack)..."

# Function to cleanup background processes on exit
cleanup() {
    echo "🔄 Stopping all servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

# Trap cleanup function on script exit
trap cleanup EXIT INT TERM

# Start backend in background
echo "🐍 Starting backend server..."
./scripts/start-backend.sh &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend server..."
./scripts/start-frontend.sh &
FRONTEND_PID=$!

echo ""
echo "✅ Both servers started successfully!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all servers..."

# Wait for processes to finish
wait