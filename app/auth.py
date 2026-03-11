"""
Authentication and authorization for Poster Management System.

Handles user login, logout, session management, and role-based access control.
Users are stored in the system configuration YAML file.
"""

import functools
import logging
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
import bcrypt
from .config import config_loader, ConfigError

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
        except (ValueError, bcrypt.exceptions.SaltValidationError):
            logger.error(f"Invalid password hash for user {self.username}")
            return False


def get_user(username: str) -> User:
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


@bp.before_app_request
def load_logged_in_user():
    """Load user from session before each request."""
    user_id = session.get('user_id')
    
    if user_id is None:
        g.user = None
    else:
        g.user = get_user(user_id)
        
        # Check if user still exists in config
        if g.user is None:
            session.clear()
            flash('Your account no longer exists. Please contact an administrator.', 'warning')


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
            
            # Update password in configuration file
            success = config_loader.update_user(g.user.username, {
                "password_hash": hashed_password,
                "force_password_change": False
            })
            
            if not success:
                flash('Failed to update password in configuration.', 'error')
                logger.error(f"Failed to update password for user {g.user.username}")
                return redirect(url_for('auth.change_password'))
            
            flash('Your password has been changed successfully.', 'success')
            
            # Clear force password change flag
            g.user.force_password_change = False
            
            logger.info(f"Password change requested for user {g.user.username}")
            return redirect(url_for('main.index'))
        
        flash(error, 'error')
    
    return render_template('auth/change_password.html')


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