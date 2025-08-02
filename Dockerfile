# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies including FFmpeg and gosu for user switching
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    build-essential \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
# Ownership will be fixed at runtime by the CMD instruction
RUN mkdir -p downloads configs logs

# Create a non-root user and group for security
# We do NOT set the USER here, as the initial command must run as root
RUN groupadd -r app && useradd --no-log-init -r -g app app

# Change ownership of the app directory itself during build time
RUN chown -R app:app /app

# Command to run the application
# This command is run as root.
# 1. It first changes ownership of the mounted volumes.
# 2. Then, it uses 'gosu' to switch to the 'app' user and execute the python script.
# The 'exec' ensures the python process becomes the main process (PID 1).
CMD ["sh", "-c", "chown -R app:app /app/configs /app/downloads /app/logs && exec gosu app python main.py"]
