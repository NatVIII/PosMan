#!/bin/bash
set -euo pipefail

# Diagnostic script for Docker container import issues
# Run this to find out why "Could not import 'app.app'" occurs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
IMAGE_NAME="poster-management"
CONTAINER_NAME="posman"  # Default container name from user
DIAG_SCRIPT="scripts/diagnose_flask_import.py"

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

# Check if the diagnostic Python script exists
if [[ ! -f "$DIAG_SCRIPT" ]]; then
    log_error "Diagnostic script not found: $DIAG_SCRIPT"
    exit 1
fi

# Function to run diagnostics in a container
run_diagnostics() {
    local container_id=$1
    log_info "Running diagnostics in container: $container_id"
    
    # Copy diagnostic script to container
    log_info "Copying diagnostic script to container..."
    if ! docker cp "$DIAG_SCRIPT" "$container_id:/tmp/diagnose_flask_import.py"; then
        log_error "Failed to copy diagnostic script to container"
        return 1
    fi
    
    # Run diagnostic script
    log_info "Executing diagnostic script..."
    docker exec "$container_id" python /tmp/diagnose_flask_import.py
    
    # Clean up
    docker exec "$container_id" rm -f /tmp/diagnose_flask_import.py
}

# Function to create a temporary test container
create_test_container() {
    log_info "Creating temporary test container for diagnostics..."
    
    # Check if image exists
    if ! docker images --format '{{.Repository}}' | grep -q "^$IMAGE_NAME$"; then
        log_warn "Image $IMAGE_NAME not found, attempting to build..."
        if ! docker build -t "$IMAGE_NAME" .; then
            log_error "Failed to build Docker image"
            exit 1
        fi
    fi
    
    # Create temporary config directory if needed
    if [[ ! -d "$PROJECT_ROOT/config" ]]; then
        log_warn "Config directory not found, creating minimal config..."
        mkdir -p "$PROJECT_ROOT/config"
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
        cat > "$PROJECT_ROOT/config/template.yaml" <<EOF
template:
  global:
    price: 12.00
    seller: "Test"
    slogans: ["Test"]
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
    
    # Run temporary container
    local temp_container_id
    temp_container_id=$(docker run -d --rm \
        --name "posman-diagnostic" \
        -v "$PROJECT_ROOT/config:/config" \
        -v "$PROJECT_ROOT/data:/data" \
        -v "$PROJECT_ROOT/backups:/backups" \
        -e FLASK_ENV=development \
        -e FLASK_APP=app \
        -e FLASK_DEBUG=1 \
        -e PYTHONUNBUFFERED=1 \
        "$IMAGE_NAME" \
        sleep 300)  # Sleep for 5 minutes to allow diagnostics
    
    echo "$temp_container_id"
}

# Main diagnostic routine
main() {
    log_info "Starting Docker container import diagnostic"
    
    # Check if the main container exists and is running
    if docker ps --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
        log_info "Container '$CONTAINER_NAME' is running"
        run_diagnostics "$CONTAINER_NAME"
    elif docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
        log_warn "Container '$CONTAINER_NAME' exists but is not running"
        log_info "Starting container..."
        docker start "$CONTAINER_NAME"
        sleep 2
        if docker ps --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
            run_diagnostics "$CONTAINER_NAME"
        else
            log_error "Failed to start container '$CONTAINER_NAME'"
            log_info "Creating temporary test container instead..."
            temp_id=$(create_test_container)
            run_diagnostics "posman-diagnostic"
            log_info "Cleaning up temporary container..."
            docker stop "posman-diagnostic" >/dev/null 2>&1 || true
        fi
    else
        log_warn "Container '$CONTAINER_NAME' does not exist"
        log_info "Creating temporary test container for diagnostics..."
        temp_id=$(create_test_container)
        run_diagnostics "posman-diagnostic"
        log_info "Cleaning up temporary container..."
        docker stop "posman-diagnostic" >/dev/null 2>&1 || true
    fi
    
    log_info "Diagnostic complete"
}

# Run main function
main