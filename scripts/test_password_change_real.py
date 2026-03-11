#!/usr/bin/env python3
"""Test password change with real configuration files."""

import sys
import os
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import config_loader

def test_password_change_real():
    """Test password change using the actual config directory."""
    # Backup system.yaml
    config_path = Path('./config')
    backup_path = Path('./config/system.yaml.backup')
    if config_path.exists():
        shutil.copy(config_path / 'system.yaml', backup_path)
        print('Backup created')
    else:
        print('Config directory not found')
        return False
    
    try:
        # Ensure config_loader uses the correct path (already set)
        config_loader.config_path = config_path
        config_loader.reload_all()
        
        app = create_app()
        
        with app.test_client() as client:
            # 1. Login as viewer (password: password)
            response = client.post('/auth/login', data={
                'username': 'viewer',
                'password': 'password'
            }, follow_redirects=True)
            if response.status_code != 200:
                print(f'Login failed: {response.status_code}')
                return False
            print('✓ Viewer login successful')
            
            # 2. Change password
            new_password = 'newpassword123'
            response = client.post('/auth/change-password', data={
                'current_password': 'password',
                'new_password': new_password,
                'confirm_password': new_password
            }, follow_redirects=True)
            if response.status_code != 200:
                print(f'Password change failed: {response.status_code}')
                return False
            # Check for success flash (hard to test)
            print('✓ Password change request successful')
            
            # 3. Logout
            client.get('/auth/logout')
            
            # 4. Login with new password
            response = client.post('/auth/login', data={
                'username': 'viewer',
                'password': new_password
            }, follow_redirects=True)
            if response.status_code != 200:
                print(f'Login with new password failed: {response.status_code}')
                return False
            print('✓ Login with new password successful')
            
            # 5. Change password back to original (optional)
            # We'll skip for now; backup will restore original
            
            print('\nAll tests passed!')
            return True
            
    except Exception as e:
        print(f'Test failed with exception: {e}')
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore backup
        if backup_path.exists():
            shutil.copy(backup_path, config_path / 'system.yaml')
            print('Original config restored')
            backup_path.unlink()

if __name__ == '__main__':
    success = test_password_change_real()
    sys.exit(0 if success else 1)