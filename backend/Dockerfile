FROM python:3.11-slim

# Set environment variables for production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies (production optimized - minimal)
RUN apt-get update && apt-get install -y \
    bash \
    gcc \
    libpq-dev \
    postgresql-client \
    postgresql-client-common \
    curl \
    netcat-openbsd \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip cache purge

# Copy application code
COPY . .

# Create non-root user for production (no sudo, minimal privileges)
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    mkdir -p \
      /app/logs \
      /data/sandbox_artifacts \
      /data/swe_runs \
      /tmp/huggingface_cache \
      /tmp/sandbox_cache \
      /tmp/sandbox_repos \
      /tmp/transformers_cache && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /data && \
    chown -R appuser:appuser \
      /tmp/huggingface_cache \
      /tmp/sandbox_cache \
      /tmp/sandbox_repos \
      /tmp/transformers_cache && \
    chmod +x /app/start.sh

RUN mkdir -p /home/appuser/.cache && \
    chown -R appuser:appuser /home/appuser && \
    chmod -R 755 /home/appuser

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Production health check (less frequent, more stable)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
  CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["/app/start.sh"]
