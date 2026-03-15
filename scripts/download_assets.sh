#!/bin/bash
set -euo pipefail

# Asset download script for Poster Management System
# Downloads Bootstrap 5.3.0 and Bootstrap Icons 1.10.0 for offline use

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
BOOTSTRAP_VERSION="5.3.0"
BOOTSTRAP_ICONS_VERSION="1.10.0"
ASSET_DIR="$PROJECT_ROOT/app/static"

# URLs
BOOTSTRAP_CSS_URL="https://cdn.jsdelivr.net/npm/bootstrap@${BOOTSTRAP_VERSION}/dist/css/bootstrap.min.css"
BOOTSTRAP_JS_URL="https://cdn.jsdelivr.net/npm/bootstrap@${BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js"
BOOTSTRAP_ICONS_CSS_URL="https://cdn.jsdelivr.net/npm/bootstrap-icons@${BOOTSTRAP_ICONS_VERSION}/font/bootstrap-icons.css"
BOOTSTRAP_ICONS_FONT_BASE="https://cdn.jsdelivr.net/npm/bootstrap-icons@${BOOTSTRAP_ICONS_VERSION}/font/fonts"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Create directory structure
create_directories() {
    log_info "Creating directory structure..."
    mkdir -p "$ASSET_DIR/css"
    mkdir -p "$ASSET_DIR/js"
    mkdir -p "$ASSET_DIR/fonts"
    log_info "Directories created"
}

# Check for required commands
check_commands() {
    local missing=()
    for cmd in curl wget; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done
    
    if [ ${#missing[@]} -eq 0 ]; then
        return 0
    fi
    
    log_warn "Missing commands: ${missing[*]}"
    log_warn "Trying alternative download methods..."
    return 1
}

# Download file with curl or wget
download_file() {
    local url="$1"
    local output="$2"
    
    log_info "Downloading: $(basename "$output")"
    
    # Try curl first, then wget
    if command -v curl >/dev/null 2>&1; then
        if curl -s -f -L "$url" -o "$output"; then
            return 0
        fi
    fi
    
    if command -v wget >/dev/null 2>&1; then
        if wget -q "$url" -O "$output"; then
            return 0
        fi
    fi
    
    log_error "Failed to download: $url"
    return 1
}

# Download Bootstrap CSS
download_bootstrap_css() {
    local output="$ASSET_DIR/css/bootstrap.min.css"
    download_file "$BOOTSTRAP_CSS_URL" "$output"
    if [ $? -eq 0 ]; then
        log_info "Bootstrap CSS downloaded: $(stat -c%s "$output") bytes"
        # Add a comment about the source
        echo -e "/* Bootstrap ${BOOTSTRAP_VERSION} - Downloaded from ${BOOTSTRAP_CSS_URL} */\n$(cat "$output")" > "$output.tmp"
        mv "$output.tmp" "$output"
    fi
}

# Download Bootstrap JS bundle
download_bootstrap_js() {
    local output="$ASSET_DIR/js/bootstrap.bundle.min.js"
    download_file "$BOOTSTRAP_JS_URL" "$output"
    if [ $? -eq 0 ]; then
        log_info "Bootstrap JS downloaded: $(stat -c%s "$output") bytes"
        # Add a comment about the source
        echo -e "/* Bootstrap ${BOOTSTRAP_VERSION} - Downloaded from ${BOOTSTRAP_JS_URL} */\n$(cat "$output")" > "$output.tmp"
        mv "$output.tmp" "$output"
    fi
}

# Download Bootstrap Icons CSS and fix font paths
download_bootstrap_icons() {
    local css_output="$ASSET_DIR/css/bootstrap-icons.css"
    download_file "$BOOTSTRAP_ICONS_CSS_URL" "$css_output"
    
    if [ $? -eq 0 ]; then
        log_info "Bootstrap Icons CSS downloaded: $(stat -c%s "$css_output") bytes"
        
        # Fix font URLs to point to local fonts directory
        sed -i 's|url("./fonts/|url("../fonts/|g' "$css_output"
        
        # Add a comment about the source
        echo -e "/* Bootstrap Icons ${BOOTSTRAP_ICONS_VERSION} - Downloaded from ${BOOTSTRAP_ICONS_CSS_URL} */\n$(cat "$css_output")" > "$css_output.tmp"
        mv "$css_output.tmp" "$css_output"
        
        # Download font files
        local font_files=("bootstrap-icons.woff2" "bootstrap-icons.woff" "bootstrap-icons.ttf")
        for font in "${font_files[@]}"; do
            local font_url="$BOOTSTRAP_ICONS_FONT_BASE/$font"
            local font_output="$ASSET_DIR/fonts/$font"
            download_file "$font_url" "$font_output"
            if [ $? -eq 0 ]; then
                log_info "Font downloaded: $font ($(stat -c%s "$font_output") bytes)"
            fi
        done
    fi
}

# Create placeholder favicon
create_placeholder_favicon() {
    log_info "Creating placeholder favicon files..."
    
    # Create a simple SVG favicon (can be replaced with custom SVG)
    cat > "$ASSET_DIR/favicon.svg" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" fill="#0d6efd"/>
  <rect x="10" y="10" width="80" height="80" fill="white"/>
  <text x="50" y="65" text-anchor="middle" font-family="Arial, sans-serif" font-size="40" fill="#0d6efd">P</text>
</svg>
EOF
    
    # Create ICO placeholder (using convert if available)
    if command -v convert >/dev/null 2>&1; then
        convert -size 64x64 xc:#0d6efd -fill white -draw "rectangle 6,6 58,58" -pointsize 32 -fill #0d6efd -draw "text 32,42 'P'" "$ASSET_DIR/favicon.ico"
        log_info "ICO favicon created"
    else
        log_warn "ImageMagick 'convert' not found, skipping ICO favicon"
    fi
    
    log_info "Placeholder favicons created"
}

# Create empty app.js if it doesn't exist
create_app_js() {
    local app_js="$ASSET_DIR/js/app.js"
    if [ ! -f "$app_js" ]; then
        log_info "Creating empty app.js"
        echo -e "/* Custom JavaScript for Poster Management System */\n// Add your custom JavaScript here\n" > "$app_js"
    fi
}

# Download all assets
download_all_assets() {
    create_directories
    
    log_info "Downloading assets for offline use..."
    log_info "Bootstrap Version: ${BOOTSTRAP_VERSION}"
    log_info "Bootstrap Icons Version: ${BOOTSTRAP_ICONS_VERSION}"
    
    check_commands || true
    
    download_bootstrap_css
    download_bootstrap_js
    download_bootstrap_icons
    create_placeholder_favicon
    create_app_js
    
    log_info "Asset download complete!"
    
    # Show file sizes
    echo ""
    log_info "Downloaded assets:"
    find "$ASSET_DIR" -type f -exec ls -lh {} \; 2>/dev/null | awk '{print $9 ": " $5}'
}

# Update templates to use local assets
update_templates() {
    log_info "Updating templates to use local assets..."
    
    # Update base.html to use local assets
    local base_template="$PROJECT_ROOT/app/templates/base.html"
    if [ -f "$base_template" ]; then
        # Backup original
        cp "$base_template" "$base_template.backup"
        
        # Replace external CDN URLs with local paths
        sed -i 's|https://cdn\.jsdelivr\.net/npm/bootstrap@5\.3\.0/dist/css/bootstrap\.min\.css|{{ url_for('\''static'\'', filename='\''css/bootstrap.min.css'\'') }}|g' "$base_template"
        sed -i 's|https://cdn\.jsdelivr\.net/npm/bootstrap-icons@1\.10\.0/font/bootstrap-icons\.css|{{ url_for('\''static'\'', filename='\''css/bootstrap-icons.css'\'') }}|g' "$base_template"
        sed -i 's|https://cdn\.jsdelivr\.net/npm/bootstrap@5\.3\.0/dist/js/bootstrap\.bundle\.min\.js|{{ url_for('\''static'\'', filename='\''js/bootstrap.bundle.min.js'\'') }}|g' "$base_template"
        
        log_info "Base template updated"
    else
        log_error "Base template not found: $base_template"
    fi
}

# Add favicon link to base template
add_favicon() {
    local base_template="$PROJECT_ROOT/app/templates/base.html"
    if [ -f "$base_template" ]; then
        # Check if favicon link already exists
        if grep -q "favicon" "$base_template"; then
            log_info "Favicon link already exists in template"
            return
        fi
        
        # Add favicon link after the title
        sed -i '/<title>/a \    <link rel="icon" href="{{ url_for('\''static'\'', filename='\''favicon.svg'\'') }}" type="image/svg+xml">\n    <link rel="shortcut icon" href="{{ url_for('\''static'\'', filename='\''favicon.ico'\'') }}" type="image/x-icon">' "$base_template"
        
        log_info "Favicon links added to template"
    fi
}

# Main function
main() {
    log_info "Starting asset setup for offline operation"
    
    # Download all assets
    download_all_assets
    
    # Update templates
    update_templates
    
    # Add favicon links
    add_favicon
    
    log_info "✅ Setup complete!"
    echo ""
    log_info "Assets are now stored locally in: $ASSET_DIR"
    log_info "Templates updated to use local assets"
    log_info "Placeholder favicons created"
    echo ""
    log_info "Next steps:"
    log_info "1. Replace $ASSET_DIR/favicon.svg with your custom logo"
    log_info "2. If you have ImageMagick installed, replace $ASSET_DIR/favicon.ico"
    log_info "3. Add any custom CSS to $ASSET_DIR/css/style.css"
    log_info "4. Add custom JavaScript to $ASSET_DIR/js/app.js"
    echo ""
    log_info "To update assets in the future, run:"
    log_info "  ./scripts/download_assets.sh"
}

# Run main function
main