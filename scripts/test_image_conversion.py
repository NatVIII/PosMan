#!/usr/bin/env python3
"""Test image to PDF conversion functionality."""

import sys
import os
import io
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pdf_processor import PDFProcessor
from PIL import Image
from werkzeug.datastructures import FileStorage

def create_test_image() -> bytes:
    """Create a simple test image in memory."""
    # Create a small red image
    img = Image.new('RGB', (100, 100), color='red')
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes.read()

def test_image_to_pdf_conversion():
    """Test converting an image to PDF."""
    print("Testing image to PDF conversion...")
    
    try:
        # Create processor
        processor = PDFProcessor()
        
        # Create image bytes
        image_bytes = create_test_image()
        
        # Create a FileStorage-like object
        image_file = FileStorage(
            stream=io.BytesIO(image_bytes),
            filename='test.png',
            content_type='image/png'
        )
        
        # Convert to PDF
        pdf_bytes = processor.convert_image_to_pdf(image_file)
        
        # Check result
        if pdf_bytes and hasattr(pdf_bytes, 'read'):
            pdf_bytes.seek(0)
            pdf_data = pdf_bytes.read()
            print(f"✓ PDF generated: {len(pdf_data)} bytes")
            
            # Basic validation: check if it starts with PDF header
            if pdf_data[:4] == b'%PDF':
                print("✓ PDF has valid header")
            else:
                print("✗ PDF header not found")
                print(f"  First 20 bytes: {pdf_data[:20]}")
            
            # Save for inspection
            test_dir = Path('test_output')
            test_dir.mkdir(exist_ok=True)
            with open(test_dir / 'test_image_conversion.pdf', 'wb') as f:
                f.write(pdf_data)
            print(f"✓ PDF saved to test_output/test_image_conversion.pdf")
            
            return True
        else:
            print("✗ No PDF bytes returned")
            return False
            
    except Exception as e:
        print(f"✗ Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pil_import():
    """Test that PIL is available."""
    print("\nTesting PIL import...")
    try:
        from PIL import Image
        print("✓ PIL imported successfully")
        return True
    except ImportError as e:
        print(f"✗ PIL import failed: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Image Conversion Test")
    print("=" * 60)
    
    pil_ok = test_pil_import()
    if not pil_ok:
        print("\n❌ PIL not available, cannot run conversion test")
        sys.exit(1)
    
    success = test_image_to_pdf_conversion()
    
    if success:
        print("\n✅ Image conversion test passed!")
        sys.exit(0)
    else:
        print("\n❌ Image conversion test failed!")
        sys.exit(1)