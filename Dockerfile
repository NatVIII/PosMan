FROM python:3.11-alpine

# Build arguments for user ID (default to 1000 for compatibility)
ARG UID=1000
ARG GID=1000

# Install system dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev \
    harfbuzz-dev \
    fribidi-dev \
    ghostscript \
    poppler-utils \
    && rm -rf /var/cache/apk/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and configuration
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY .flaskenv .

# Set default environment variables
ENV FLASK_APP=app \
    FLASK_ENV=production \
    CONFIG_PATH=/config \
    PYTHONUNBUFFERED=1

# Create necessary directories
RUN mkdir -p /config /data /backups \
    && chmod 755 /config /data /backups

# Create non-root user with specified UID/GID
RUN addgroup -g $GID posteruser && \
    adduser -D -u $UID -G posteruser posteruser

# Set ownership of directories to the new user
RUN chown -R $UID:$GID /config /data /backups /app

USER posteruser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

# Run application
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]