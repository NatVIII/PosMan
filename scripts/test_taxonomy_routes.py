#!/usr/bin/env python3
"""Test taxonomy edit/delete routes using Flask test client."""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import config_loader

def test_taxonomy_routes():
    """Test taxonomy edit/delete routes."""
    # Create temporary config directory
    temp_dir = tempfile.mkdtemp(prefix='pms_test_')
    print(f"Using temporary config directory: {temp_dir}")
    
    # Copy config files from original config directory
    config_source = Path('./config')
    for config_file in config_source.glob('*.yaml'):
        shutil.copy(config_file, temp_dir)
    
    # Set config path
    config_loader.config_path = Path(temp_dir)
    config_loader.reload_all()
    
    # Create app
    app = create_app()
    
    try:
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
            
            # Access taxonomy list page
            response = client.get('/auth/admin/taxonomy')
            if response.status_code != 200:
                print(f'Taxonomy list page failed: {response.status_code}')
                return False
            print('✓ Taxonomy list page loaded')
            
            # Add a test source
            response = client.post('/auth/admin/taxonomy/sources/add', data={
                'name': 'Test Source',
                'code': 'T'
            }, follow_redirects=True)
            if response.status_code != 200:
                # Might be redirect
                if response.status_code != 302:
                    print(f'Add source failed: {response.status_code}')
                    return False
            print('✓ Test source added')
            
            # Get source ID from taxonomy config
            taxonomy = config_loader.load_taxonomy_config()
            sources = taxonomy.get('sources', [])
            test_source = next((s for s in sources if s['code'] == 'T'), None)
            if not test_source:
                print('✗ Test source not found after addition')
                return False
            source_id = test_source['id']
            print(f'  Source ID: {source_id}')
            
            # Test source edit page
            response = client.get(f'/auth/admin/taxonomy/sources/{source_id}/edit')
            if response.status_code != 200:
                print(f'Source edit page failed: {response.status_code}')
                return False
            print('✓ Source edit page loaded')
            
            # Edit source
            response = client.post(f'/auth/admin/taxonomy/sources/{source_id}/edit', data={
                'name': 'Test Source Updated',
                'code': 'T'
            }, follow_redirects=True)
            if response.status_code != 200 and response.status_code != 302:
                print(f'Source edit POST failed: {response.status_code}')
                return False
            print('✓ Source edit successful')
            
            # Verify update
            taxonomy = config_loader.load_taxonomy_config()
            sources = taxonomy.get('sources', [])
            updated_source = next((s for s in sources if s['id'] == source_id), None)
            if not updated_source or updated_source['name'] != 'Test Source Updated':
                print('✗ Source not updated correctly')
                return False
            print('✓ Source verified updated')
            
            # Add a test category
            response = client.post('/auth/admin/taxonomy/categories/add', data={
                'name': 'Test Category',
                'code': 'TC'
            }, follow_redirects=True)
            if response.status_code != 200 and response.status_code != 302:
                print(f'Add category failed: {response.status_code}')
                return False
            print('✓ Test category added')
            
            # Get category ID
            taxonomy = config_loader.load_taxonomy_config()
            categories = taxonomy.get('categories', [])
            test_category = next((c for c in categories if c['code'] == 'TC'), None)
            if not test_category:
                print('✗ Test category not found after addition')
                return False
            category_id = test_category['id']
            print(f'  Category ID: {category_id}')
            
            # Test category edit page
            response = client.get(f'/auth/admin/taxonomy/categories/{category_id}/edit')
            if response.status_code != 200:
                print(f'Category edit page failed: {response.status_code}')
                return False
            print('✓ Category edit page loaded')
            
            # Edit category
            response = client.post(f'/auth/admin/taxonomy/categories/{category_id}/edit', data={
                'name': 'Test Category Updated',
                'code': 'TC'
            }, follow_redirects=True)
            if response.status_code != 200 and response.status_code != 302:
                print(f'Category edit POST failed: {response.status_code}')
                return False
            print('✓ Category edit successful')
            
            # Verify update
            taxonomy = config_loader.load_taxonomy_config()
            categories = taxonomy.get('categories', [])
            updated_category = next((c for c in categories if c['id'] == category_id), None)
            if not updated_category or updated_category['name'] != 'Test Category Updated':
                print('✗ Category not updated correctly')
                return False
            print('✓ Category verified updated')
            
            # Test source delete (should succeed since not used)
            response = client.post(f'/auth/admin/taxonomy/sources/{source_id}/delete', 
                                  follow_redirects=True)
            if response.status_code != 200 and response.status_code != 302:
                print(f'Source delete failed: {response.status_code}')
                return False
            print('✓ Source delete successful')
            
            # Verify source deleted
            taxonomy = config_loader.load_taxonomy_config()
            sources = taxonomy.get('sources', [])
            deleted_source = next((s for s in sources if s['id'] == source_id), None)
            if deleted_source:
                print('✗ Source not deleted')
                return False
            print('✓ Source verified deleted')
            
            # Test category delete (should succeed since not used)
            response = client.post(f'/auth/admin/taxonomy/categories/{category_id}/delete',
                                  follow_redirects=True)
            if response.status_code != 200 and response.status_code != 302:
                print(f'Category delete failed: {response.status_code}')
                return False
            print('✓ Category delete successful')
            
            # Verify category deleted
            taxonomy = config_loader.load_taxonomy_config()
            categories = taxonomy.get('categories', [])
            deleted_category = next((c for c in categories if c['id'] == category_id), None)
            if deleted_category:
                print('✗ Category not deleted')
                return False
            print('✓ Category verified deleted')
            
            print('\nAll taxonomy route tests passed!')
            return True
    finally:
        # Cleanup temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"Cleaned up temporary directory: {temp_dir}")

if __name__ == '__main__':
    success = test_taxonomy_routes()
    sys.exit(0 if success else 1)