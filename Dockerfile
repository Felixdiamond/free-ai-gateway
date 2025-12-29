FROM python:slim

# Install system dependencies
# chromium: The browser required for zendriver
# xvfb: Virtual framebuffer to enable headful apps in containers
# x11-utils: Provides xset for checking X11 server status
RUN apt-get update && apt-get install -y \
    chromium \
    xvfb \
    x11-utils \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BROWSER_PATH=/usr/bin/chromium \
    HEADLESS=false \
    DISPLAY=:99

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy and make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Command to run the application
ENTRYPOINT ["/entrypoint.sh"]
