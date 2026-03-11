"""
Poster Management System - Flask application factory.
"""

import os
import logging
from flask import Flask
from .config import config_loader, ConfigError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    
    # Default configuration
    app.config.from_mapping(
        SECRET_KEY='dev',  # Override in production
        MAX_CONTENT_LENGTH=200 * 1024 * 1024,  # 200MB upload limit
        SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
    
    if test_config is None:
        # Load configuration from YAML files
        try:
            system_config = config_loader.load_system_config()
            
            # Apply system configuration to app config
            if 'system' in system_config:
                sys_cfg = system_config['system']
                app.config['SYSTEM_NAME'] = sys_cfg.get('name', 'Poster Management System')
                app.config['DATA_PATH'] = sys_cfg.get('data_path', '/data')
                app.config['FTP_EXPORT_PATH'] = sys_cfg.get('ftp_export_path', '/data/ftp_export')
                app.config['BACKUP_PATH'] = sys_cfg.get('backup_path', '/backups')
                app.config['BACKUP_RETENTION'] = sys_cfg.get('backup_retention', 4)
                app.config['MAX_CONTENT_LENGTH'] = sys_cfg.get('upload_limit_mb', 200) * 1024 * 1024
                
            logger.info("Configuration loaded successfully")
            
        except ConfigError as e:
            logger.error(f"Failed to load configuration: {e}")
            # Use defaults but log warning
            logger.warning("Using default configuration due to load error")
    else:
        # Load test configuration
        app.config.from_mapping(test_config)
    
    # Ensure necessary directories exist
    try:
        # Config directory (where YAML files are stored)
        os.makedirs(str(config_loader.config_path), exist_ok=True)
        
        # Data directories
        data_path = app.config.get('DATA_PATH', '/data')
        backup_path = app.config.get('BACKUP_PATH', '/backups')
        ftp_export_path = app.config.get('FTP_EXPORT_PATH', '/data/ftp_export')
        
        os.makedirs(data_path, exist_ok=True)
        os.makedirs(backup_path, exist_ok=True)
        os.makedirs(os.path.join(data_path, 'originals'), exist_ok=True)
        os.makedirs(os.path.join(data_path, 'processed'), exist_ok=True)
        os.makedirs(os.path.join(data_path, 'thumbnails'), exist_ok=True)
        os.makedirs(ftp_export_path, exist_ok=True)
        os.makedirs(os.path.join(ftp_export_path, 'All'), exist_ok=True)
        os.makedirs(os.path.join(ftp_export_path, 'Ordered'), exist_ok=True)
        
        logger.info(f"Directories created/verified: {data_path}, {backup_path}, {ftp_export_path}")
    except OSError as e:
        logger.error(f"Failed to create directories: {e}")
    
    # Register blueprints/views
    from . import auth, routes, poster_routes
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(routes.bp)
    app.register_blueprint(poster_routes.bp)
    
    # Add template filters
    @app.template_filter('format_price')
    def format_price(value):
        """Format price as currency."""
        try:
            return f"${float(value):.2f}"
        except (ValueError, TypeError):
            return value
    
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='medium'):
        """Format datetime string."""
        if not value:
            return ''
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if format == 'short':
                return dt.strftime('%Y-%m-%d')
            elif format == 'time':
                return dt.strftime('%H:%M')
            else:
                return dt.strftime('%Y-%m-%d %H:%M')
        except (ValueError, TypeError):
            return value
    
    @app.context_processor
    def inject_current_year():
        import datetime
        return {'current_year': datetime.datetime.now().year}
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return 'OK', 200
    
    logger.info("Poster Management System application created")
    return app