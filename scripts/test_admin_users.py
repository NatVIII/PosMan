#!/usr/bin/env python3
"""Test admin user management pages."""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import config_loader

def test_admin_pages():
    """Test admin pages load."""
    config_loader.config_path = Path('./config')
    config_loader.reload_all()
    
    app = create_app()
    
    with app.test_client() as client:
        # Login as admin
        response = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'password'
        }, follow_redirects=True)
        if response.status_code != 200:
            print(f'Admin login failed: {response.status_code}')
            return False
        print('✓ Admin login successful')
        
        # Access user list page
        response = client.get('/auth/admin/users')
        if response.status_code != 200:
            print(f'User list page failed: {response.status_code}')
            return False
        print('✓ User list page loaded')
        
        # Access add user page
        response = client.get('/auth/admin/users/add')
        if response.status_code != 200:
            print(f'Add user page failed: {response.status_code}')
            return False
        print('✓ Add user page loaded')
        
        # Try to add a test user
        response = client.post('/auth/admin/users/add', data={
            'username': 'testuser',
            'password': 'testpassword123',
            'role': 'viewer',
            'force_password_change': False
        }, follow_redirects=True)
        if response.status_code != 200:
            print(f'Add user POST failed: {response.status_code}')
            # Maybe success redirects to user list (302)
            # Let's check if redirect
            if response.status_code == 302:
                print('  (Redirect detected)')
                # Follow redirect
                pass
        # Check if user appears in list
        response = client.get('/auth/admin/users')
        if b'testuser' not in response.data:
            print('✗ Test user not found after addition')
            return False
        print('✓ Test user added successfully')
        
        # Cleanup: delete test user via POST (we'll implement later)
        # For now, just pass
        
        print('\nAll admin page tests passed!')
        return True

if __name__ == '__main__':
    from pathlib import Path
    success = test_admin_pages()
    sys.exit(0 if success else 1)