# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    build-essential \
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
RUN mkdir -p downloads configs logs

# Set proper permissions
RUN chmod +x main.py

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

# Create an entrypoint script to fix permissions at runtime
RUN echo '#!/bin/bash\n\
# Fix permissions for mounted directories\n\
if [ -d "/app/logs" ]; then\n\
    sudo chown -R app:app /app/logs 2>/dev/null || true\n\
fi\n\
# Run the main application\n\
exec python main.py' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import discord; print('Bot dependencies OK')" || exit 1

# Command to run the application
CMD ["python", "main.py"]