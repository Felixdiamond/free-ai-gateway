#!/bin/bash
set -e

# Clean up any stale X11 lock files
rm -f /tmp/.X99-lock

# Start Xvfb and store PID
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!

# Wait for Xvfb to be ready
echo "Waiting for Xvfb to start..."
for i in {1..30}; do
    if xset -display :99 q > /dev/null 2>&1; then
        echo "Xvfb is ready"
        break
    fi
    echo "Attempt $i: Xvfb not ready, waiting..."
    sleep 0.5
done

# Start the application
echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
