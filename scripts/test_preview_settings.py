#!/usr/bin/env python3
"""Test preview settings transformations."""

import sys
import os
import tempfile
from pathlib import Path

# Set config path before importing
os.environ['CONFIG_PATH'] = './config'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pdf_processor import PDFProcessor
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader

def create_test_pdf(path: Path, text: str = "Test PDF") -> None:
    """Create a simple PDF for testing."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(100, 500, text)
    c.showPage()
    c.save()
    print(f"Created test PDF at {path}")

def verify_pdf_dimensions(path: Path, expected_width_pt: float, expected_height_pt: float, tolerance: float = 1.0) -> bool:
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

def test_preview_settings():
    """Test preview settings transformations."""
    print("Testing PDFProcessor preview settings...")
    
    # Create processor with default config
    processor = PDFProcessor()
    paper_width_pt = processor.PAGE_W_PT
    paper_height_pt = processor.PAGE_H_PT
    
    # Create a temporary source PDF (portrait letter)
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as src_file:
        src_path = Path(src_file.name)
        create_test_pdf(src_path, "Source PDF for preview settings")
    
    try:
        # Test 1: Basic transformation (no fill color)
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
        
        if not verify_pdf_dimensions(out_path, paper_width_pt, paper_height_pt):
            return False
        
        # Test 2: With fill color
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out2_file:
            out2_path = Path(out2_file.name)
        
        preview_settings2 = {
            'alignment': 'top',
            'length_snap': '13.75',
            'orientation': 'portrait',
            'fill_color': '#ff0000',  # red
            'page_number': 1,
        }
        
        processor._apply_preview_settings(src_path, out2_path, preview_settings2)
        print(f"✓ Applied fill color preview settings")
        
        if not verify_pdf_dimensions(out2_path, paper_width_pt, paper_height_pt):
            return False
        
        # Test 3: Landscape orientation (source is portrait letter)
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out3_file:
            out3_path = Path(out3_file.name)
        
        preview_settings3 = {
            'alignment': 'middle',
            'length_snap': '',
            'orientation': 'landscape',
            'fill_color': '#00ff00',
            'page_number': 1,
        }
        
        processor._apply_preview_settings(src_path, out3_path, preview_settings3)
        print(f"✓ Applied landscape orientation")
        
        if not verify_pdf_dimensions(out3_path, paper_width_pt, paper_height_pt):
            return False
        
        # Test 4: Length snapping
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out4_file:
            out4_path = Path(out4_file.name)
        
        preview_settings4 = {
            'alignment': 'bottom',
            'length_snap': '17.0',
            'orientation': 'auto',
            'fill_color': '#ffffff',
            'page_number': 1,
        }
        
        processor._apply_preview_settings(src_path, out4_path, preview_settings4)
        print(f"✓ Applied length snapping to 17.0 inches")
        
        if not verify_pdf_dimensions(out4_path, paper_width_pt, paper_height_pt):
            return False
        
        # Test 5: Different alignments
        for align in ['top', 'middle', 'bottom']:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as out5_file:
                out5_path = Path(out5_file.name)
            
            preview_settings5 = {
                'alignment': align,
                'length_snap': '',
                'orientation': 'auto',
                'fill_color': '#ffffff',
                'page_number': 1,
            }
            
            processor._apply_preview_settings(src_path, out5_path, preview_settings5)
            print(f"✓ Applied alignment '{align}'")
            
            if not verify_pdf_dimensions(out5_path, paper_width_pt, paper_height_pt):
                return False
            out5_path.unlink()
        
        # Clean up temp output files
        for p in [out_path, out2_path, out3_path, out4_path]:
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
    """Run preview settings tests."""
    print("Preview Settings Tests")
    print("=" * 50)
    
    if test_preview_settings():
        print("\n" + "=" * 50)
        print("All preview settings tests passed!")
        return 0
    else:
        print("\n" + "=" * 50)
        print("Some preview settings tests failed.")
        return 1

if __name__ == '__main__':
    sys.exit(main())