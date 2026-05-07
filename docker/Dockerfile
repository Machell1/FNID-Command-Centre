# FNID Command Centre v2.0 - Production Dockerfile
FROM python:3.12-slim-bookworm

LABEL maintainer="FNID Area 3 IT Support"
LABEL version="2.0"
LABEL description="JCF FNID Command Centre - Production"

# Security: Run as non-root
RUN groupadd -r fnid && useradd -r -g fnid fnid

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     gcc     postgresql-client     libpq-dev     libgeos-dev     && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY wsgi.py .
COPY .env.example .env

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/exports /app/logs     && chown -R fnid:fnid /app

# Switch to non-root user
USER fnid

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Expose port
EXPOSE 5000

# Production command
CMD ["gunicorn", "-w", "4", "-k", "sync", "--bind", "0.0.0.0:5000", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--enable-stdio-inheritance", "wsgi:app"]
