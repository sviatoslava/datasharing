#!/bin/bash
# Start both backend and frontend servers

echo "Starting Noon Clone..."
echo ""

# Start backend
echo "Starting backend API on http://localhost:3001"
cd backend && node server.js &
BACKEND_PID=$!

# Wait for backend to start
sleep 1

# Start frontend
echo "Starting frontend dev server on http://localhost:5173"
cd ../frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "App is running!"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:3001"
echo ""
echo "Press Ctrl+C to stop"

# Handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
