"""
Main routes for Poster Management System.

Handles dashboard, index, and other main pages.
"""

import logging
from flask import Blueprint, render_template, g, flash, current_app, redirect, url_for
from .auth import login_required

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Home page - redirects to dashboard if logged in, otherwise shows landing."""
    if g.user:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with system overview."""
    try:
        # Import here to avoid circular imports
        from .poster import PosterManager
        from pathlib import Path
        
        data_path = Path(current_app.config.get('DATA_PATH', './data'))
        poster_manager = PosterManager(data_path)
        stats = poster_manager.get_stats()
        
    except Exception as e:
        logger.error(f"Failed to load poster stats: {e}")
        stats = {
            'total_posters': 0,
            'total_inventory': 0,
            'kits': 0,
            'collections': 0,
            'recent_uploads': [],
        }
    
    return render_template('dashboard.html', user=g.user, stats=stats)


@bp.route('/about')
def about():
    """About page with system information."""
    system_name = current_app.config.get('SYSTEM_NAME', 'Poster Management System')
    version = '1.0.0-dev'
    
    return render_template('about.html', 
                          system_name=system_name, 
                          version=version,
                          user=g.user if hasattr(g, 'user') else None)


@bp.route('/system-info')
@login_required
def system_info():
    """System information page (admin only)."""
    # TODO: Add more system information
    config_info = {
        'system_name': current_app.config.get('SYSTEM_NAME'),
        'upload_limit_mb': current_app.config.get('MAX_CONTENT_LENGTH') // (1024 * 1024),
        'ftp_export_path': current_app.config.get('FTP_EXPORT_PATH'),
        'backup_path': current_app.config.get('BACKUP_PATH'),
        'backup_retention': current_app.config.get('BACKUP_RETENTION'),
    }
    
    return render_template('system_info.html', 
                          config=config_info,
                          user=g.user)


# Error handlers
@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html', user=g.user if hasattr(g, 'user') else None), 404


@bp.app_errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html', user=g.user if hasattr(g, 'user') else None), 500


@bp.app_errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html', user=g.user if hasattr(g, 'user') else None), 403