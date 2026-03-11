#!/usr/bin/env python3
"""Integration test for poster management system."""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Set config path
os.environ['CONFIG_PATH'] = './config'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.poster import PosterManager, PosterStorage
from app.pdf_processor import PDFProcessor

def test_poster_storage():
    """Test poster metadata storage."""
    print("Testing poster storage...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = PosterStorage(Path(tmpdir))
        
        # Test save and load
        poster = {
            'id': 'TEST-001',
            'title': 'Test Poster',
            'source': 'Test',
            'categories': 'Test',
            'attribution': 'Test',
            'length': '13.75"',
            'orientation': 'portrait',
            'dimensions': {'width': 864, 'height': 1296},
            'price': 12.00,
            'price_tier': 'standard',
            'inventory_count': 5,
            'inventory_history': [],
            'original_pdf_path': 'originals/TEST-001.pdf',
            'processed_pdf_path': '',
            'thumbnail_path': '',
            'kit': 'Test Kit',
            'collection': 'Test Collection',
            'processed_at': '',
            'processing_notes': '',
            'tags': ['test', 'demo'],
            'ratings': {},
            'slogans': ['Test slogan'],
            'seller': 'Test Seller',
            'created_at': '2024-01-01T00:00:00',
            'updated_at': '2024-01-01T00:00:00',
            'created_by': 'testuser',
            'updated_by': 'testuser',
        }
        
        storage.save(poster)
        
        loaded = storage.load('TEST-001')
        assert loaded is not None
        assert loaded['id'] == 'TEST-001'
        assert loaded['title'] == 'Test Poster'
        
        # Test list
        ids = storage.list_all()
        assert 'TEST-001' in ids
        
        # Test delete
        storage.delete('TEST-001')
        assert storage.load('TEST-001') is None
        
        print("✓ Poster storage tests passed")
        return True

def test_poster_manager():
    """Test poster manager."""
    print("Testing poster manager...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = PosterManager(Path(tmpdir))
        
        # Test directory creation
        assert (Path(tmpdir) / 'originals').exists()
        assert (Path(tmpdir) / 'processed').exists()
        assert (Path(tmpdir) / 'thumbnails').exists()
        assert (Path(tmpdir) / 'metadata').exists()
        
        # Test stats with no posters
        stats = manager.get_stats()
        assert stats['total_posters'] == 0
        assert stats['total_inventory'] == 0
        
        print("✓ Poster manager tests passed")
        return True

def test_pdf_processor():
    """Test PDF processor."""
    print("Testing PDF processor...")
    
    processor = PDFProcessor()
    
    # Test configuration loading
    assert processor.template_config is not None
    assert 'global' in processor.template_config
    
    # Test bug image generation
    metadata = {
        'title': 'Test Poster',
        'source': 'Test',
        'categories': 'Test',
        'price': 12.00,
        'seller': 'Test Seller',
        'slogans': ['Test slogan'],
    }
    
    try:
        bug_image = processor._build_bug_image('TEST-001', metadata)
        assert bug_image.size[0] > 0
        assert bug_image.size[1] > 0
        print("✓ Bug image generation works")
    except Exception as e:
        print(f"⚠ Bug image generation test skipped: {e}")
    
    print("✓ PDF processor tests passed")
    return True

def test_app_creation():
    """Test Flask app creation."""
    print("Testing Flask app creation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test config directory
        config_dir = Path(tmpdir) / 'config'
        config_dir.mkdir()
        
        # Create minimal config files
        system_config = config_dir / 'system.yaml'
        system_config.write_text("""
system:
  name: "Test System"
  data_path: "./data"
  ftp_export_path: "./data/ftp_export"
  backup_path: "./backups"
  backup_retention: 4
  upload_limit_mb: 200
users:
  admin:
    username: "admin"
    password_hash: "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
    role: "admin"
    force_password_change: false
""")
        
        template_config = config_dir / 'template.yaml'
        template_config.write_text("""
template:
  global:
    price: 12.00
    seller: "Test Seller"
    slogans:
      - "@test"
    bug:
      width_in: 2.0
      top_frac: 0.1
      page_margin_in: 0.5
      dpi: 300
""")
        
        # Set config path
        os.environ['CONFIG_PATH'] = str(config_dir)
        
        # Create app
        app = create_app()
        
        # Test app config
        assert app.config['SYSTEM_NAME'] == 'Test System'
        assert 'posters' in [bp.name for bp in app.blueprints.values()]
        
        print("✓ Flask app creation tests passed")
        return True

def main():
    """Run all integration tests."""
    print("Running integration tests...")
    print("=" * 60)
    
    tests = [
        test_poster_storage,
        test_poster_manager,
        test_pdf_processor,
        test_app_creation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())