#!/bin/bash
set -e

# SALSA Docker Entrypoint
# Starts both FastAPI backend and Reflex frontend

# Default to production mode
MODE="${MODE:-prod}"

echo "Starting SALSA in ${MODE} mode..."

# Start FastAPI backend in background
echo "Starting FastAPI backend on port 8001..."
uvicorn salsa.backend.main:app --host 0.0.0.0 --port 8001 &
FASTAPI_PID=$!

# Give FastAPI a moment to start
sleep 2

# Start Reflex frontend (foreground - keeps container running)
echo "Starting Reflex frontend on port 3000..."
if [ "$MODE" = "dev" ]; then
    # Development mode with hot reload
    reflex run --env dev --frontend-port 3000 --backend-port 8000
else
    # Production mode
    reflex run --env prod --frontend-port 3000 --backend-port 8000
fi
