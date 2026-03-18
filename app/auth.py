"""
Authentication and authorization for Poster Management System.

Handles user login, logout, session management, and role-based access control.
Users are stored in the system configuration YAML file.
"""

import functools
import logging
import secrets
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
import bcrypt
from typing import Optional
from .config import config_loader, ConfigError
from .poster import PosterManager

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__, url_prefix='/auth')


class User:
    """Represents a system user."""
    
    def __init__(self, user_data: dict):
        self.username = user_data.get('username')
        self.password_hash = user_data.get('password_hash')
        self.role = user_data.get('role', 'viewer')
        self.created_at = user_data.get('created_at')
        self.force_password_change = user_data.get('force_password_change', False)
        self.session_salt = user_data.get('session_salt', '')
        
    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'
    
    @property
    def is_contributor(self) -> bool:
        return self.role in ['contributor', 'admin']
    
    @property
    def is_viewer(self) -> bool:
        return self.role in ['viewer', 'contributor', 'admin']
    
    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash."""
        if not self.password_hash:
            return False
            
        try:
            # bcrypt hash should start with $2b$
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except ValueError:
            logger.error(f"Invalid password hash for user {self.username}")
            return False


def generate_session_salt() -> str:
    """Generate a random session salt."""
    return secrets.token_urlsafe(16)


def ensure_session_salt(username: str) -> str:
    """Ensure user has a session salt, generating one if missing. Returns the salt."""
    user_data = config_loader.get_user(username)
    if not user_data:
        raise ValueError(f"User {username} not found")
    
    session_salt = user_data.get('session_salt')
    if not session_salt:
        # Generate new salt and update user config
        session_salt = generate_session_salt()
        success = config_loader.update_user(username, {'session_salt': session_salt})
        if not success:
            logger.error(f"Failed to update session salt for user {username}")
            # Fallback to using generated salt for this session anyway
    return session_salt


def get_user(username: str) -> Optional[User]:
    """Get a User object by username."""
    user_data = config_loader.get_user(username)
    if user_data:
        return User(user_data)
    return None


def login_required(view):
    """Decorator that requires login."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


def role_required(role: str):
    """Decorator that requires specific role."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            
            role_hierarchy = ['viewer', 'contributor', 'admin']
            user_role_index = role_hierarchy.index(g.user.role)
            required_role_index = role_hierarchy.index(role)
            
            if user_role_index < required_role_index:
                flash('Insufficient permissions to access this page.', 'error')
                return redirect(url_for('main.index'))
                
            return view(**kwargs)
        return wrapped_view
    return decorator


def admin_required(view):
    """Decorator that requires admin role."""
    return role_required('admin')(view)


def contributor_required(view):
    """Decorator that requires contributor or admin role."""
    return role_required('contributor')(view)


def upload_allowed(view):
    """Decorator that checks if system is configured for uploads."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        from .config import config_loader
        
        if not config_loader.is_system_ready_for_uploads():
            flash('System not ready for uploads. Please configure taxonomy, ID templates, and bleed template first.', 'error')
            # Redirect to appropriate configuration page or dashboard
            return redirect(url_for('main.dashboard'))
        
        return view(**kwargs)
    return wrapped_view


@bp.before_app_request
def load_logged_in_user():
    """Load user from session before each request."""
    user_id = session.get('user_id')
    session_salt = session.get('session_salt')
    
    if user_id is None or session_salt is None:
        g.user = None
        # If user_id exists but no session_salt, clear session (migration)
        if user_id is not None and session_salt is None:
            session.clear()
            flash('Your session is invalid. Please log in again.', 'warning')
    else:
        g.user = get_user(user_id)
        
        # Check if user still exists in config and session salt matches
        if g.user is None:
            session.clear()
            flash('Your account no longer exists. Please contact an administrator.', 'warning')
        elif g.user.session_salt != session_salt:
            # Session salt mismatch - password may have been changed
            session.clear()
            g.user = None
            flash('Your session has expired. Please log in again.', 'warning')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    """Log in a user."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        
        user = get_user(username)
        
        if user is None:
            error = 'Invalid username or password.'
        elif not user.check_password(password):
            error = 'Invalid username or password.'
        
        if error is None:
            # Clear any existing session
            session.clear()
            
            # Ensure user has a session salt (generates if missing)
            try:
                session_salt = ensure_session_salt(username)
                session['session_salt'] = session_salt
            except Exception as e:
                logger.error(f"Failed to ensure session salt for {username}: {e}")
                # Continue without salt? Should not happen, but fallback
                session['session_salt'] = ''
            
            # user is guaranteed to be non-None at this point (error would have been set)
            assert user is not None
            session['user_id'] = user.username
            
            # Check if this is the default admin password (security warning)
            if username == 'admin' and password == 'password':
                flash('WARNING: You are using the default admin password. Please change it immediately!', 'danger')
                user.force_password_change = True
                # TODO: Implement password change requirement
            
            logger.info(f"User {username} logged in successfully")
            return redirect(url_for('main.index'))
        
        flash(error, 'error')
        logger.warning(f"Failed login attempt for user {username}")
    
    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    """Log out the current user."""
    username = session.get('user_id')
    session.clear()
    
    if username:
        logger.info(f"User {username} logged out")
        flash('You have been logged out.', 'info')
    
    return redirect(url_for('main.index'))


@bp.route('/change-password', methods=('GET', 'POST'))
@login_required
def change_password():
    """Change current user's password."""
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        error = None
        
        if not g.user.check_password(current_password):
            error = 'Current password is incorrect.'
        elif new_password != confirm_password:
            error = 'New passwords do not match.'
        elif len(new_password) < 8:
            error = 'Password must be at least 8 characters long.'
        elif new_password == current_password:
            error = 'New password must be different from current password.'
        
        if error is None:
            # Hash new password
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Generate new session salt to invalidate existing sessions
            new_session_salt = generate_session_salt()
            
            # Update password and session salt in configuration file
            success = config_loader.update_user(g.user.username, {
                "password_hash": hashed_password,
                "session_salt": new_session_salt,
                "force_password_change": False
            })
            
            if not success:
                flash('Failed to update password in configuration.', 'error')
                logger.error(f"Failed to update password for user {g.user.username}")
                return redirect(url_for('auth.change_password'))
            
            # Clear session to force re-login with new password
            session.clear()
            flash('Your password has been changed successfully. Please log in with your new password.', 'success')
            
            logger.info(f"Password changed for user {g.user.username}, sessions invalidated")
            return redirect(url_for('auth.login'))
        
        flash(error, 'error')
    
    return render_template('auth/change_password.html', user=g.user)


# Admin user management routes
@bp.route('/admin/users')
@admin_required
def user_list():
    """List all users (admin only)."""
    system_config = config_loader.load_system_config()
    users = system_config.get('users', [])
    return render_template('auth/admin/users.html', users=users)


@bp.route('/admin/users/add', methods=('GET', 'POST'))
@admin_required
def user_add():
    """Add a new user (admin only)."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        force_password_change = 'force_password_change' in request.form
        
        error = None
        
        if not username or not password:
            error = 'Username and password are required.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters long.'
        elif role not in ('viewer', 'contributor', 'admin'):
            error = 'Invalid role selected.'
        
        if error is None:
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_data = {
                'username': username,
                'password_hash': hashed_password,
                'role': role,
                'session_salt': generate_session_salt(),
                'force_password_change': force_password_change,
            }
            
            success = config_loader.add_user(user_data)
            if success:
                flash(f'User {username} added successfully.', 'success')
                return redirect(url_for('auth.user_list'))
            else:
                error = f'Username {username} already exists.'
        
        flash(error, 'error')
    
    return render_template('auth/admin/user_form.html', action='add')


@bp.route('/admin/users/<username>/edit', methods=('GET', 'POST'))
@admin_required
def user_edit(username):
    """Edit an existing user (admin only)."""
    user = config_loader.get_user(username)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.user_list'))
    
    if request.method == 'POST':
        new_username = request.form['username']
        role = request.form['role']
        force_password_change = 'force_password_change' in request.form
        reset_password = 'reset_password' in request.form
        new_password = request.form.get('new_password', '')
        
        error = None
        
        if not new_username:
            error = 'Username is required.'
        elif new_username != username and config_loader.get_user(new_username):
            error = f'Username {new_username} already exists.'
        elif role not in ('viewer', 'contributor', 'admin'):
            error = 'Invalid role selected.'
        elif reset_password and len(new_password) < 8:
            error = 'New password must be at least 8 characters long.'
        
        if error is None:
            updates = {
                'username': new_username,
                'role': role,
                'force_password_change': force_password_change,
            }
            
            # If username changed, we need to delete old and add new? Simpler: update_user can change username if we delete old and add new.
            # For simplicity, we'll delete old user and create new one.
            # We'll implement update_user to handle username change later.
            # For now, we'll just update other fields and keep same username.
            # Let's just update fields except username.
            # We'll update username separately via delete/add.
            if new_username != username:
                # Delete old user and create new with same data except username
                # For simplicity, we'll not allow username change in this iteration.
                error = 'Username change not yet supported.'
            else:
                if reset_password:
                    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    updates['password_hash'] = hashed_password
                    updates['session_salt'] = generate_session_salt()
                    updates['force_password_change'] = True
                
                success = config_loader.update_user(username, updates)
                if success:
                    flash(f'User {username} updated successfully.', 'success')
                    return redirect(url_for('auth.user_list'))
                else:
                    error = 'Failed to update user.'
        
        flash(error, 'error')
    
    return render_template('auth/admin/user_form.html', action='edit', user=user)


@bp.route('/admin/users/<username>/delete', methods=('POST',))
@admin_required
def user_delete(username):
    """Delete a user (admin only)."""
    if username == g.user.username:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('auth.user_list'))
    
    success = config_loader.delete_user(username)
    if success:
        flash(f'User {username} deleted successfully.', 'success')
    else:
        flash('User not found.', 'error')
    
    return redirect(url_for('auth.user_list'))


# Taxonomy management routes
@bp.route('/admin/taxonomy')
@admin_required
def taxonomy_list():
    """List all sources and categories (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    sources = taxonomy.get('sources', [])
    categories = taxonomy.get('categories', [])
    return render_template('auth/admin/taxonomy.html', 
                         sources=sources, 
                         categories=categories)


@bp.route('/admin/taxonomy/settings', methods=('GET', 'POST'))
@admin_required
def taxonomy_settings():
    """Configure taxonomy settings (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    
    if request.method == 'POST':
        try:
            source_length = int(request.form.get('source_code_length', '1'))
            category_length = int(request.form.get('category_code_length', '2'))
            
            error = None
            if source_length < 1 or source_length > 10:
                error = 'Source code length must be between 1 and 10.'
            elif category_length < 1 or category_length > 10:
                error = 'Category code length must be between 1 and 10.'
            
            if error is None:
                taxonomy['code_lengths'] = {
                    'sources': source_length,
                    'categories': category_length
                }
                config_loader.save_taxonomy_config(taxonomy)
                flash('Taxonomy settings updated successfully.', 'success')
                return redirect(url_for('auth.taxonomy_list'))
            
            flash(error, 'error')
        except ValueError:
            flash('Invalid number format for code lengths.', 'error')
    
    code_lengths = taxonomy.get('code_lengths', {'sources': 1, 'categories': 2})
    return render_template('auth/admin/taxonomy_settings.html',
                          source_code_length=code_lengths.get('sources', 1),
                          category_code_length=code_lengths.get('categories', 2))


@bp.route('/admin/taxonomy/sources/add', methods=('GET', 'POST'))
@admin_required
def source_add():
    """Add a new source (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    code_lengths = taxonomy.get('code_lengths', {'sources': 1, 'categories': 2})
    source_length = code_lengths.get('sources', 1)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        
        error = None
        if not name:
            error = 'Name is required.'
        elif not code:
            error = 'Code is required.'
        elif len(code) != source_length:
            error = f'Code must be exactly {source_length} character(s).'
        
        if error is None:
            taxonomy = config_loader.load_taxonomy_config()
            sources = taxonomy.get('sources', [])
            # Generate unique ID
            source_id = f"source_{len(sources) + 1:03d}"
            # Check for duplicate code
            if any(s['code'] == code for s in sources):
                error = f'Code "{code}" already exists.'
            else:
                new_source = {
                    'id': source_id,
                    'name': name,
                    'code': code,
                }
                sources.append(new_source)
                taxonomy['sources'] = sources
                config_loader.save_taxonomy_config(taxonomy)
                flash(f'Source "{name}" added successfully.', 'success')
                return redirect(url_for('auth.taxonomy_list'))
        
        flash(error, 'error')
    
    return render_template('auth/admin/source_form.html', action='add', source_length=source_length)


@bp.route('/admin/taxonomy/sources/<source_id>/edit', methods=('GET', 'POST'))
@admin_required
def source_edit(source_id):
    """Edit an existing source (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    code_lengths = taxonomy.get('code_lengths', {'sources': 1, 'categories': 2})
    source_length = code_lengths.get('sources', 1)
    
    # Find the source
    sources = taxonomy.get('sources', [])
    source = next((s for s in sources if s['id'] == source_id), None)
    if not source:
        flash(f'Source with ID "{source_id}" not found.', 'error')
        return redirect(url_for('auth.taxonomy_list'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        
        error = None
        if not name:
            error = 'Name is required.'
        elif not code:
            error = 'Code is required.'
        elif len(code) != source_length:
            error = f'Code must be exactly {source_length} character(s).'
        
        if error is None:
            taxonomy = config_loader.load_taxonomy_config()
            sources = taxonomy.get('sources', [])
            
            # Check for duplicate code (excluding current source)
            duplicate = any(s['code'] == code and s['id'] != source_id for s in sources)
            if duplicate:
                error = f'Code "{code}" already exists.'
            else:
                # Update source
                for s in sources:
                    if s['id'] == source_id:
                        s['name'] = name
                        s['code'] = code
                        break
                
                taxonomy['sources'] = sources
                config_loader.save_taxonomy_config(taxonomy)
                flash(f'Source "{name}" updated successfully.', 'success')
                return redirect(url_for('auth.taxonomy_list'))
        
        flash(error, 'error')
        # Re-render with submitted values
        source = {'id': source_id, 'name': name, 'code': code}
    
    return render_template('auth/admin/source_form.html', 
                          action='edit', 
                          source=source,
                          source_length=source_length)


@bp.route('/admin/taxonomy/sources/<source_id>/delete', methods=('POST',))
@admin_required
def source_delete(source_id):
    """Delete a source (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    sources = taxonomy.get('sources', [])
    
    # Find the source
    source = next((s for s in sources if s['id'] == source_id), None)
    if not source:
        flash(f'Source with ID "{source_id}" not found.', 'error')
        return redirect(url_for('auth.taxonomy_list'))
    
    # Check if source is used by any posters
    try:
        data_path = current_app.config.get('DATA_PATH', './data')
        poster_manager = PosterManager(data_path)
        all_posters = poster_manager.storage.list_all()
        used_by = []
        
        for poster_id in all_posters:
            poster = poster_manager.storage.load(poster_id)
            if poster and poster.get('source') == source_id:
                used_by.append(poster_id)
        
        if used_by:
            flash(f'Cannot delete source "{source["name"]}". It is used by {len(used_by)} poster(s).', 'error')
            return redirect(url_for('auth.taxonomy_list'))
    except Exception as e:
        logger.warning(f"Failed to check poster usage for source {source_id}: {e}")
        # Continue anyway, but warn user
        flash(f'Warning: Could not verify if source is in use. Proceeding with deletion.', 'warning')
    
    # Remove source
    sources = [s for s in sources if s['id'] != source_id]
    taxonomy['sources'] = sources
    config_loader.save_taxonomy_config(taxonomy)
    
    flash(f'Source "{source["name"]}" deleted successfully.', 'success')
    return redirect(url_for('auth.taxonomy_list'))


@bp.route('/admin/taxonomy/categories/add', methods=('GET', 'POST'))
@admin_required
def category_add():
    """Add a new category (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    code_lengths = taxonomy.get('code_lengths', {'sources': 1, 'categories': 2})
    category_length = code_lengths.get('categories', 2)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        
        error = None
        if not name:
            error = 'Name is required.'
        elif not code:
            error = 'Code is required.'
        elif len(code) != category_length:
            error = f'Code must be exactly {category_length} character(s).'
        
        if error is None:
            taxonomy = config_loader.load_taxonomy_config()
            categories = taxonomy.get('categories', [])
            # Generate unique ID
            category_id = f"category_{len(categories) + 1:03d}"
            # Check for duplicate code
            if any(c['code'] == code for c in categories):
                error = f'Code "{code}" already exists.'
            else:
                new_category = {
                    'id': category_id,
                    'name': name,
                    'code': code,
                }
                categories.append(new_category)
                taxonomy['categories'] = categories
                config_loader.save_taxonomy_config(taxonomy)
                flash(f'Category "{name}" added successfully.', 'success')
                return redirect(url_for('auth.taxonomy_list'))
        
        flash(error, 'error')
    
    return render_template('auth/admin/category_form.html', action='add', category_length=category_length)


@bp.route('/admin/taxonomy/categories/<category_id>/edit', methods=('GET', 'POST'))
@admin_required
def category_edit(category_id):
    """Edit an existing category (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    code_lengths = taxonomy.get('code_lengths', {'sources': 1, 'categories': 2})
    category_length = code_lengths.get('categories', 2)
    
    # Find the category
    categories = taxonomy.get('categories', [])
    category = next((c for c in categories if c['id'] == category_id), None)
    if not category:
        flash(f'Category with ID "{category_id}" not found.', 'error')
        return redirect(url_for('auth.taxonomy_list'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        
        error = None
        if not name:
            error = 'Name is required.'
        elif not code:
            error = 'Code is required.'
        elif len(code) != category_length:
            error = f'Code must be exactly {category_length} character(s).'
        
        if error is None:
            taxonomy = config_loader.load_taxonomy_config()
            categories = taxonomy.get('categories', [])
            
            # Check for duplicate code (excluding current category)
            duplicate = any(c['code'] == code and c['id'] != category_id for c in categories)
            if duplicate:
                error = f'Code "{code}" already exists.'
            else:
                # Update category
                for c in categories:
                    if c['id'] == category_id:
                        c['name'] = name
                        c['code'] = code
                        break
                
                taxonomy['categories'] = categories
                config_loader.save_taxonomy_config(taxonomy)
                flash(f'Category "{name}" updated successfully.', 'success')
                return redirect(url_for('auth.taxonomy_list'))
        
        flash(error, 'error')
        # Re-render with submitted values
        category = {'id': category_id, 'name': name, 'code': code}
    
    return render_template('auth/admin/category_form.html', 
                          action='edit', 
                          category=category,
                          category_length=category_length)


@bp.route('/admin/taxonomy/categories/<category_id>/delete', methods=('POST',))
@admin_required
def category_delete(category_id):
    """Delete a category (admin only)."""
    taxonomy = config_loader.load_taxonomy_config()
    categories = taxonomy.get('categories', [])
    
    # Find the category
    category = next((c for c in categories if c['id'] == category_id), None)
    if not category:
        flash(f'Category with ID "{category_id}" not found.', 'error')
        return redirect(url_for('auth.taxonomy_list'))
    
    # Check if category is used by any posters
    try:
        data_path = current_app.config.get('DATA_PATH', './data')
        poster_manager = PosterManager(data_path)
        all_posters = poster_manager.storage.list_all()
        used_by = []
        
        for poster_id in all_posters:
            poster = poster_manager.storage.load(poster_id)
            if poster and poster.get('categories') == category_id:
                used_by.append(poster_id)
        
        if used_by:
            flash(f'Cannot delete category "{category["name"]}". It is used by {len(used_by)} poster(s).', 'error')
            return redirect(url_for('auth.taxonomy_list'))
    except Exception as e:
        logger.warning(f"Failed to check poster usage for category {category_id}: {e}")
        # Continue anyway, but warn user
        flash(f'Warning: Could not verify if category is in use. Proceeding with deletion.', 'warning')
    
    # Remove category
    categories = [c for c in categories if c['id'] != category_id]
    taxonomy['categories'] = categories
    config_loader.save_taxonomy_config(taxonomy)
    
    flash(f'Category "{category["name"]}" deleted successfully.', 'success')
    return redirect(url_for('auth.taxonomy_list'))


@bp.route('/admin/bleed-template', methods=('GET', 'POST'))
@admin_required
def bleed_template_edit():
    """Edit bleed template configuration (admin only)."""
    bleed_config = config_loader.load_bleed_template_config()
    # Extract inner template (config file may have 'bleed_template' key)
    inner = bleed_config.get('bleed_template', {})
    
    if request.method == 'POST':
        try:
            # Parse float values
            paper_width = float(request.form.get('paper_width', '0'))
            paper_height = float(request.form.get('paper_height', '0'))
            bleed_margin = float(request.form.get('bleed_margin', '0'))
            safe_margin = float(request.form.get('safe_margin', '0'))
            trim_top = float(request.form.get('trim_top', '0'))
            trim_bottom = float(request.form.get('trim_bottom', '0'))
            trim_left = float(request.form.get('trim_left', '0'))
            trim_right = float(request.form.get('trim_right', '0'))
            
            # Parse standard lengths (comma-separated)
            lengths_str = request.form.get('standard_lengths', '')
            standard_lengths = [float(l.strip()) for l in lengths_str.split(',') if l.strip()]
            
            # Validate
            error = None
            if paper_width <= 0 or paper_height <= 0:
                error = 'Paper dimensions must be positive numbers.'
            elif bleed_margin < 0:
                error = 'Bleed margin cannot be negative.'
            elif safe_margin < 0:
                error = 'Safe margin cannot be negative.'
            elif trim_top < 0:
                error = 'Trim top margin cannot be negative.'
            elif trim_bottom < 0:
                error = 'Trim bottom margin cannot be negative.'
            elif trim_left < 0:
                error = 'Trim left margin cannot be negative.'
            elif trim_right < 0:
                error = 'Trim right margin cannot be negative.'
            
            if error is None:
                new_template = {
                    'paper_width': paper_width,
                    'paper_height': paper_height,
                    'bleed_margin': bleed_margin,
                    'safe_margin': safe_margin,
                    'trim_top': trim_top,
                    'trim_bottom': trim_bottom,
                    'trim_left': trim_left,
                    'trim_right': trim_right,
                    'standard_lengths': standard_lengths,
                }
                # Save with top-level 'bleed_template' key
                config_loader.save_bleed_template_config({'bleed_template': new_template})
                flash('Bleed template updated successfully.', 'success')
                return redirect(url_for('auth.bleed_template_edit'))
        
        except ValueError as e:
            error = 'Invalid numeric value entered.'
        
        if error:
            flash(error, 'error')
    
    # Prepare data for template
    paper_width = inner.get('paper_width', 12.0)
    paper_height = inner.get('paper_height', 18.0)
    bleed_margin = inner.get('bleed_margin', 0.125)
    safe_margin = inner.get('safe_margin', 0.25)
    trim_top = inner.get('trim_top', 0.5)
    trim_bottom = inner.get('trim_bottom', 0.5)
    trim_left = inner.get('trim_left', 0.5)
    trim_right = inner.get('trim_right', 0.5)
    standard_lengths = inner.get('standard_lengths', [13.75, 16.9, 19.0])
    
    return render_template('auth/admin/bleed_template.html',
                         paper_width=paper_width,
                         paper_height=paper_height,
                         bleed_margin=bleed_margin,
                         safe_margin=safe_margin,
                         trim_top=trim_top,
                         trim_bottom=trim_bottom,
                         trim_left=trim_left,
                         trim_right=trim_right,
                         standard_lengths=', '.join(str(l) for l in standard_lengths))


@bp.route('/admin/id-templates', methods=('GET', 'POST'))
@admin_required
def id_templates_edit():
    """Edit ID template configuration (admin only)."""
    id_templates = config_loader.load_id_templates_config()
    templates = id_templates.get('templates', [])
    default_template = next((t for t in templates if t.get('default', False)), None)
    
    if request.method == 'POST':
        pattern = request.form.get('pattern', '').strip()
        description = request.form.get('description', '').strip()
        
        error = None
        if not pattern:
            error = 'Pattern is required.'
        elif '{{seq' not in pattern:
            error = 'Pattern must contain a {{seq}} variable for sequential numbering.'
        
        if error is None:
            # Update or create default template
            if default_template:
                default_template['pattern'] = pattern
                default_template['description'] = description
            else:
                default_template = {
                    'id': 'default',
                    'pattern': pattern,
                    'description': description,
                    'default': True,
                }
                templates.append(default_template)
            
            # Ensure only one default
            for t in templates:
                t['default'] = (t.get('id') == default_template.get('id'))
            
            id_templates['templates'] = templates
            config_loader.save_id_templates_config(id_templates)
            flash('ID template updated successfully.', 'success')
            return redirect(url_for('auth.id_templates_edit'))
        
        flash(error, 'error')
    
    pattern = default_template.get('pattern', '') if default_template else ''
    description = default_template.get('description', '') if default_template else ''
    
    return render_template('auth/admin/id_templates.html',
                         pattern=pattern,
                         description=description)