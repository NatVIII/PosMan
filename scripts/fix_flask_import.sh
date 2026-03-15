#!/bin/bash
set -euo pipefail

# Quick fix script for "Could not import 'app.app'" error
# This script rebuilds the Docker image with proper configuration
# and verifies the import works.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
IMAGE_NAME="poster-management"
CONTAINER_NAME="posman"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check Docker
if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi

# Ensure config directory exists with minimal config
ensure_config() {
    if [[ ! -d "$PROJECT_ROOT/config" ]]; then
        log_warn "Config directory not found, creating minimal config..."
        mkdir -p "$PROJECT_ROOT/config"
    fi
    
    # Ensure system.yaml exists
    if [[ ! -f "$PROJECT_ROOT/config/system.yaml" ]]; then
        log_warn "Creating minimal system.yaml..."
        cat > "$PROJECT_ROOT/config/system.yaml" <<EOF
system:
  name: "Poster Management System"
  data_path: "/data"
  ftp_export_path: "/data/ftp_export"
  backup_path: "/backups"
  backup_retention: 4
  upload_limit_mb: 200
users: []
EOF
    fi
    
    # Ensure template.yaml exists
    if [[ ! -f "$PROJECT_ROOT/config/template.yaml" ]]; then
        log_warn "Creating minimal template.yaml..."
        cat > "$PROJECT_ROOT/config/template.yaml" <<EOF
template:
  global:
    price: 12.00
    seller: "Party For Socialism and Liberation"
    slogans: ["@pslvirginia", "Dare to struggle, dare to win"]
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
    fi
    
    # Ensure data directories exist
    mkdir -p "$PROJECT_ROOT/data/originals" \
             "$PROJECT_ROOT/data/processed" \
             "$PROJECT_ROOT/data/thumbnails" \
             "$PROJECT_ROOT/data/ftp_export" \
             "$PROJECT_ROOT/backups"
}

# Fix permissions (set to user 1000, typical for Docker)
fix_permissions() {
    log_info "Checking directory permissions..."
    if [[ -d "$PROJECT_ROOT/config" ]]; then
        # Check if we can fix permissions (might need sudo)
        if [[ -w "$PROJECT_ROOT/config" ]]; then
            log_info "Setting permissions on config directory..."
            chmod 755 "$PROJECT_ROOT/config"
            find "$PROJECT_ROOT/config" -type f -exec chmod 644 {} \;
        else
            log_warn "Cannot write to config directory, permission fix may require sudo"
        fi
    fi
}

# Rebuild Docker image with fixes
rebuild_image() {
    log_info "Rebuilding Docker image '$IMAGE_NAME'..."
    if docker build -t "$IMAGE_NAME:latest" .; then
        log_info "Image rebuilt successfully"
        return 0
    else
        log_error "Failed to rebuild image"
        return 1
    fi
}

# Test import in the Docker image
test_import() {
    log_info "Testing import in Docker image..."
    if docker run --rm \
        -v "$PROJECT_ROOT/config:/config" \
        -v "$PROJECT_ROOT/data:/data" \
        -v "$PROJECT_ROOT/backups:/backups" \
        -e FLASK_APP=app \
        -e FLASK_ENV=development \
        "$IMAGE_NAME:latest" \
        python -c "import sys; sys.path.insert(0, '.'); import app; print('✅ Import successful')"; then
        log_info "Import test passed"
        return 0
    else
        log_error "Import test failed"
        return 1
    fi
}

# Stop and remove existing container
cleanup_container() {
    if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
        log_info "Stopping and removing existing container '$CONTAINER_NAME'..."
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
        docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    else
        log_info "Container '$CONTAINER_NAME' not found"
    fi
}

# Start container using docker-compose
start_container() {
    log_info "Starting container with docker-compose..."
    if command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        log_error "docker-compose not found"
        return 1
    fi
    
    if $COMPOSE_CMD up -d; then
        log_info "Container started successfully"
        return 0
    else
        log_error "Failed to start container with docker-compose"
        return 1
    fi
}

# Main fix routine
main() {
    log_info "Starting fix for Flask import error"
    
    # Step 1: Ensure configuration exists
    ensure_config
    
    # Step 2: Fix permissions (optional)
    fix_permissions
    
    # Step 3: Rebuild image with fixes
    if ! rebuild_image; then
        exit 1
    fi
    
    # Step 4: Test import works
    if ! test_import; then
        log_error "Import test failed. Running detailed diagnostic..."
        # Run diagnostic script if available
        if [[ -f "$SCRIPT_DIR/diagnose_flask_import.py" ]]; then
            docker run --rm \
                -v "$PROJECT_ROOT/config:/config" \
                -v "$PROJECT_ROOT/data:/data" \
                -v "$PROJECT_ROOT/backups:/backups" \
                -e FLASK_APP=app \
                "$IMAGE_NAME:latest" \
                python "$SCRIPT_DIR/diagnose_flask_import.py"
        fi
        exit 1
    fi
    
    # Step 5: Clean up existing container
    cleanup_container
    
    # Step 6: Start new container
    if start_container; then
        log_info "✅ Fix applied successfully!"
        log_info "Container should now be running. Check logs with:"
        log_info "  docker logs $CONTAINER_NAME"
        log_info "Access the application at: http://localhost:5000"
    else
        log_error "Failed to start container. You can try manually:"
        log_error "  docker-compose up -d"
        exit 1
    fi
}

# Run main function
main