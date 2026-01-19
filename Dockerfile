FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    cron \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data and logs
RUN mkdir -p /data /logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////data/congress_tracker.db
ENV PYTHONPATH=/app

# Copy cron file to container
COPY docker/crontab /etc/cron.d/congress-tracker

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/congress-tracker

# Apply cron job
RUN crontab /etc/cron.d/congress-tracker

# Create entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command runs cron in foreground
CMD ["cron"]
