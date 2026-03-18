#!/usr/bin/env python3
"""Test taxonomy edit and delete functionality."""

import os
import sys
import tempfile
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_taxonomy_edit_delete():
    """Test editing and deleting sources and categories."""
    print("Testing taxonomy edit/delete functionality...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_path = tmpdir / "config"
        data_path = tmpdir / "data"
        config_path.mkdir()
        data_path.mkdir()
        
        # Create initial configuration with one source and one category
        taxonomy_config = {
            'sources': [
                {'id': 'source_001', 'name': 'Original Source', 'code': 'OS'}
            ],
            'categories': [
                {'id': 'category_001', 'name': 'Original Category', 'code': 'OC'}
            ],
            'code_lengths': {'sources': 2, 'categories': 2}
        }
        
        pattern = '{{source_code}}{{category_code}}-{{seq:04d}}'
        id_templates_config = {
            'templates': [
                {
                    'id': 'default',
                    'pattern': pattern,
                    'description': 'Default',
                    'default': True
                }
            ],
            'counters': {pattern: 1}
        }
        
        bleed_template_config = {
            'bleed_template': {
                'paper_width': 12.0,
                'paper_height': 18.0,
                'bleed_margin': 0.125,
                'safe_margin': 0.25,
                'standard_lengths': [13.75]
            }
        }
        
        (config_path / 'taxonomy.yaml').write_text(yaml.dump(taxonomy_config))
        (config_path / 'id_templates.yaml').write_text(yaml.dump(id_templates_config))
        (config_path / 'bleed_template.yaml').write_text(yaml.dump(bleed_template_config))
        
        os.environ['CONFIG_PATH'] = str(config_path)
        
        # Import modules after setting config path
        import importlib
        import app.config
        import app.auth
        
        importlib.reload(app.config)
        importlib.reload(app.auth)
        
        from app.config import config_loader
        
        # Test 1: Load initial configuration
        taxonomy = config_loader.load_taxonomy_config()
        assert len(taxonomy['sources']) == 1
        assert len(taxonomy['categories']) == 1
        print("✓ Initial config loaded")
        
        # Test 2: Edit source (simulate update)
        # Create a copy of taxonomy with edited source
        edited_taxonomy = taxonomy.copy()
        for source in edited_taxonomy['sources']:
            if source['id'] == 'source_001':
                source['name'] = 'Updated Source'
                source['code'] = 'US'
                break
        
        config_loader.save_taxonomy_config(edited_taxonomy)
        
        # Reload and verify
        reloaded = config_loader.load_taxonomy_config()
        updated_source = next(s for s in reloaded['sources'] if s['id'] == 'source_001')
        assert updated_source['name'] == 'Updated Source'
        assert updated_source['code'] == 'US'
        print("✓ Source edit works")
        
        # Test 3: Edit category (simulate update)
        edited_taxonomy = reloaded.copy()
        for category in edited_taxonomy['categories']:
            if category['id'] == 'category_001':
                category['name'] = 'Updated Category'
                category['code'] = 'UC'
                break
        
        config_loader.save_taxonomy_config(edited_taxonomy)
        
        # Reload and verify
        reloaded = config_loader.load_taxonomy_config()
        updated_category = next(c for c in reloaded['categories'] if c['id'] == 'category_001')
        assert updated_category['name'] == 'Updated Category'
        assert updated_category['code'] == 'UC'
        print("✓ Category edit works")
        
        # Test 4: Delete source (when not in use)
        # First add another source to delete
        edited_taxonomy = reloaded.copy()
        edited_taxonomy['sources'].append({
            'id': 'source_002',
            'name': 'Temp Source',
            'code': 'TS'
        })
        config_loader.save_taxonomy_config(edited_taxonomy)
        
        # Now delete it
        edited_taxonomy = config_loader.load_taxonomy_config()
        edited_taxonomy['sources'] = [s for s in edited_taxonomy['sources'] if s['id'] != 'source_002']
        config_loader.save_taxonomy_config(edited_taxonomy)
        
        # Verify deletion
        reloaded = config_loader.load_taxonomy_config()
        source_ids = [s['id'] for s in reloaded['sources']]
        assert 'source_002' not in source_ids
        assert len(reloaded['sources']) == 1
        print("✓ Source delete works")
        
        # Test 5: Delete category (when not in use)
        # Add another category to delete
        edited_taxonomy = reloaded.copy()
        edited_taxonomy['categories'].append({
            'id': 'category_002',
            'name': 'Temp Category',
            'code': 'TC'
        })
        config_loader.save_taxonomy_config(edited_taxonomy)
        
        # Now delete it
        edited_taxonomy = config_loader.load_taxonomy_config()
        edited_taxonomy['categories'] = [c for c in edited_taxonomy['categories'] if c['id'] != 'category_002']
        config_loader.save_taxonomy_config(edited_taxonomy)
        
        # Verify deletion
        reloaded = config_loader.load_taxonomy_config()
        category_ids = [c['id'] for c in reloaded['categories']]
        assert 'category_002' not in category_ids
        assert len(reloaded['categories']) == 1
        print("✓ Category delete works")
        
        # Test 6: Verify system still ready for uploads
        assert config_loader.is_system_ready_for_uploads()
        print("✓ System remains ready for uploads")
        
        return True

def main():
    """Run the test."""
    print("Taxonomy Edit/Delete Test")
    print("=" * 50)
    
    try:
        if test_taxonomy_edit_delete():
            print("\n" + "=" * 50)
            print("✓ All tests passed!")
            return 0
        else:
            print("\n" + "=" * 50)
            print("✗ Test failed")
            return 1
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())