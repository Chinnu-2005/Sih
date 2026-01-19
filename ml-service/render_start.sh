#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Starting ML Service and Worker on Render..."

# Start Redis-dependent worker in background
python worker.py &

# Start FastAPI app in foreground
# Uvicorn needs to listen on 0.0.0.0 and the PORT env var provided by Render
python -m uvicorn app:app --host 0.0.0.0 --port $PORT
