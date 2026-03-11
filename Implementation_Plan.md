# Poster Management System - Implementation Plan

## Executive Summary

The Poster Management System is a Flask-based web application designed to manage poster production for the Party for Socialism and Liberation. The system replaces manual Python scripts with a user-friendly web interface accessible via a Docker container on a Tailscale network. Key features include configurable bug generation with automatic rotation for landscape posters, kit/collection hierarchy with inventory tracking, automatic printable label generation, and a file-based data architecture using YAML/JSON for easy backup and version control.

## System Architecture

### Technology Stack
- **Backend**: Flask with Jinja2 templates (server-rendered)
- **Authentication**: bcrypt password hashing, session-based
- **File Storage**: YAML for configuration, JSON for metadata, filesystem for PDFs/images
- **Processing**: Enhanced version of existing `bug.backup112325.py` with 90° rotation support
- **Container**: Docker with `python:3.11-alpine` base image
- **Network**: Accessible via Tailscale network

### File Structure
```
/postermanagement/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── app/                          # Flask application
│   ├── __init__.py
│   ├── auth.py                   # Authentication system
│   ├── config.py                 # Configuration loader
│   ├── models.py                 # Data models (file-based)
│   ├── processing.py             # Bug generation + label generation
│   ├── routes.py                 # URL routing
│   ├── static/                   # CSS, JS, assets
│   └── templates/                # Jinja2 templates
├── config/                       # Mounted volume: configuration
│   ├── system.yaml              # Global system settings
│   ├── template.yaml            # Bug template defaults
│   ├── price_tiers.yaml         # Price tiers configuration
│   └── users/                   # User account files (optional)
├── data/                         # Mounted volume: data storage
│   ├── kits/                    # Kit definitions (YAML)
│   │   ├── smalls.yaml         # "Smalls" kit
│   ├── collections/             # Collection definitions (YAML)
│   │   ├── jaffa.yaml          # Jaffa collection
│   │   ├── harlem.yaml         # Harlem collection
│   │   └── palisades.yaml      # Palisades collection
│   ├── posters/                 # Poster metadata (JSON, one per poster)
│   │   ├── PANN-01.json
│   │   ├── PANN-02.json
│   │   └── ...
│   ├── originals/               # Original uploaded files (preserved)
│   ├── processed/               # Final 12x18 PDFs with bugs
│   ├── thumbnails/              # Web previews (300px width)
│   ├── labels/                  # Generated printable labels
│   │   ├── kits/               # Kit labels (8.5×11")
│   │   └── collections/        # Collection labels (11×17")
│   ├── ftp_export/              # Printer-ready PDFs
│   │   ├── All/                # Flat structure: all posters
│   │   └── Ordered/            # Hierarchical: Kit → Collection → PDF
│   └── inventory/               # Inventory history snapshots
└── scripts/                     # Utility scripts
    ├── migrate_csv.py          # CSV to JSON migration
    └── generate_labels.py      # Label generation utility
```

## Data Models

### System Configuration (`/config/system.yaml`)
```yaml
system:
  name: "Poster Management System"
  ftp_export_path: "/data/ftp_export"
  backup_path: "/backups"
  backup_retention: 4           # Keep last 4 weekly backups
  upload_limit_mb: 200          # 200MB file size limit
  
users:
  - username: "admin"
    password_hash: "$2b$..."    # bcrypt hash
    role: "admin"               # admin/contributor/viewer
    created_at: "2025-03-11T12:00:00Z"
    force_password_change: true # Force change on first login
    
label_templates:
  kit:
    page_size: [8.5, 11]        # inches
    margins: [0.5, 0.5]         # inches
    background_color: "#FFFFFF"
    header:
      font_size: 36
      color: "#000000"
    collections_list:
      font_size: 18
      spacing: 0.25             # inches
      
  collection:
    page_size: [11, 17]         # inches  
    margins: [0.5, 0.5]
    thumbnail_size: [2.0, 1.5]  # inches
    grid: [4, 5]                # columns, rows
    id_font_size: 12
```

### Bug Template Configuration (`/config/template.yaml`)
```yaml
template:
  global:
    price: 12.00
    seller: "Party For Socialism and Liberation"
    slogans:
      - "@pslvirginia"
      - "Dare to struggle, dare to win"
    logo:
      path: "/config/assets/logo.png"
      width_ratio: 0.8
      scaling: "fit"
    bug:
      width_in: 2.0
      top_frac: 0.1
      page_margin_in: 0.5
      dpi: 300
      horizontal_orientation: "landscape"  # Rotate 90° for landscape posters

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
```

### Kit Definition (`/data/kits/smalls.yaml`)
```yaml
id: "smalls"
name: "Smalls"
description: "Small format posters in plastic tote"
collections: ["jaffa", "harlem", "palisades"]  # Collection IDs
label_config:
  background_color: "#FF0000"    # Red for Smalls kit
  icon_path: "/config/assets/smalls_icon.png"
  custom_text: "Contains Jaffa, Harlem, and Palisades collections"
created_at: "2025-02-28T12:00:00Z"
updated_at: "2025-02-28T12:00:00Z"
```

### Collection Definition (`/data/collections/jaffa.yaml`)
```yaml
id: "jaffa"
name: "Jaffa Kit"
description: "Jaffa collection binder"
kit_id: "smalls"
label_config:
  inherit_kit_color: true        # Use kit's background color
  thumbnail_grid: [4, 5]         # Override default grid layout
created_at: "2025-02-28T12:00:00Z"
updated_at: "2025-02-28T12:00:00Z"
```

### Poster Metadata (`/data/posters/PANN-01.json`)
```json
{
  "id": "PANN-01",
  "title": "U.S. + ISRAEL HANDS OFF IRAN",
  "source": "National",
  "categories": ["Anti-War"],
  "tags": ["No War With Iran", "Color Collective Press"],
  "length": "13.75",
  "attribution": "",
  "source_link": "HANDS OFF IRAN 6-28-25A.png",
  "print_style": "Digital",
  "orientation": "portrait",  // auto-detected on upload
  "rotation": 0,  // user-adjustable rotation (0, 90, 180, 270)
  
  "overrides": {
    "price": null,           // null = use global default
    "seller": null,
    "slogans": null,
    "logo": null,
    "bug": {
      "top_frac": 0.15       // per-poster adjustment
    }
  },
  
  "price_tier": "standard",
  "collections": ["jaffa"],  // can belong to multiple collections
  
  "inventory": [  // history entries, newest first
    {
      "collection_id": "jaffa",
      "type": "counted",     // "counted" or "printed"
      "count": 15,
      "date": "2025-08-14",
      "recorded_by": "username",
      "recorded_at": "2025-08-14T10:00:00Z",
      "notes": "Initial import from CSV"
    },
    {
      "collection_id": "jaffa",
      "type": "printed",
      "count": 0,
      "date": "2025-08-19",
      "recorded_by": "system",
      "recorded_at": "2025-08-19T14:30:00Z"
    }
  ],
  
  "files": {
    "original": "/data/originals/PANN-01.pdf",
    "processed": "/data/processed/PANN-01.pdf",
    "thumbnail_web": "/data/thumbnails/web/PANN-01.jpg",      // 300px width
    "thumbnail_label": "/data/thumbnails/label/PANN-01.jpg",  // 600px width
    "thumbnail_preview": "/data/thumbnails/preview/PANN-01.jpg" // 150px width
  },
  
  "created_at": "2025-08-13T09:16:00Z",
  "updated_at": "2025-08-13T09:16:00Z",
  "created_by": "system",
  "updated_by": "system"
}
```

## Implementation Phases (10 Weeks Total)

### Phase 1: Development Environment & Foundation (Week 1)
**Goal**: Set up development environment with basic Flask application structure.

**Tasks**:
1. **Initialize Git repository** with proper `.gitignore`
2. **Create Dockerfile** using `python:3.11-alpine` base
3. **Set up docker-compose.yml** with volume mounts
4. **Create requirements.txt** with dependencies:
   - Flask, Jinja2, bcrypt, PyYAML, Pillow, qrcode[pil], pypdf, reportlab, pandas
5. **Build basic Flask app** with minimal routing
6. **Implement file-based authentication** with bcrypt
   - Default credentials: `admin` / `password` (with security warning)
   - Force password change on first login
7. **Create configuration loader** with YAML parsing
8. **Set up file locking system** for concurrent access
9. **Create basic templates** (login, dashboard, layout)

**Deliverables**:
- Working Docker container with Flask app
- Authentication system with user management
- Configuration loading system
- Basic web interface structure

### Phase 2: Data Models & Configuration System (Week 2)
**Goal**: Implement complete data models and configuration management.

**Tasks**:
1. **Implement YAML configuration classes**:
   - System configuration with validation
   - Template configuration with override resolution
   - Price tier management
2. **Create JSON data models**:
   - Poster metadata with override system
   - Kit/Collection hierarchy models
   - Inventory history tracking
3. **Build file watcher system** for config changes
4. **Implement JSON Schema validation** for poster metadata
5. **Create configuration editor interface** (admin-only)
6. **Add user management interface** (admin-only)
7. **Implement session management** with role-based permissions

**Deliverables**:
- Complete configuration system with validation
- Data models for all entities
- Configuration editor web interface
- User management interface

### Phase 3: Poster Processing Core Engine (Week 3-4)
**Goal**: Implement enhanced bug generation with rotation support.

**Tasks**:
1. **Port `bug.backup112325.py` to service module**:
   - Convert to class-based service
   - Add rotation support (90° for landscape)
   - Implement global + per-poster override system
2. **Create upload pipeline**:
   - File validation (200MB limit, format checking)
   - Orientation detection (portrait vs landscape)
   - Thumbnail generation at multiple sizes
   - Background processing queue
3. **Implement PDF processing**:
   - Convert to standardized 12x18" format with 0.5" margins
   - Append bug page with proper rotation
   - Store originals and processed versions
4. **Build thumbnail service**:
   - Generate web thumbnails (300px)
   - Generate label thumbnails (600px)
   - Generate preview thumbnails (150px)
   - Implement lazy loading and caching
5. **Create upload interface**:
   - Drag-and-drop file upload
   - Real-time preview with rotation controls
   - Metadata form with auto-fill from CSV (future)
   - Processing status indicator

**Deliverables**:
- Complete poster processing pipeline
- Upload interface with preview
- Thumbnail generation service
- Enhanced bug generation with rotation

### Phase 4: Web Interface - Core Features (Week 5-6)
**Goal**: Build comprehensive web interface for poster management.

**Tasks**:
1. **Dashboard implementation**:
   - System statistics (poster count, recent uploads)
   - Processing queue status
   - Quick upload button
2. **Poster browser interface**:
   - Grid view with thumbnails
   - Filtering by kit, collection, category, orientation
   - Search functionality (ID, title, tags)
   - Pagination (50+ posters per page)
   - Sort options (newest, ID, title)
3. **Poster detail view**:
   - Full metadata display and editing
   - Poster preview with zoom
   - Download options (original, processed, thumbnail)
   - Override configuration interface
   - Processing history
   - Reprocess button
4. **Collection management interface**:
   - Kit/Collection hierarchy browser
   - Add/remove posters from collections
   - Collection statistics
5. **Responsive design** for mobile/desktop

**Deliverables**:
- Complete web interface for poster management
- Dashboard with system overview
- Advanced filtering and search
- Responsive design

### Phase 5: Inventory & Collections Management (Week 7)
**Goal**: Implement inventory tracking with spreadsheet interface.

**Tasks**:
1. **Inventory data model**:
   - Track "counted" and "printed" states
   - Calculate sum: `last_counted - total_printed_since_count`
   - History tracking with audit trail
2. **Spreadsheet interface**:
   - Grid view: posters × collections
   - Bulk editing of counts
   - Color coding for low inventory
   - Export to CSV
3. **Inventory workflows**:
   - Counting interface (alphabetical by collection)
   - Print tracking interface
   - History view with charts
4. **Permission system**:
   - Only Contributors+ can submit counts
   - Admin can adjust any count
   - Viewers can only view counts
5. **Reporting interface**:
   - Inventory summaries by kit/collection
   - Reorder alerts
   - Print history reports

**Deliverables**:
- Complete inventory tracking system
- Spreadsheet interface for bulk editing
- Inventory reporting and alerts
- Permission-based access control

### Phase 6: Label Generation System (Week 8)
**Goal**: Implement automatic printable label generation for kits and collections.

**Tasks**:
1. **Kit label generator** (8.5×11" PDF):
   - Configurable background colors per kit
   - Icon/logo support (upload and management)
   - Collection listing with formatting
   - Custom text fields
   - Template-based design system
2. **Collection label generator** (11×17" PDF):
   - Thumbnail grid layout algorithm
   - Automatic pagination for large collections
   - Poster ID labels below thumbnails
   - Color coding matching kit
   - Grid optimization (4×5 default, adjustable)
3. **Label management interface**:
   - Preview labels before generation
   - Batch generation for all kits/collections
   - Download as PDF for printing
   - Caching system to avoid regeneration
4. **Template customization**:
   - Multiple label design templates
   - Color palette management
   - Font selection and sizing
5. **File storage for labels**:
   - Store generated PDFs in `/data/labels/`
   - Generate preview images for web
   - Cache invalidation on poster changes

**Deliverables**:
- Automatic label generation system
- Configurable label templates
- Web interface for label management
- Caching system for performance

### Phase 7: Advanced Features & Export (Week 9)
**Goal**: Implement export systems, backups, and batch operations.

**Tasks**:
1. **FTP export structure**:
   - Generate `/data/ftp_export/All/` (flat structure)
   - Generate `/data/ftp_export/Ordered/` (hierarchical: Kit → Collection)
   - Automatic sync on processing completion
   - Configurable export paths
2. **Backup system**:
   - Weekly automatic backups (cron job)
   - ZIP archive containing config + metadata
   - Retention policy (keep last N backups)
   - Manual backup trigger
   - Backup verification
3. **Batch operations**:
   - Bulk reprocess with new template
   - Export selected posters as ZIP
   - Batch metadata editing
   - Import/export to CSV
4. **Search functionality**:
   - Full-text search across all metadata
   - Advanced search filters
   - Search result export
5. **Performance optimization**:
   - Cache parsed YAML/JSON files
   - Background processing for expensive operations
   - Database indexing for large collections

**Deliverables**:
- FTP export system with dual structure
- Automated backup system
- Batch operation tools
- Enhanced search functionality

### Phase 8: Testing & Deployment (Week 10)
**Goal**: Final testing, optimization, and production deployment.

**Tasks**:
1. **End-to-end testing**:
   - Test all user workflows
   - Load testing with sample data
   - Edge case testing (large files, concurrent access)
2. **Security hardening**:
   - Input validation and sanitization
   - Rate limiting
   - Security headers
   - Logging and monitoring
3. **Performance optimization**:
   - Docker container optimization
   - Memory usage optimization
   - Response time improvements
4. **Documentation**:
   - User manual (web-based)
   - Administrator guide
   - API documentation (if applicable)
   - Deployment instructions
5. **Production deployment**:
   - Docker production configuration
   - Environment-specific settings
   - Backup strategy implementation
   - Monitoring setup

**Deliverables**:
- Fully tested production-ready system
- Complete documentation
- Optimized Docker deployment
- Monitoring and backup systems

## Technical Specifications

### Bug Generation with Rotation
**Portrait Posters**:
- Standard vertical bug page (existing logic from `bug.backup112325.py`)
- Centered on 12x18" page with 0.5" margins
- Configurable positioning via `bug_top_frac`

**Landscape Posters**:
- Bug page rotated 90° to match poster orientation
- Same formatting, scaling, and relative positioning
- Automatic content fitting using Pillow/ReportLab
- Maintain aspect ratio during rotation

**Implementation Details**:
```python
def generate_bug_page(poster_metadata, template_config, orientation="portrait"):
    # Generate bug image (existing logic)
    bug_image = build_bug_image(...)
    
    if orientation == "landscape":
        # Rotate 90° clockwise
        bug_image = bug_image.rotate(90, expand=True)
    
    # Convert to PDF page
    return bug_image_to_pdf_page(bug_image, orientation=orientation)
```

### Inventory Tracking System
**State Management**:
- `counted`: Physical count of posters in a collection
- `printed`: Posters removed for printing
- `sum`: Calculated as `last_counted - total_printed_since_last_count`

**Data Flow**:
1. User performs count → creates `counted` entry
2. Posters are printed → creates `printed` entry
3. System calculates current sum for display
4. History preserved for audit trail

**Permission Model**:
- **Viewers**: Can view counts only
- **Contributors**: Can submit counted/printed entries
- **Admins**: Can edit any count, adjust history

### Label Generation System
**Kit Labels (8.5×11")**:
```
┌─────────────────────────────────┐
│         [KIT ICON]              │
│         KIT NAME                │
│                                 │
│  Collections in this kit:       │
│  • Jaffa Collection             │
│  • Harlem Collection            │
│  • Palisades Collection         │
│                                 │
│  [Custom text field]            │
└─────────────────────────────────┘
```

**Collection Labels (11×17")**:
```
┌─────────────────────────────────┐
│      COLLECTION NAME            │
│      (Kit: Smalls)              │
│                                 │
│  ┌───┐  ┌───┐  ┌───┐  ┌───┐    │
│  │   │  │   │  │   │  │   │    │
│  │   │  │   │  │   │  │   │    │
│  └───┘  └───┘  └───┘  └───┘    │
│  PANN-01 PANN-02 PANN-03 PANN-04│
│                                 │
│  ┌───┐  ┌───┐  ┌───┐  ┌───┐    │
│  │   │  │   │  │   │  │   │    │
│  │   │  │   │  │   │  │   │    │
│  └───┘  └───┘  └───┘  └───┘    │
│  PANN-05 PANN-06 PANN-07 PANN-08│
│                                 │
└─────────────────────────────────┘
```

### FTP Export Structure
```
/data/ftp_export/
├── All/                    # Flat structure (all posters)
│   ├── PANN-01.pdf
│   ├── PANN-02.pdf
│   └── ...
└── Ordered/               # Hierarchical structure
    └── smalls/            # Kit
        ├── jaffa/         # Collection
        │   ├── PANN-01.pdf
        │   ├── PANN-14.pdf
        │   └── ...
        ├── harlem/
        │   ├── PBLN-01.pdf
        │   └── ...
        └── palisades/
            ├── PGEN-01.pdf
            └── ...
```

## Migration Strategy

### Phase 1: New System Deployment
1. Deploy empty system with Docker
2. Create initial configuration
3. Set up authentication with default admin user
4. Manually add new posters via web interface

### Phase 2: CSV Metadata Import (Future)
1. **Script**: `scripts/migrate_csv.py`
2. **Process**:
   - Parse `List Of All Posters - Sheet1.csv` (203 rows)
   - Convert to JSON metadata files
   - Extract inventory history from dated count columns
   - Map "Kit" column to collections
   - Drop "Column 11" and rating columns
3. **Output**: JSON files in `/data/posters/`

### Phase 3: Source File Migration (User-led)
1. User locates original source files
2. Upload via web interface or bulk import
3. System processes with new template
4. Generate thumbnails and labels

## Security Considerations

### Authentication
- **Default credentials**: `admin` / `password` with forced change on first login
- **Password hashing**: bcrypt with appropriate work factor
- **Session management**: Secure cookies with expiration
- **Rate limiting**: Prevent brute force attacks

### File Upload Security
- **File type validation**: Whitelist of allowed extensions
- **Size limits**: 200MB configurable limit
- **Virus scanning**: If possible within Docker environment
- **Path traversal prevention**: Secure file path handling

### Data Protection
- **Configuration files**: No sensitive data in version control
- **Backups**: Encrypted or stored in secure location
- **Logs**: No sensitive data in logs
- **Network**: Tailscale network for access control

## Performance Considerations

### Caching Strategy
1. **Configuration files**: Cache parsed YAML/JSON in memory
2. **Thumbnails**: Generate on first access, cache on filesystem
3. **Labels**: Cache generated PDFs, invalidate on data changes
4. **Metadata**: Cache frequently accessed poster metadata

### Background Processing
1. **Upload processing**: Queue system for PDF generation
2. **Thumbnail generation**: Background thread pool
3. **Label generation**: Async generation with progress tracking
4. **Backup creation**: Scheduled cron job

### Database Optimization
1. **File indexing**: Maintain index of poster metadata for fast search
2. **Pagination**: Limit results per page (50+ posters)
3. **Lazy loading**: Load thumbnails and previews on demand
4. **Connection pooling**: For future SQLite optimization

## Open Issues & Decisions

### Technical Decisions Pending
1. **File locking implementation**: Use `fcntl` vs `portalocker` library
2. **Background job queue**: Use Python `threading` vs `multiprocessing`
3. **Cache invalidation strategy**: File watchers vs timestamp checking
4. **Docker volume permissions**: User/group mapping for file access

### User Experience Decisions
1. **Label template variations**: Number of pre-designed templates
2. **Icon management**: Upload vs predefined icon library
3. **Color palette system**: Predefined palettes vs fully custom colors
4. **Export formats**: Additional formats beyond PDF (PNG, JPG)

### Migration Considerations
1. **CSV column mapping**: Exact mapping of all 31 columns to JSON fields
2. **Inventory history**: How to interpret dated count columns as history entries
3. **Source file location**: Strategy for locating original files
4. **Validation**: How to validate migrated data completeness

## Success Metrics

### Technical Metrics
- **Processing time**: < 2 minutes per poster upload
- **System uptime**: > 99.5% availability
- **Concurrent users**: Support 5-10 simultaneous users
- **File storage**: Efficient compression and organization

### User Satisfaction Metrics
- **Upload time**: < 5 minutes for new poster addition
- **Training time**: < 30 minutes for new users
- **Error rate**: Reduction in processing errors
- **User feedback**: Positive adoption and usage

### Business Metrics
- **Printing errors**: Reduction due to standardized process
- **Time savings**: Reduced manual processing time
- **Production volume**: Increased poster output
- **Cost savings**: From streamlined workflow

## Appendix

### Dependencies
```txt
Flask>=2.3.0
Jinja2>=3.1.0
bcrypt>=4.0.0
PyYAML>=6.0
Pillow>=10.0.0
qrcode[pil]>=7.4.0
pypdf>=3.0.0
reportlab>=4.0.0
pandas>=2.0.0  # For CSV migration only
```

### Default Configuration Values
```yaml
# system.yaml defaults
upload_limit_mb: 200
backup_retention: 4
session_timeout_minutes: 120

# template.yaml defaults
price: 12.00
bug_width_in: 2.0
bug_top_frac: 0.1
page_margin_in: 0.5
dpi: 300

# label templates defaults
kit_page_size: [8.5, 11]
collection_page_size: [11, 17]
thumbnail_grid: [4, 5]
```

### File Naming Conventions
- **Poster metadata**: `{POSTER_ID}.json` (e.g., `PANN-01.json`)
- **Processed PDF**: `{POSTER_ID}.pdf`
- **Original file**: `{POSTER_ID}_original.{ext}`
- **Web thumbnail**: `{POSTER_ID}_web.jpg` (300px width)
- **Label thumbnail**: `{POSTER_ID}_label.jpg` (600px width)
- **Preview thumbnail**: `{POSTER_ID}_preview.jpg` (150px width)

### Role Definitions
- **Viewer**: Browse, search, download posters. View inventory counts.
- **Contributor**: All viewer permissions + add/edit posters, submit inventory counts, generate labels.
- **Admin**: All contributor permissions + user management, configuration editing, system administration.

---

*This document serves as the comprehensive implementation plan for the Poster Management System. All development should follow this plan unless explicitly approved for deviation.*