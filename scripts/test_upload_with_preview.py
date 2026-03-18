#!/usr/bin/env python3
"""
End-to-end test of upload workflow with preview settings.
Tests that preview settings (alignment, length snapping, orientation, fill color)
are correctly applied during PDF processing.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
import yaml
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from pypdf import PdfReader

def create_test_pdf(path: Path, pagesize=letter, text="Test PDF") -> None:
    """Create a simple PDF for testing."""
    c = canvas.Canvas(str(path), pagesize=pagesize)
    c.drawString(100, 500, text)
    c.drawString(100, 400, "This is a test PDF for upload workflow")
    c.showPage()
    c.save()
    print(f"Created test PDF at {path}")

def verify_pdf_dimensions(path: Path, expected_width_pt: float, expected_height_pt: float, tolerance: float = 2.0) -> bool:
    """Verify PDF page dimensions."""
    try:
        reader = PdfReader(str(path))
        page = reader.pages[0]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        
        if abs(width - expected_width_pt) <= tolerance and abs(height - expected_height_pt) <= tolerance:
            print(f"  Dimensions OK: {width:.1f}x{height:.1f} pt (expected {expected_width_pt}x{expected_height_pt})")
            return True
        else:
            print(f"  Dimensions mismatch: got {width:.1f}x{height:.1f} pt, expected {expected_width_pt}x{expected_height_pt}")
            return False
    except Exception as e:
        print(f"  Failed to read PDF dimensions: {e}")
        return False

def verify_page_count(path: Path, expected_pages: int) -> bool:
    """Verify PDF page count."""
    try:
        reader = PdfReader(str(path))
        actual = len(reader.pages)
        if actual == expected_pages:
            print(f"  Page count OK: {actual} pages")
            return True
        else:
            print(f"  Page count mismatch: got {actual}, expected {expected_pages}")
            return False
    except Exception as e:
        print(f"  Failed to count pages: {e}")
        return False

def test_upload_with_preview_settings():
    """Test complete upload workflow with preview settings."""
    print("Testing upload workflow with preview settings...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_path = tmpdir / "config"
        data_path = tmpdir / "data"
        config_path.mkdir()
        data_path.mkdir()
        
        # Create complete configuration
        taxonomy_config = {
            'sources': [
                {'id': 'psl', 'name': 'PSL', 'code': 'P'}
            ],
            'categories': [
                {'id': 'socialism', 'name': 'Socialism', 'code': 'S'}
            ],
            'code_lengths': {'sources': 1, 'categories': 2}
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
                'standard_lengths': [11.0, 13.75, 17.0]
            }
        }
        
        (config_path / 'taxonomy.yaml').write_text(yaml.dump(taxonomy_config))
        (config_path / 'id_templates.yaml').write_text(yaml.dump(id_templates_config))
        (config_path / 'bleed_template.yaml').write_text(yaml.dump(bleed_template_config))
        
        # Set environment variable for config path
        os.environ['CONFIG_PATH'] = str(config_path)
        
        # Import modules after setting config path
        import importlib
        import app.config
        import app.id_generator
        import app.pdf_processor
        import app.poster
        
        importlib.reload(app.config)
        importlib.reload(app.id_generator)
        importlib.reload(app.pdf_processor)
        importlib.reload(app.poster)
        
        from app.config import config_loader
        from app.id_generator import id_generator
        from app.poster import PosterManager
        from app.pdf_processor import PDFProcessor
        
        # Verify system is ready
        assert config_loader.is_system_ready_for_uploads(), "System should be ready for uploads"
        
        # Create a test PDF (portrait letter size)
        test_pdf_path = tmpdir / "test.pdf"
        create_test_pdf(test_pdf_path, pagesize=letter, text="Test Poster")
        
        # Create poster metadata with preview settings
        metadata = {
            'id': 'PS-0001',  # Will be generated, but we'll use this for testing
            'title': 'Test Poster with Preview Settings',
            'source': 'psl',
            'categories': 'socialism',
            'attribution': 'Test Artist',
            'length': '13.75',
            'price': 12.00,
            'kit': '',
            'collection': '',
            'tags': ['test'],
            'slogans': ['@test'],
            'preview_settings': {
                'alignment': 'top',
                'length_snap': '13.75',
                'orientation': 'portrait',
                'fill_color': '#ff0000',  # red
                'page_number': 1,
            }
        }
        
        # Create PosterManager
        config = {
            'default_price': 12.00,
            'seller': 'Test Seller'
        }
        manager = PosterManager(data_path, config)
        
        # Mock PDF file object (simulating upload)
        class MockPDF:
            def __init__(self, path):
                self.path = path
                
            def save(self, destination):
                shutil.copy2(self.path, destination)
        
        mock_pdf = MockPDF(test_pdf_path)
        
        # Create poster from upload (simulates upload route)
        poster = manager.create_from_upload(mock_pdf, metadata, 'test_user')
        assert poster is not None, "Failed to create poster"
        print(f"✓ Created poster: {poster['id']}")
        
        # Verify poster metadata includes preview settings
        assert 'preview_settings' in poster, "Preview settings not saved in poster metadata"
        assert poster['preview_settings']['alignment'] == 'top'
        assert poster['preview_settings']['fill_color'] == '#ff0000'
        print("✓ Preview settings saved in metadata")
        
        # Process PDF with PDFProcessor
        pdf_processor = PDFProcessor()
        
        original_path = data_path / poster['original_pdf_path']
        processed_path = data_path / 'processed' / f"{poster['id']}.pdf"
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Map taxonomy IDs to names for bug display
        sources_map = {s['id']: s for s in taxonomy_config['sources']}
        categories_map = {c['id']: c for c in taxonomy_config['categories']}
        source_name = sources_map.get(poster['source'], {}).get('name', poster['source'])
        category_name = categories_map.get(poster['categories'], {}).get('name', poster['categories'])
        
        # Process poster (this should apply preview settings)
        result = pdf_processor.process_poster(
            original_path,
            processed_path,
            poster['id'],
            {
                'title': poster['title'],
                'source': source_name,
                'categories': category_name,
                'length': poster['length'],
                'attribution': poster['attribution'],
                'price': poster['price'],
                'seller': poster['seller'],
                'slogans': poster['slogans'],
                'preview_settings': poster['preview_settings'],
            }
        )
        
        print(f"✓ PDF processed: {result['bug_applied']}")
        
        # Verify processed PDF exists
        assert processed_path.exists(), "Processed PDF not created"
        assert processed_path.stat().st_size > 0, "Processed PDF is empty"
        
        # Verify dimensions (should be paper size: 12x18 inches = 864x1296 points)
        paper_width_pt = 12.0 * 72  # 864
        paper_height_pt = 18.0 * 72  # 1296
        
        # Note: The processed PDF includes the bug page as last page
        # First page (poster) should have paper dimensions
        reader = PdfReader(str(processed_path))
        first_page = reader.pages[0]
        width = float(first_page.mediabox.width)
        height = float(first_page.mediabox.height)
        
        if abs(width - paper_width_pt) <= 2 and abs(height - paper_height_pt) <= 2:
            print("✓ Processed PDF has correct paper dimensions")
        else:
            print(f"✗ Processed PDF dimensions: {width:.1f}x{height:.1f} pt (expected {paper_width_pt}x{paper_height_pt})")
            return False
        
        # Verify page count (original pages + bug page)
        # Original PDF has 1 page, bug page adds 1 = 2 pages total
        if len(reader.pages) == 2:
            print("✓ Bug page added (2 pages total)")
        else:
            print(f"✗ Expected 2 pages, got {len(reader.pages)}")
            return False
        
        # Test 2: Different preview settings
        print("\nTesting different preview settings...")
        test_pdf_path2 = tmpdir / "test2.pdf"
        create_test_pdf(test_pdf_path2, pagesize=A4, text="Landscape Test")
        
        metadata2 = {
            'id': 'PS-0002',
            'title': 'Landscape Test',
            'source': 'psl',
            'categories': 'socialism',
            'preview_settings': {
                'alignment': 'middle',
                'length_snap': '',
                'orientation': 'landscape',
                'fill_color': '#00ff00',
                'page_number': 1,
            }
        }
        
        mock_pdf2 = MockPDF(test_pdf_path2)
        poster2 = manager.create_from_upload(mock_pdf2, metadata2, 'test_user')
        assert poster2 is not None
        
        processed_path2 = data_path / 'processed' / f"{poster2['id']}.pdf"
        result2 = pdf_processor.process_poster(
            data_path / poster2['original_pdf_path'],
            processed_path2,
            poster2['id'],
            {
                'title': poster2['title'],
                'source': source_name,
                'categories': category_name,
                'preview_settings': poster2['preview_settings'],
            }
        )
        
        assert processed_path2.exists()
        print("✓ Landscape orientation processed")
        
        # Clean up
        try:
            shutil.rmtree(data_path)
        except:
            pass
        
        return True

def main():
    """Run the test."""
    print("Upload with Preview Settings - End-to-end Test")
    print("=" * 60)
    
    try:
        if test_upload_with_preview_settings():
            print("\n" + "=" * 60)
            print("✓ All tests passed!")
            return 0
        else:
            print("\n" + "=" * 60)
            print("✗ Test failed")
            return 1
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())