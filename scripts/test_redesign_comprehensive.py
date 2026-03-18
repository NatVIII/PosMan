#!/usr/bin/env python3
"""
Comprehensive tests for the Poster Management System redesign.

Tests the new taxonomy system, ID generation, configuration management,
and upload enforcement.
"""

import os
import sys
import tempfile
import shutil
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_test(name, test_func):
    """Run a test and print result."""
    try:
        test_func()
        print(f"✓ {name}")
        return True
    except Exception as e:
        print(f"✗ {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_loader():
    """Test ConfigLoader with new configuration types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config_path.mkdir()
        
        # Create minimal config files with correct structure
        taxonomy_config = {
            'sources': [
                {'id': 'source_001', 'name': 'Test Source', 'code': 'TS1'}
            ],
            'categories': [
                {'id': 'category_001', 'name': 'Test Category', 'code': 'TC1'}
            ]
        }
        
        id_templates_config = {
            'templates': [
                {
                    'id': 'default',
                    'pattern': 'P{{category_code}}{{source_code}}-{{seq:04d}}',
                    'description': 'Test template',
                    'default': True
                }
            ],
            'counters': {'default': 1}
        }
        
        bleed_template_config = {
            'bleed_template': {
                'paper_width': 12.0,
                'paper_height': 18.0,
                'bleed_margin': 0.125,
                'safe_margin': 0.25,
                'standard_lengths': [13.75, 16.9, 19.0]
            }
        }
        
        # Write config files
        (config_path / 'taxonomy.yaml').write_text(yaml.dump(taxonomy_config))
        (config_path / 'id_templates.yaml').write_text(yaml.dump(id_templates_config))
        (config_path / 'bleed_template.yaml').write_text(yaml.dump(bleed_template_config))
        
        # Import and test ConfigLoader
        from app.config import ConfigLoader
        loader = ConfigLoader(str(config_path))
        
        # Test loading
        taxonomy = loader.load_taxonomy_config()
        assert len(taxonomy['sources']) == 1
        assert taxonomy['sources'][0]['code'] == 'TS1'
        
        id_templates = loader.load_id_templates_config()
        assert len(id_templates['templates']) == 1
        assert id_templates['templates'][0]['pattern'] == 'P{{category_code}}{{source_code}}-{{seq:04d}}'
        assert id_templates['templates'][0]['default'] == True
        
        bleed = loader.load_bleed_template_config()
        assert 'bleed_template' in bleed
        assert bleed['bleed_template']['paper_width'] == 12.0
        assert bleed['bleed_template']['bleed_margin'] == 0.125
        
        # Test system readiness
        assert loader.is_system_ready_for_uploads() == True
        
        # Test saving
        taxonomy['sources'].append({
            'id': 'source_002',
            'name': 'Another Source',
            'code': 'TS2'
        })
        loader.save_taxonomy_config(taxonomy)
        
        # Reload and verify
        reloaded = loader.load_taxonomy_config()
        assert len(reloaded['sources']) == 2
        
        # Test invalid config detection - remove bleed template data
        empty_bleed = {}
        (config_path / 'bleed_template.yaml').write_text(yaml.dump(empty_bleed))
        # Clear cache
        loader._bleed_template_config = None
        assert loader.is_system_ready_for_uploads() == False

def test_id_generator():
    """Test IDGenerator with template variables and sequence persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config_path.mkdir()
        
        # Create config files with correct structure
        pattern = 'P{{category_code}}{{source_code}}-{{seq:04d}}'
        id_templates_config = {
            'templates': [
                {
                    'id': 'default',
                    'pattern': pattern,
                    'description': 'Test template',
                    'default': True
                }
            ],
            'counters': {pattern: 5}  # Start at 5, key is the pattern string
        }
        
        (config_path / 'id_templates.yaml').write_text(yaml.dump(id_templates_config))
        
        # Patch environment variable
        with patch.dict(os.environ, {'CONFIG_PATH': str(config_path)}):
            from app.id_generator import IDGenerator
            from app.config import ConfigLoader
            
            loader = ConfigLoader(str(config_path))
            generator = IDGenerator(loader)
            
            # Test template parsing
            pattern = '{{year}}-{{month:02d}}-{{category_code}}-{{seq:04d}}'
            format_str, variables = generator.parse_template(pattern)
            assert len(variables) == 4
            assert any(v[0] == 'seq' for v in variables)
            
            # Test preview with default pattern
            context = {'category_code': 'TC1', 'source_code': 'TS1'}
            preview = generator.preview_id(context)
            # Default pattern is P{{category_code}}{{source_code}}-{{seq:04d}}
            # With counter 5, should be PTC1TS1-0005
            print(f"DEBUG preview: '{preview}'")
            assert preview == 'PTC1TS1-0005'
            
            # Test generation (increments counter)
            generated = generator.generate_id(context)
            assert generated == 'PTC1TS1-0005'
            
            # Next generation should increment
            next_id = generator.generate_id(context)
            assert next_id == 'PTC1TS1-0006'
            
            # Test parse_template with custom pattern (doesn't require config)
            pattern2 = '{{year}}-{{month:02d}}-{{category_code}}-{{seq:04d}}'
            format_str2, vars2 = generator.parse_template(pattern2)
            assert len(vars2) == 4
            assert any(v[0] == 'year' for v in vars2)
            assert any(v[0] == 'month' for v in vars2)

def test_taxonomy_integration():
    """Test poster routes with taxonomy integration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config_path.mkdir()
        
        # Create taxonomy config
        taxonomy_config = {
            'sources': [
                {'id': 'psl', 'name': 'Party for Socialism and Liberation', 'code': 'PSL'},
                {'id': 'local', 'name': 'Local Chapter', 'code': 'LOC'}
            ],
            'categories': [
                {'id': 'socialism', 'name': 'Socialism', 'code': 'SOC'},
                {'id': 'antiwar', 'name': 'Anti-War', 'code': 'ANT'}
            ]
        }
        
        (config_path / 'taxonomy.yaml').write_text(yaml.dump(taxonomy_config))
        
        # Patch the global config_loader in poster_routes module
        with patch.dict(os.environ, {'CONFIG_PATH': str(config_path)}):
            # Import after patching env var
            import importlib
            import app.poster_routes
            import app.config
            
            # Reload module to pick up new config path
            importlib.reload(app.config)
            importlib.reload(app.poster_routes)
            
            from app.poster_routes import get_taxonomy_data, get_taxonomy_mappings, enrich_poster_with_taxonomy
            
            # Test get_taxonomy_data
            data = get_taxonomy_data()
            assert len(data['sources']) == 2
            assert len(data['categories']) == 2
            
            # Test get_taxonomy_mappings
            sources_map, categories_map = get_taxonomy_mappings()
            assert 'psl' in sources_map
            assert sources_map['psl']['code'] == 'PSL'
            assert 'socialism' in categories_map
            assert categories_map['socialism']['code'] == 'SOC'
            
            # Test enrich_poster_with_taxonomy
            poster = {
                'id': 'test-001',
                'source': 'psl',
                'categories': 'socialism',
                'title': 'Test Poster'
            }
            
            enriched = enrich_poster_with_taxonomy(poster)
            assert enriched['source_display'] == 'Party for Socialism and Liberation'
            assert enriched['categories_display'] == 'Socialism'
            
            # Test with unknown IDs (fallback)
            poster2 = {
                'id': 'test-002',
                'source': 'unknown_id',
                'categories': 'unknown_cat',
                'title': 'Test Poster 2'
            }
            
            enriched2 = enrich_poster_with_taxonomy(poster2)
            assert enriched2['source_display'] == 'unknown_id'
            assert enriched2['categories_display'] == 'unknown_cat'

def test_poster_manager_taxonomy():
    """Test PosterManager with taxonomy IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = Path(tmpdir) / "data"
        data_path.mkdir()
        
        from app.poster import PosterManager
        
        config = {
            'default_price': 12.00,
            'seller': 'Test Seller'
        }
        
        manager = PosterManager(data_path, config)
        
        # Test that create_from_upload accepts taxonomy IDs
        # (PosterManager doesn't validate taxonomy - that's done in routes)
        mock_pdf = MagicMock()
        mock_pdf.save = MagicMock()
        
        metadata = {
            'id': 'TEST-001',
            'title': 'Test Poster',
            'source': 'psl_id',  # Taxonomy ID
            'categories': 'socialism_id',  # Taxonomy ID
            'attribution': 'Test Artist',
            'length': '13.75"',
            'price': '12.00',
            'kit': '',
            'collection': '',
            'tags': [],
            'slogans': []
        }
        
        # This should work - PosterManager doesn't validate taxonomy
        poster = manager.create_from_upload(mock_pdf, metadata, 'test_user')
        assert poster is not None
        assert poster['source'] == 'psl_id'
        assert poster['categories'] == 'socialism_id'

def test_full_upload_workflow():
    """Test the complete upload workflow with mocked components."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config"
        config_path.mkdir()
        
        # Create complete configs with correct structure
        taxonomy_config = {
            'sources': [
                {'id': 'psl', 'name': 'PSL', 'code': 'PSL'}
            ],
            'categories': [
                {'id': 'socialism', 'name': 'Socialism', 'code': 'SOC'}
            ]
        }
        
        pattern = 'P{{category_code}}{{source_code}}-{{seq:04d}}'
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
                'standard_lengths': [13.75, 16.9, 19.0]
            }
        }
        
        (config_path / 'taxonomy.yaml').write_text(yaml.dump(taxonomy_config))
        (config_path / 'id_templates.yaml').write_text(yaml.dump(id_templates_config))
        (config_path / 'bleed_template.yaml').write_text(yaml.dump(bleed_template_config))
        
        with patch.dict(os.environ, {'CONFIG_PATH': str(config_path)}):
            # Import modules after patching
            import importlib
            import app.config
            import app.id_generator
            import app.poster_routes
            
            importlib.reload(app.config)
            importlib.reload(app.id_generator)
            importlib.reload(app.poster_routes)
            
            from app.config import config_loader
            from app.id_generator import id_generator
            from app.poster_routes import get_taxonomy_mappings
            
            # Test system readiness
            assert config_loader.is_system_ready_for_uploads() == True
            
            # Test ID generation with taxonomy
            sources_map, categories_map = get_taxonomy_mappings()
            
            context = {
                'source_code': sources_map['psl']['code'],  # 'PSL'
                'category_code': categories_map['socialism']['code']  # 'SOC'
            }
            
            # Generate ID - pattern is P{{category_code}}{{source_code}}-{{seq:04d}}
            # So with SOC and PSL, we get PSOCPSL-0001? Wait: P{{category_code}}{{source_code}}
            # That's P + SOC + PSL = PSOCPSL
            # Actually: P + category_code + source_code = P + SOC + PSL = PSOCPSL
            # Then -{{seq:04d}} = -0001
            # So ID = PSOCPSL-0001
            poster_id = id_generator.generate_id(context)
            assert poster_id == 'PSOCPSL-0001'
            
            # Verify counter was incremented
            config = config_loader.load_id_templates_config()
            pattern = 'P{{category_code}}{{source_code}}-{{seq:04d}}'
            assert config['counters'][pattern] == 2  # Started at 1, incremented to 2

def test_admin_route_structures():
    """Test that admin route functions exist and have correct signatures."""
    # Just import to verify no syntax errors
    from app.auth import (
        taxonomy_list,
        source_add,
        category_add,
        bleed_template_edit,
        id_templates_edit
    )
    
    # Check they're callable
    assert callable(taxonomy_list)
    assert callable(source_add)
    assert callable(category_add)
    assert callable(bleed_template_edit)
    assert callable(id_templates_edit)
    
    # Verify they have required decorators by checking function names
    # (Can't easily test decorators without running Flask)

def main():
    """Run all tests."""
    print("Running comprehensive redesign tests...")
    print("=" * 60)
    
    tests = [
        ("ConfigLoader", test_config_loader),
        ("IDGenerator", test_id_generator),
        ("Taxonomy Integration", test_taxonomy_integration),
        ("Poster Manager with Taxonomy", test_poster_manager_taxonomy),
        ("Full Upload Workflow", test_full_upload_workflow),
        ("Admin Route Structures", test_admin_route_structures),
    ]
    
    results = []
    for name, test_func in tests:
        results.append(run_test(name, test_func))
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
    else:
        print(f"✗ {total - passed} tests failed")
    
    return 0 if passed == total else 1

if __name__ == '__main__':
    sys.exit(main())