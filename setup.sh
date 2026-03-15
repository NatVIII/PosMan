#!/bin/bash
set -euo pipefail

# Setup script for Poster Management System
# Creates necessary directories with proper permissions and configures Docker

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

log_info "Current user: $(whoami) (UID: $CURRENT_UID, GID: $CURRENT_GID)"

# Create necessary directories with proper ownership
create_directories() {
    log_info "Creating required directories..."
    
    local dirs=("config" "data" "backups")
    
    for dir in "${dirs[@]}"; do
        local full_path="$PROJECT_ROOT/$dir"
        if [[ ! -d "$full_path" ]]; then
            log_info "Creating directory: $dir"
            mkdir -p "$full_path"
        else
            log_info "Directory already exists: $dir"
        fi
        
        # Set ownership to current user
        if [[ -w "$full_path" ]]; then
            log_info "Setting ownership of $dir to $CURRENT_UID:$CURRENT_GID"
            chown "$CURRENT_UID:$CURRENT_GID" "$full_path"
            chmod 755 "$full_path"
        else
            log_warn "Cannot change ownership of $dir (permission denied)"
            log_warn "You may need to run: sudo chown -R $CURRENT_UID:$CURRENT_GID $dir"
        fi
    done
    
    # Create subdirectories inside data
    local data_subdirs=("originals" "processed" "thumbnails" "ftp_export" "ftp_export/All" "ftp_export/Ordered")
    for subdir in "${data_subdirs[@]}"; do
        local full_path="$PROJECT_ROOT/data/$subdir"
        if [[ ! -d "$full_path" ]]; then
            log_info "Creating data subdirectory: $subdir"
            mkdir -p "$full_path"
            if [[ -w "$full_path" ]]; then
                chown "$CURRENT_UID:$CURRENT_GID" "$full_path"
                chmod 755 "$full_path"
            fi
        fi
    done
}

# Create minimal configuration files if missing
create_config_files() {
    log_info "Checking configuration files..."
    
    # Create config directory if it doesn't exist
    mkdir -p "$PROJECT_ROOT/config"
    
    # Create system.yaml if missing
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
users:
  - created_at: '2025-03-11T00:00:00Z'
    force_password_change: true
    password_hash: \$2b\$12\$qUJvPsZHvbNpI4fVLK9VmOcJ96eKj7vNkVOqhpiEevtn7uzzBhfZa
    role: admin
    username: admin
  - created_at: '2025-03-11T00:00:00Z'
    force_password_change: false
    password_hash: \$2b\$12\$qUJvPsZHvbNpI4fVLK9VmOcJ96eKj7vNkVOqhpiEevtn7uzzBhfZa
    role: viewer
    username: viewer
EOF
        chmod 644 "$PROJECT_ROOT/config/system.yaml"
        log_info "Created system.yaml with default users (admin/viewer password: 'password')"
    fi
    
    # Create template.yaml if missing
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
    premium:
      name: "Premium"
      price: 15.00
    sale:
      name: "Sale"
      price: 8.00
EOF
        chmod 644 "$PROJECT_ROOT/config/template.yaml"
    fi
    
    # Create assets directory
    mkdir -p "$PROJECT_ROOT/config/assets"
    log_info "Configuration files checked/created"
}

# Create .env file for Docker Compose
create_env_file() {
    log_info "Creating .env file for Docker Compose..."
    
    cat > "$PROJECT_ROOT/.env" <<EOF
# Docker Compose environment variables
# These are used to match container user with host user

# Current user's UID and GID
UID=$CURRENT_UID
GID=$CURRENT_GID

# Flask settings (can be overridden here)
FLASK_APP=app
FLASK_ENV=development
CONFIG_PATH=/config

# Uncomment for production
# FLASK_ENV=production
# SECRET_KEY=your-secure-random-key-here
EOF
    
    chmod 644 "$PROJECT_ROOT/.env"
    log_info "Created .env file with UID=$CURRENT_UID, GID=$CURRENT_GID"
}

# Update docker-compose.yml to use current user
update_docker_compose() {
    log_info "Checking docker-compose.yml configuration..."
    
    # Check if docker-compose.yml has user configuration
    if grep -q "user:" "$PROJECT_ROOT/docker-compose.yml"; then
        log_info "docker-compose.yml has user configuration"
    else
        log_warn "docker-compose.yml missing user configuration"
        log_warn "The container may have permission issues!"
    fi
    
    # Check if docker-compose.yml has build args
    if grep -q "args:" "$PROJECT_ROOT/docker-compose.yml"; then
        log_info "docker-compose.yml has build args for UID/GID"
    else
        log_warn "docker-compose.yml missing build args for UID/GID"
        log_warn "Rebuild the image with: docker-compose build"
    fi
}

# Check if rebuild is needed based on UID/GID
check_rebuild_needed() {
    if [[ "$CURRENT_UID" != "1000" || "$CURRENT_GID" != "1000" ]]; then
        log_warn "Your user ID ($CURRENT_UID) or group ID ($CURRENT_GID) is not 1000"
        log_warn "You MUST rebuild the Docker image with your IDs:"
        log_warn "  docker-compose build"
        log_warn "Otherwise the container will have permission issues!"
    fi
}

# Display next steps
show_next_steps() {
    log_info "Setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Review configuration files in config/ directory"
    echo "2. Build the Docker image with your user ID (important if UID != 1000):"
    echo "     docker-compose build"
    echo "3. Start the container:"
    echo "     docker-compose up -d"
    echo "4. Access the application at: http://localhost:5000"
    echo "5. Default login: admin / password (change immediately!)"
    echo ""
    echo "If you encounter permission issues:"
    echo "  ./fix-permissions.sh"
    echo ""
    echo "If the container fails to start, check logs:"
    echo "  docker-compose logs"
    echo ""
}

# Main execution
main() {
    log_info "Setting up Poster Management System"
    
    create_directories
    create_config_files
    create_env_file
    update_docker_compose
    check_rebuild_needed
    show_next_steps
}

# Run main function
main