#!/bin/bash
set -euo pipefail

# Docker container test script for Poster Management System
# This script builds the Docker image, runs a container, and verifies
# that the application starts correctly and passes health checks.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
IMAGE_NAME="poster-management-test"
CONTAINER_NAME="poster-management-test-container"
PORT="5500"  # Use a different port to avoid conflicts
MAX_WAIT=60  # Maximum seconds to wait for container to be healthy
SLEEP_INTERVAL=2

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

cleanup() {
    log_info "Cleaning up..."
    # Stop and remove container if it exists
    if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
        log_info "Stopping container $CONTAINER_NAME..."
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
        log_info "Removing container $CONTAINER_NAME..."
        docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
    # Remove the test image if it exists
    if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^$IMAGE_NAME:latest$"; then
        log_info "Removing image $IMAGE_NAME:latest..."
        docker rmi "$IMAGE_NAME:latest" >/dev/null 2>&1 || true
    fi
    # Remove temporary config directory if created
    if [[ -n "${TEMP_CONFIG_DIR:-}" && -d "$TEMP_CONFIG_DIR" ]]; then
        log_info "Removing temporary config directory $TEMP_CONFIG_DIR..."
        rm -rf "$TEMP_CONFIG_DIR"
    fi
}

# Set up trap to ensure cleanup on script exit
trap cleanup EXIT

# Check if Docker is available
if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi

# Create temporary config directory if config directory is missing
if [[ ! -d "$PROJECT_ROOT/config" ]]; then
    log_warn "Config directory not found at $PROJECT_ROOT/config, creating temporary one..."
    TEMP_CONFIG_DIR="$(mktemp -d)"
    cp -r "$PROJECT_ROOT/config"/* "$TEMP_CONFIG_DIR/" 2>/dev/null || {
        # If no config files exist, create minimal config
        mkdir -p "$TEMP_CONFIG_DIR"
        cat > "$TEMP_CONFIG_DIR/system.yaml" <<EOF
system:
  name: "Poster Management System Test"
  data_path: "/data"
  ftp_export_path: "/data/ftp_export"
  backup_path: "/backups"
  backup_retention: 4
  upload_limit_mb: 200
users: []
EOF
        cat > "$TEMP_CONFIG_DIR/template.yaml" <<EOF
template:
  global:
    price: 12.00
    seller: "Test Seller"
    slogans: ["Test slogan"]
    logo:
      path: "/config/assets/logo.png"
      width_ratio: 0.8
      scaling: "fit"
    bug:
      width_in: 2.0
      top_frac: 0.1
      page_margin_in: 0.5
      dpi: 300
      horizontal_orientation: "landscape"
  price_tiers:
    standard:
      name: "Standard"
      price: 12.00
      default: true
EOF
    }
    CONFIG_DIR="$TEMP_CONFIG_DIR"
else
    CONFIG_DIR="$PROJECT_ROOT/config"
fi

# Build Docker image
log_info "Building Docker image $IMAGE_NAME..."
if ! docker build -t "$IMAGE_NAME:latest" .; then
    log_error "Docker build failed"
    exit 1
fi

# Run import test to verify all dependencies are installed
log_info "Running import test inside container..."
if ! docker run --rm \
    -v "$CONFIG_DIR:/config" \
    -v "$PROJECT_ROOT/data:/data" \
    -v "$PROJECT_ROOT/backups:/backups" \
    -e FLASK_ENV=development \
    -e FLASK_APP=app \
    -e FLASK_DEBUG=1 \
    -e PYTHONUNBUFFERED=1 \
    "$IMAGE_NAME:latest" \
    python scripts/container_import_test.py; then
    log_error "Import test failed - missing dependencies or configuration"
    exit 1
fi

# Run container
log_info "Starting container $CONTAINER_NAME on port $PORT..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$PORT:5000" \
    -v "$CONFIG_DIR:/config" \
    -v "$PROJECT_ROOT/data:/data" \
    -v "$PROJECT_ROOT/backups:/backups" \
    -e FLASK_ENV=development \
    -e FLASK_APP=app \
    -e FLASK_DEBUG=1 \
    -e PYTHONUNBUFFERED=1 \
    "$IMAGE_NAME:latest"

# Wait for container to be healthy
log_info "Waiting for container to become healthy (max ${MAX_WAIT}s)..."
ELAPSED=0
HEALTH_STATUS=""
while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    if ! docker ps --format '{{.Names}} {{.Status}}' | grep -q "$CONTAINER_NAME Up"; then
        log_error "Container is not running"
        docker logs "$CONTAINER_NAME"
        exit 1
    fi
    
    # Check health status using Docker healthcheck
    HEALTH_STATUS="$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "no-healthcheck")"
    if [[ "$HEALTH_STATUS" == "healthy" ]]; then
        log_info "Container is healthy!"
        break
    fi
    
    # Also check if the application is responding to HTTP health endpoint
    if curl -s -f "http://localhost:$PORT/health" >/dev/null 2>&1; then
        log_info "Health endpoint responded successfully"
        HEALTH_STATUS="healthy"
        break
    fi
    
    sleep "$SLEEP_INTERVAL"
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

if [[ "$HEALTH_STATUS" != "healthy" ]]; then
    log_error "Container did not become healthy within $MAX_WAIT seconds"
    log_error "Container logs:"
    docker logs "$CONTAINER_NAME"
    exit 1
fi

# Check for any import errors in logs
log_info "Checking container logs for import errors..."
if docker logs "$CONTAINER_NAME" 2>&1 | grep -i "could not import\|module not found\|import error"; then
    log_error "Found import errors in container logs"
    docker logs "$CONTAINER_NAME"
    exit 1
fi

# Verify the application is serving the health endpoint
log_info "Testing health endpoint..."
if ! curl -s -f "http://localhost:$PORT/health" | grep -q "OK"; then
    log_error "Health endpoint did not return OK"
    exit 1
fi

log_info "All tests passed! The Docker container is running correctly."

# Optional: run additional integration tests here
# ...

# The cleanup trap will handle stopping and removing the container
log_info "Test completed successfully. Container will be stopped and removed."