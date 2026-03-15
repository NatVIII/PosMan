# Poster Management System

A Flask-based web application for managing poster production, inventory, and distribution for the Party for Socialism and Liberation. This system replaces manual Python scripts with a user-friendly web interface that handles bug generation, thumbnail creation, inventory tracking, and label generation.

## Table of Contents
- [Features](#features)
- [System Requirements](#system-requirements)
- [Quick Start with Docker](#quick-start-with-docker)
- [Production Deployment Considerations](#production-deployment-considerations)
- [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Using the System](#using-the-system)
- [User Roles](#user-roles)
- [File Structure](#file-structure)
- [PDF Processing Configuration](#pdf-processing-configuration)
- [Backup and Recovery](#backup-and-recovery)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Features

### Currently Implemented (Phase 4)
- **PDF Processing**: Automatically adds bug pages with QR codes, metadata, and logos to poster PDFs
- **Thumbnail Generation**: Creates preview thumbnails from PDF first pages using pdf2image
- **Inventory Tracking**: Tracks poster counts with history and user attribution
- **Role-Based Authentication**: Viewer, Contributor, and Admin roles with different permissions
- **File-Based Storage**: JSON/YAML files for easy backup and version control (no database required)
- **Responsive Web Interface**: Bootstrap 5-based interface accessible from any device
- **Docker Deployment**: Easy containerized deployment with Docker
- **Landscape Support**: Automatic 90° rotation for landscape posters
- **Price Management**: Configurable price tiers and pricing
- **Poster Management**: Upload, view, edit, delete, and download posters
- **Dashboard**: System statistics and recent activity overview

### Coming Soon (Future Phases)
- **Collection Management**: Kit/Collection hierarchy browser and management
- **Label Generation**: Automatic PDF label generation for kits and collections
- **FTP Export**: Organized export structure for printing
- **CSV Import**: Migration tool for existing poster data
- **Advanced Search**: Filtering by kit, collection, category, orientation
- **Batch Operations**: Bulk inventory updates and processing

## System Requirements

- **Docker** (recommended) or **Python 3.11+**
- **PDF processing dependencies**: poppler-utils (for thumbnail generation)
- **Disk Space**: ~500MB for application + storage for your poster files
- **Memory**: 1GB RAM minimum, 2GB recommended for processing large PDFs

## Quick Start with Docker

### 1. Clone and Setup
```bash
git clone https://github.com/NatVIII/PosMan
cd poster-management-system
```

### 2. Setup Permissions and Configuration
```bash
# Run the setup script to create directories with proper permissions
chmod +x setup.sh
./setup.sh

# If Docker Compose already created directories as root, fix permissions:
chmod +x fix-permissions.sh
./fix-permissions.sh
```

### 3. Build the Docker Image (required if your user ID is not 1000)
```bash
docker-compose build
```

> **Note:** The setup script automatically detects your user ID. If your UID is not 1000 (the default), you MUST run `docker-compose build` to rebuild the image with your user ID. This ensures proper file permissions.

### 4. Start the Application
```bash
docker-compose up -d
```

### 5. Access the Application
Open your browser to: `http://localhost:5000`

### 6. Login Credentials
> **⚠️ SECURITY WARNING**: Change default passwords immediately after first login!

- **Admin**: `admin` / `password` (password change required on first login)
- **Viewer**: `viewer` / `password`
- Additional users can be created in the admin interface


## Offline Deployment and Customization

The system is designed to run in completely offline environments with no external network dependencies. All web assets (Bootstrap CSS/JS, Bootstrap Icons) are included locally in the repository.

### Local Assets
- Bootstrap 5.3.0 CSS and JavaScript bundle
- Bootstrap Icons 1.10.0 (WOFF2/WOFF fonts)
- Customizable SVG favicon
- Placeholder `app.js` for custom JavaScript

### Updating Assets
To update Bootstrap or Bootstrap Icons to newer versions, run:
```bash
./scripts/download_assets.sh
```

This script downloads the latest versions and updates templates automatically.

### Custom Favicon
Replace `app/static/favicon.svg` with your custom SVG logo. The system will automatically use it. For ICO favicon support, install ImageMagick and run the asset script again.

### Verification
Run the offline test to confirm everything works without network access:
```bash
./scripts/test_docker.sh
```

## Production Deployment Considerations

The default `docker-compose.yml` uses development settings. For production:

1. **Set a proper SECRET_KEY** in the Flask app configuration
2. **Enable HTTPS** and set `SESSION_COOKIE_SECURE=True`
3. **Use a reverse proxy** (nginx, Apache) for SSL termination
4. **Configure proper backups** with off-site storage
5. **Set up monitoring** and log aggregation
6. **Restrict network access** (use Tailscale, VPN, or firewall rules)
7. **Regularly update dependencies** for security patches

Example production `docker-compose.yml` additions:
```yaml
environment:
  - FLASK_ENV=production
  - SECRET_KEY=your-very-secure-random-key-here
```

## Manual Installation

### 1. Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv poppler-utils

# macOS with Homebrew
brew install python poppler
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment

**Option A: Environment variables**
```bash
export FLASK_APP=app
export FLASK_ENV=development
export CONFIG_PATH=./config
```

**Option B: Use .flaskenv file** (already configured in the repository)
```bash
# The repository includes a .flaskenv file with these settings
# Just activate your virtual environment and run Flask
```

### 5. Run the Application
```bash
python -m flask run --host=0.0.0.0 --port=5000
```

## Configuration

### Configuration Files
The system uses YAML configuration files in the `config/` directory:

- `config/system.yaml` - System settings and user accounts
- `config/template.yaml` - Bug template settings and price tiers
- `config/assets/logo.png` - Logo for bug pages (optional)

### Default Users
The system comes with three default users (all with password "password"):
- `admin` - Full system access
- `viewer` - Read-only access
- `testuser` - Read-only access

### Changing Passwords
1. Log in as `admin` (password: `password`)
2. Go to **Admin → Manage Users**
3. Click "Edit" next to any user
4. Enter new password and save

### Creating New Users
1. Log in as `admin`
2. Go to **Admin → Manage Users**
3. Click "Add New User"
4. Fill in username, password, and role
5. Save

## Using the System

### 1. Uploading Posters
1. Log in as a Contributor or Admin
2. Click "Upload Poster" in the navigation bar
3. Fill in the form:
   - **PDF File**: Select your 12x18" poster PDF
   - **Title**: Descriptive title (required)
   - **Source**: e.g., National, Local, Chapter
   - **Categories**: e.g., Anti-War, Labor, Palestine
   - **Price**: Default is $12.00
   - **Kit/Collection**: Organizational hierarchy
4. Click "Upload & Process"

The system will:
- Save the original PDF
- Add a bug page with QR code and metadata
- Generate a thumbnail preview
- Rotate landscape posters 90° if configured
- Save processed PDF to storage

### 2. Managing Inventory
1. Navigate to **Posters → All Posters**
2. Click on any poster to view details
3. In the "Pricing & Inventory" section:
   - Enter new count
   - Select action (Counted, Printed, Adjusted)
   - Add optional notes
   - Click "Update Count"

Inventory history is tracked with timestamps and user attribution.

### 3. Editing Poster Metadata
1. Navigate to **Posters → All Posters**
2. Click "Edit" on any poster
3. Modify any field (title, categories, price, etc.)
4. Click "Save Changes"

### 4. Downloading Posters
1. Navigate to **Posters → All Posters**
2. Click on any poster
3. Click "Download PDF" to get the processed version with bug page

### 5. Deleting Posters
1. Navigate to **Posters → All Posters**
2. Click on any poster
3. Click "Delete" (Admin only)
4. Confirm deletion

This removes the poster and all associated files (original PDF, processed PDF, thumbnail, metadata).

## User Roles

### Viewer
- View posters and thumbnails
- Download processed PDFs
- View inventory counts
- Cannot modify any data

### Contributor
- All Viewer permissions
- Upload new posters
- Edit poster metadata
- Update inventory counts
- Cannot delete posters or manage users

### Admin
- All Contributor permissions
- Delete posters
- Manage user accounts
- Access system configuration
- View system information

## File Structure

```
poster-management-system/
├── Dockerfile                 # Docker build configuration
├── docker-compose.yml         # Docker Compose configuration
├── requirements.txt           # Python dependencies
├── config/                    # Configuration files (mounted volume)
│   ├── system.yaml           # System settings and users
│   ├── template.yaml         # Bug template configuration
│   └── assets/               # Logo and other assets
├── data/                      # Data storage (mounted volume)
│   ├── originals/            # Original uploaded PDFs
│   ├── processed/            # Processed PDFs with bugs
│   ├── thumbnails/           # Generated thumbnail images
│   └── metadata/             # Poster metadata (JSON files)
├── backups/                   # Automated backups (mounted volume)
├── app/                       # Flask application
│   ├── __init__.py           # Application factory
│   ├── auth.py               # Authentication system
│   ├── config.py             # Configuration loader
│   ├── routes.py             # Main routes (dashboard, about, etc.)
│   ├── poster_routes.py      # Poster management routes
│   ├── poster.py             # Poster model and storage
│   ├── pdf_processor.py      # PDF processing engine
│   └── templates/            # HTML templates
└── scripts/                  # Utility scripts
    ├── generate_hash.py      # Generate password hashes
    └── test_*.py            # Various test scripts
```

## PDF Processing Configuration

The bug generation is configured in `config/template.yaml`:

```yaml
template:
  global:
    price: 12.00                    # Default price
    seller: "Party For Socialism and Liberation"
    slogans:                        # Default slogans
      - "@pslvirginia"
      - "Dare to struggle, dare to win"
    logo:
      path: "/config/assets/logo.png"
      width_ratio: 0.8             # Logo width relative to bug
    bug:
      width_in: 2.0                # Bug width in inches
      top_frac: 0.1                # Vertical position (0=top, 1=bottom)
      page_margin_in: 0.5          # Page margin in inches
      dpi: 300                     # Output resolution
      horizontal_orientation: "landscape"  # Rotate landscape posters
      font_size: 18                # Text size
      qr_box_size: 10              # QR code box size
```

## Customizing the Logo

1. Place your logo file in `config/assets/logo.png`
2. Ensure it has transparency (PNG with alpha channel recommended)
3. The system will automatically resize it to fit the bug page

## Backup and Recovery

### Automatic Backups
The system creates weekly backups in the `backups/` directory:
- Full system backup every Sunday at 2:00 AM
- 4 weeks of retention (configurable in `system.yaml`)
- ZIP files containing configuration and metadata

### Manual Backup
```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/ config/

# Restore from backup
tar -xzf backup-20250311.tar.gz
```

### Disaster Recovery
1. Stop the application
2. Restore `config/` and `data/` directories from backup
3. Restart the application

## Troubleshooting

### Common Issues

#### "Permission denied" errors with Docker

Docker Compose may create directories as root when they don't exist. Fix with:

**Option A: Use the fix-permissions script (recommended):**
```bash
chmod +x fix-permissions.sh
./fix-permissions.sh
```

**Option B: Manual fix:**
```bash
# Replace 1000:1000 with your user's UID:GID (run `id -u` and `id -g`)
sudo chown -R $(id -u):$(id -g) config data backups
sudo chmod -R 755 config data backups
```

**Prevention:** Run `./setup.sh` before `docker-compose up -d` to create directories with proper ownership.

#### PDF processing fails
1. Check that poppler-utils is installed (`pdftoppm --version`)
2. Verify PDF is valid and not corrupted
3. Check application logs for errors

#### Thumbnails not generating
1. Ensure `pdf2image` Python package is installed
2. Verify poppler-utils is installed
3. Check `data/thumbnails/` directory permissions

#### "File too large" error
Increase upload limit in `config/system.yaml`:
```yaml
system:
  upload_limit_mb: 500  # Increase from default 200MB
```

### Viewing Logs

#### Docker Compose
```bash
docker-compose logs -f
```

#### Manual Installation
Check Flask output in terminal or system logs.

### Resetting Passwords
If you lose admin access:
1. Stop the application
2. Edit `config/system.yaml`
3. Find the admin user and update `password_hash`
4. Generate a new hash: `python scripts/generate_hash.py newpassword`
5. Copy the hash to the YAML file
6. Restart the application

## Development

### Running Tests
```bash
# Run integration tests
python scripts/test_integration.py

# Test PDF processor
python scripts/test_pdf_processor.py

# Test thumbnail generation
python scripts/test_thumbnail.py
```

### Code Structure
- `app/` - Flask application with modular components
- `app/auth.py` - Authentication and authorization
- `app/poster.py` - Poster model and JSON storage
- `app/pdf_processor.py` - PDF processing based on legacy bug script
- `app/poster_routes.py` - All poster-related web endpoints

### Adding New Features
1. Add routes to appropriate blueprint (`routes.py` or `poster_routes.py`)
2. Create templates in `app/templates/`
3. Add any new models to `app/poster.py`
4. Update tests in `scripts/`

### Implementation Plan
This project follows a phased implementation plan documented in `Implementation_Plan.md`. The current implementation covers Phase 4 (Thumbnail Generation & Upload Interface). Future phases include collection management, label generation, FTP export, and CSV migration.

## Migration from Legacy System

### CSV Migration (Planned)
The system includes a CSV migration tool (in development) to import existing poster data from `List Of All Posters - Sheet1.csv`.

### File Migration
1. Copy existing PDFs to `data/originals/`
2. Use the CSV migration tool once implemented
3. Or manually upload through the web interface

## Security Considerations

- Change default passwords immediately
- Use HTTPS in production (set `SESSION_COOKIE_SECURE=True` in app config)
- Restrict network access (use Tailscale or VPN)
- Regular backups
- Monitor application logs
- Keep dependencies updated

## License

This project is developed for internal use by the Party for Socialism and Liberation.

## Support

For issues and feature requests:
1. Check the troubleshooting section
2. Review application logs
3. Contact system administrator

---

**Version**: 1.0.0-dev  
**Last Updated**: March 2025  
**Status**: Development (Phase 4 Complete - Thumbnail Generation & Upload Interface)