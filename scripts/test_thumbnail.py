#!/usr/bin/env python3
"""Test thumbnail generation."""

import sys
import os
from pathlib import Path

# Set config path before importing
os.environ['CONFIG_PATH'] = './config'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pdf_processor import PDFProcessor

def main():
    print("Testing thumbnail generation...")
    
    # Create processor
    processor = PDFProcessor()
    
    # Test PDF path
    pdf_path = Path('test_output/test_bug.pdf')
    if not pdf_path.exists():
        print(f"Test PDF not found: {pdf_path}")
        return 1
    
    # Generate thumbnail
    thumbnail_path = processor._generate_thumbnail(pdf_path, 'TEST-001')
    
    print(f"Thumbnail generated at: {thumbnail_path}")
    print(f"File exists: {thumbnail_path.exists()}")
    print(f"File size: {thumbnail_path.stat().st_size if thumbnail_path.exists() else 0} bytes")
    
    # Check if it's a real image (not just placeholder)
    from PIL import Image
    if thumbnail_path.exists():
        img = Image.open(thumbnail_path)
        print(f"Image size: {img.size}")
        print(f"Image mode: {img.mode}")
        
        # Check if it's the placeholder (lightgray background)
        # Get pixel at (0,0)
        pixel = img.getpixel((0,0))
        if pixel == (211, 211, 211):  # lightgray
            print("WARNING: Generated placeholder instead of real thumbnail")
        else:
            print("SUCCESS: Generated real thumbnail from PDF")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())