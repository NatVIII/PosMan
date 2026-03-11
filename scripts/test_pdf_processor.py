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
    
    print("\n" + "=" * 50)
    if success:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed.")
        return 1

if __name__ == '__main__':
    sys.exit(main())