#!/bin/bash
set -euo pipefail

# Fix permissions for Docker Compose directories
# Use this script if Docker Compose created directories as root

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Get current user's UID and GID
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

log_info "Fixing permissions for user: $(whoami) (UID: $CURRENT_UID, GID: $CURRENT_GID)"

# Check if we have sudo access
check_sudo() {
    if sudo -n true 2>/dev/null; then
        return 0
    else
        log_warn "sudo access not available or requires password"
        return 1
    fi
}

# Fix ownership of directories
fix_ownership() {
    local dirs=("config" "data" "backups")
    
    for dir in "${dirs[@]}"; do
        local full_path="$PROJECT_ROOT/$dir"
        if [[ -d "$full_path" ]]; then
            log_info "Checking ownership of $dir..."
            local current_owner=$(stat -c '%u:%g' "$full_path" 2>/dev/null || stat -f '%u:%g' "$full_path")
            if [[ "$current_owner" != "$CURRENT_UID:$CURRENT_GID" ]]; then
                log_warn "$dir is owned by $current_owner, changing to $CURRENT_UID:$CURRENT_GID"
                if [[ -w "$full_path" ]]; then
                    chown -R "$CURRENT_UID:$CURRENT_GID" "$full_path"
                    chmod -R 755 "$full_path"
                else
                    if check_sudo; then
                        log_info "Using sudo to change ownership..."
                        sudo chown -R "$CURRENT_UID:$CURRENT_GID" "$full_path"
                        sudo chmod -R 755 "$full_path"
                    else
                        log_error "Cannot change ownership of $dir (permission denied)"
                        log_error "Please run: sudo chown -R $CURRENT_UID:$CURRENT_GID $dir"
                        return 1
                    fi
                fi
            else
                log_info "$dir already owned by $CURRENT_UID:$CURRENT_GID"
            fi
        else
            log_info "Directory $dir does not exist, skipping"
        fi
    done
    
    # Fix subdirectories
    if [[ -d "$PROJECT_ROOT/data" ]]; then
        log_info "Fixing permissions in data subdirectories..."
        find "$PROJECT_ROOT/data" -type d -exec chmod 755 {} \; 2>/dev/null || true
        find "$PROJECT_ROOT/data" -type f -exec chmod 644 {} \; 2>/dev/null || true
    fi
    
    return 0
}

# Stop and remove existing containers to avoid conflicts
stop_containers() {
    log_info "Checking for running containers..."
    if command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        log_warn "docker-compose not found, skipping container stop"
        return
    fi
    
    if $COMPOSE_CMD ps -q >/dev/null 2>&1; then
        log_info "Stopping existing containers..."
        $COMPOSE_CMD down
    fi
}

# Main function
main() {
    log_info "Starting permission fix..."
    
    # Stop containers to avoid permission conflicts
    stop_containers
    
    # Fix ownership
    if fix_ownership; then
        log_info "✅ Permissions fixed successfully!"
        log_info ""
        log_info "Now you can start the container with:"
        log_info "  docker-compose up -d"
        log_info ""
        log_info "If you want to rebuild the image with your user ID:"
        log_info "  docker-compose build"
        log_info "  docker-compose up -d"
    else
        log_error "Failed to fix permissions"
        exit 1
    fi
}

# Run main function
main