#!/usr/bin/env python3
"""Test PDF processor functionality."""

import sys
import os
import tempfile
from pathlib import Path

# Set config path before importing
os.environ['CONFIG_PATH'] = './config'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pdf_processor import PDFProcessor, PDFProcessorError
from reportlab.pdfgen import canvas
from pypdf import PdfReader

def create_test_pdf(path, text="Test PDF"):
    """Create a simple PDF for testing."""
    from reportlab.lib.pagesizes import letter
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(100, 500, text)
    c.showPage()
    c.save()
    print(f"Created test PDF at {path}")

def test_bug_image_generation():
    """Test bug image generation without actual PDF."""
    print("Testing PDFProcessor bug image generation...")
    
    # Create processor with default config
    processor = PDFProcessor()
    
    # Test metadata
    metadata = {
        'title': 'Test Poster',
        'source': 'Test Source',
        'categories': 'Test Category',
        'price': 12.00,
        'seller': 'Test Seller',
        'slogans': ['@test', 'Test slogan'],
    }
    
    # Generate bug image
    try:
        bug_image = processor._build_bug_image('TEST-001', metadata)
        print(f"✓ Bug image generated: {bug_image.size} pixels")
        
        # Save test image
        test_dir = Path('test_output')
        test_dir.mkdir(exist_ok=True)
        bug_image.save(test_dir / 'test_bug.png')
        print(f"✓ Bug image saved to test_output/test_bug.png")
        
        # Test converting bug image to PDF page
        pdf_bytes = processor._bug_image_to_pdf_page(bug_image)
        print(f"✓ PDF page generated: {len(pdf_bytes)} bytes")
        
        # Save PDF
        with open(test_dir / 'test_bug.pdf', 'wb') as f:
            f.write(pdf_bytes)
        print(f"✓ PDF saved to test_output/test_bug.pdf")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_processor_initialization():
    """Test PDFProcessor initialization."""
    print("\nTesting PDFProcessor initialization...")
    
    try:
        processor = PDFProcessor()
        print(f"✓ Processor initialized")
        print(f"  Template config keys: {list(processor.template_config.keys())}")
        print(f"  Global config keys: {list(processor.global_config.keys())}")
        print(f"  Bug config: {processor.bug_config}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_preview_settings():
    """Test preview settings transformations."""
    print("\nTesting PDFProcessor preview settings...")
    
    # Create processor with default config
    processor = PDFProcessor()
    paper_width_pt = processor.PAGE_W_PT
    paper_height_pt = processor.PAGE_H_PT
    
    # Create a temporary source PDF (portrait letter)
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as src_file:
        src_path = Path(src_file.name)
        create_test_pdf(src_path, "Source PDF for preview settings")
    
    try:
        # Test basic transformation
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out_file:
            out_path = Path(out_file.name)
        
        preview_settings = {
            'alignment': 'middle',
            'length_snap': '',
            'orientation': 'auto',
            'fill_color': '#ffffff',
            'page_number': 1,
        }
        
        processor._apply_preview_settings(src_path, out_path, preview_settings)
        print(f"✓ Applied basic preview settings")
        
        # Verify output exists and is non-empty
        if out_path.exists() and out_path.stat().st_size > 0:
            print("✓ Output PDF created successfully")
        else:
            print("✗ Output PDF empty or missing")
            return False
        
        # Verify dimensions
        reader = PdfReader(str(out_path))
        page = reader.pages[0]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if abs(width - paper_width_pt) <= 1 and abs(height - paper_height_pt) <= 1:
            print(f"✓ Dimensions correct: {width:.1f}x{height:.1f} pt")
        else:
            print(f"✗ Dimensions mismatch: {width:.1f}x{height:.1f} pt")
            return False
        
        # Test with fill color
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out2_file:
            out2_path = Path(out2_file.name)
        
        preview_settings2 = {
            'alignment': 'top',
            'length_snap': '13.75',
            'orientation': 'portrait',
            'fill_color': '#ff0000',
            'page_number': 1,
        }
        
        processor._apply_preview_settings(src_path, out2_path, preview_settings2)
        print(f"✓ Applied fill color preview settings")
        
        if out2_path.exists() and out2_path.stat().st_size > 0:
            print("✓ Colored background PDF created")
        else:
            print("✗ Colored background PDF empty")
            return False
        
        # Clean up temp output files
        for p in [out_path, out2_path]:
            try:
                p.unlink()
            except:
                pass
        
        return True
        
    finally:
        # Clean up source PDF
        try:
            src_path.unlink()
        except:
            pass

def main():
    """Run all tests."""
    print("PDF Processor Tests")
    print("=" * 50)
    
    success = True
    
    # Test initialization
    if not test_processor_initialization():
        success = False
    
    # Test bug image generation
    if not test_bug_image_generation():
        success = False
    
    # Test preview settings
    if not test_preview_settings():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed.")
        return 1

if __name__ == '__main__':
    sys.exit(main())