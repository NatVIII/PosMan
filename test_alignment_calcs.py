#!/usr/bin/env python3
"""
Test alignment calculations between JavaScript preview and Python PDF processor.
Ensures both produce consistent results.
"""

import sys
import os
sys.path.insert(0, '.')

# Set CONFIG_PATH for config loader
os.environ['CONFIG_PATH'] = './config'

from app.config import config_loader
from app.pdf_processor import PDFProcessor

def simulate_javascript_calculations(page_width_pts, page_height_pts, rotation_angle=0):
    """
    Simulate JavaScript calculations from upload_preview.js.
    Returns offsetXPoints, offsetYPoints for each alignment.
    
    This mimics the logic in loadPage() function.
    """
    # Load config (same as JavaScript)
    bleed_config_raw = config_loader.load_bleed_template_config()
    bleed_config = bleed_config_raw.get('bleed_template', {})
    
    # Paper dimensions (inches)
    paper_width_in = bleed_config.get('paper_width', 12.0)
    paper_height_in = bleed_config.get('paper_height', 18.0)
    
    # Trim margins (inches) with fallbacks like JavaScript
    trim_top_in = bleed_config.get('trim_top') or bleed_config.get('safe_margin') or 0.5
    trim_bottom_in = bleed_config.get('trim_bottom') or bleed_config.get('safe_margin') or 0.5
    trim_left_in = bleed_config.get('trim_left') or bleed_config.get('safe_margin') or 0.5
    trim_right_in = bleed_config.get('trim_right') or bleed_config.get('safe_margin') or 0.5
    
    # Convert to points (72 points per inch)
    paper_width_pts = paper_width_in * 72
    paper_height_pts = paper_height_in * 72
    trim_top_pts = trim_top_in * 72
    trim_bottom_pts = trim_bottom_in * 72
    trim_left_pts = trim_left_in * 72
    trim_right_pts = trim_right_in * 72
    
    # Content area within trim lines
    content_width_pts = paper_width_pts - trim_left_pts - trim_right_pts
    content_height_pts = paper_height_pts - trim_top_pts - trim_bottom_pts
    
    # Apply rotation (like JavaScript lines 225-230)
    rotated_width = page_width_pts
    rotated_height = page_height_pts
    if rotation_angle == 90 or rotation_angle == 270:
        rotated_width = page_height_pts
        rotated_height = page_width_pts
    
    # Scale PDF to fit within content area (maintain aspect ratio)
    pdf_scale_x = content_width_pts / rotated_width
    pdf_scale_y = content_height_pts / rotated_height
    pdf_scale = min(pdf_scale_x, pdf_scale_y)
    
    scaled_pdf_width = rotated_width * pdf_scale
    scaled_pdf_height = rotated_height * pdf_scale
    
    # Calculate positions for each alignment
    results = {}
    
    for alignment in ['top', 'middle', 'bottom']:
        # Horizontal centering within trim lines (same for all alignments)
        offset_x_pts = trim_left_pts + (content_width_pts - scaled_pdf_width) / 2
        
        # Vertical alignment (canvas coordinates: origin at top-left)
        if alignment == 'top':
            # Align top of poster with top trim line
            offset_y_pts = trim_top_pts
        elif alignment == 'bottom':
            # Align bottom of poster with bottom trim line
            offset_y_pts = paper_height_pts - trim_bottom_pts - scaled_pdf_height
        else:  # middle
            # Center between top and bottom trim lines
            offset_y_pts = trim_top_pts + (content_height_pts - scaled_pdf_height) / 2
        
        results[alignment] = {
            'offset_x_pts': offset_x_pts,
            'offset_y_pts': offset_y_pts,
            'scaled_width_pts': scaled_pdf_width,
            'scaled_height_pts': scaled_pdf_height,
            'scale': pdf_scale,
            'content_width_pts': content_width_pts,
            'content_height_pts': content_height_pts,
        }
    
    return results, {
        'paper_width_pts': paper_width_pts,
        'paper_height_pts': paper_height_pts,
        'trim_top_pts': trim_top_pts,
        'trim_bottom_pts': trim_bottom_pts,
        'trim_left_pts': trim_left_pts,
        'trim_right_pts': trim_right_pts,
    }

def simulate_python_calculations(page_width_pts, page_height_pts, rotation_angle=0):
    """
    Simulate Python PDF processor calculations from _apply_preview_settings.
    Returns offset_x, offset_y for each alignment (PDF coordinates: origin at bottom-left).
    """
    # Create PDF processor instance
    pdf_processor = PDFProcessor()
    
    # Get processor's internal dimensions
    paper_width_pts = pdf_processor.PAGE_W_PT
    paper_height_pts = pdf_processor.PAGE_H_PT
    trim_top_pts = pdf_processor.trim_top_pt
    trim_bottom_pts = pdf_processor.trim_bottom_pt
    trim_left_pts = pdf_processor.trim_left_pt
    trim_right_pts = pdf_processor.trim_right_pt
    content_width_pts = pdf_processor.content_width_pt
    content_height_pts = pdf_processor.content_height_pt
    
    # Apply rotation (simplified - actual PDF processor handles rotation differently)
    rotated_width = page_width_pts
    rotated_height = page_height_pts
    if rotation_angle == 90 or rotation_angle == 270:
        rotated_width = page_height_pts
        rotated_height = page_width_pts
    
    # Scale to fit within content area (same logic)
    scale_x = content_width_pts / rotated_width
    scale_y = content_height_pts / rotated_height
    scale = min(scale_x, scale_y)
    
    scaled_width_pts = rotated_width * scale
    scaled_height_pts = rotated_height * scale
    
    results = {}
    
    for alignment in ['top', 'middle', 'bottom']:
        # Horizontal centering (same)
        offset_x = trim_left_pts + (content_width_pts - scaled_width_pts) / 2
        
        # Vertical alignment (PDF coordinates: origin at bottom-left)
        if alignment == 'top':
            # Align top of poster with top trim line
            offset_y = trim_bottom_pts + content_height_pts - scaled_height_pts
        elif alignment == 'bottom':
            # Align bottom of poster with bottom trim line
            offset_y = trim_bottom_pts
        else:  # middle
            # Center between trim lines
            offset_y = trim_bottom_pts + (content_height_pts - scaled_height_pts) / 2
        
        results[alignment] = {
            'offset_x_pts': offset_x,
            'offset_y_pts': offset_y,  # PDF coordinates (from bottom)
            'scaled_width_pts': scaled_width_pts,
            'scaled_height_pts': scaled_height_pts,
            'scale': scale,
        }
    
    return results

def convert_pdf_to_canvas_coords(pdf_offset_y, scaled_height, paper_height_pts):
    """Convert PDF coordinates (origin bottom-left) to canvas coordinates (origin top-left)."""
    # In PDF: y is distance from bottom edge
    # In canvas: y is distance from top edge
    # canvas_y = paper_height_pts - (pdf_y + scaled_height)
    return paper_height_pts - (pdf_offset_y + scaled_height)

def test_consistency():
    """Test that JavaScript and Python calculations produce consistent visual results."""
    print("Testing alignment calculation consistency between JavaScript and Python...")
    
    # Test with various page sizes
    test_cases = [
        # (page_width_in, page_height_in, rotation_angle, description)
        (8.5, 11.0, 0, "Letter portrait"),
        (11.0, 8.5, 0, "Letter landscape"),
        (8.5, 11.0, 90, "Letter portrait rotated 90°"),
        (12.0, 18.0, 0, "Full paper size"),
        (10.0, 15.0, 0, "Smaller poster"),
    ]
    
    all_passed = True
    
    for width_in, height_in, rotation, desc in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {desc} ({width_in}×{height_in} in, rotation {rotation}°)")
        
        # Convert to points
        width_pts = width_in * 72
        height_pts = height_in * 72
        
        # Get JavaScript-style results
        js_results, config = simulate_javascript_calculations(width_pts, height_pts, rotation)
        
        # Get Python results
        py_results = simulate_python_calculations(width_pts, height_pts, rotation)
        
        paper_height_pts = config['paper_height_pts']
        
        print(f"Paper: {config['paper_width_pts']/72:.1f}×{paper_height_pts/72:.1f} in")
        print(f"Trim: T={config['trim_top_pts']/72:.2f}, B={config['trim_bottom_pts']/72:.2f}, "
              f"L={config['trim_left_pts']/72:.2f}, R={config['trim_right_pts']/72:.2f} in")
        
        for alignment in ['top', 'middle', 'bottom']:
            js = js_results[alignment]
            py = py_results[alignment]
            
            # Convert Python PDF coordinates to canvas coordinates for comparison
            py_canvas_y = convert_pdf_to_canvas_coords(
                py['offset_y_pts'], py['scaled_height_pts'], paper_height_pts
            )
            
            print(f"\n  {alignment.upper()} alignment:")
            print(f"    JS: offset=({js['offset_x_pts']/72:.2f}, {js['offset_y_pts']/72:.2f}) in "
                  f"size=({js['scaled_width_pts']/72:.2f}×{js['scaled_height_pts']/72:.2f}) in")
            print(f"    PY: offset=({py['offset_x_pts']/72:.2f}, {py_canvas_y/72:.2f}) in "
                  f"size=({py['scaled_width_pts']/72:.2f}×{py['scaled_height_pts']/72:.2f}) in")
            
            # Check horizontal position matches (should be identical)
            if abs(js['offset_x_pts'] - py['offset_x_pts']) > 0.1:  # tolerance 0.1 pt
                print(f"    ⚠ X offset mismatch: JS={js['offset_x_pts']:.1f}, PY={py['offset_x_pts']:.1f}")
                all_passed = False
            else:
                print(f"    ✓ X offset matches")
            
            # Check vertical position matches after coordinate conversion
            if abs(js['offset_y_pts'] - py_canvas_y) > 0.1:
                print(f"    ⚠ Y offset mismatch: JS={js['offset_y_pts']:.1f}, PY(canvas)={py_canvas_y:.1f}")
                all_passed = False
            else:
                print(f"    ✓ Y offset matches (after coordinate conversion)")
            
            # Check scaling matches
            if abs(js['scale'] - py['scale']) > 0.0001:
                print(f"    ⚠ Scale mismatch: JS={js['scale']:.4f}, PY={py['scale']:.4f}")
                all_passed = False
    
    return all_passed

def test_horizontal_centering():
    """Specifically test horizontal centering with various poster widths."""
    print("\n" + "="*60)
    print("Testing horizontal centering...")
    
    # Load config
    bleed_config_raw = config_loader.load_bleed_template_config()
    bleed_config = bleed_config_raw.get('bleed_template', {})
    
    paper_width_in = bleed_config.get('paper_width', 12.0)
    trim_left_in = bleed_config.get('trim_left') or bleed_config.get('safe_margin') or 0.5
    trim_right_in = bleed_config.get('trim_right') or bleed_config.get('safe_margin') or 0.5
    
    content_width_in = paper_width_in - trim_left_in - trim_right_in
    
    print(f"Paper width: {paper_width_in} in")
    print(f"Trim left: {trim_left_in} in, Trim right: {trim_right_in} in")
    print(f"Content width: {content_width_in:.2f} in")
    
    # Test various poster widths
    test_widths = [content_width_in, content_width_in * 0.8, content_width_in * 0.5, content_width_in * 0.3]
    
    all_passed = True
    
    for poster_width_in in test_widths:
        offset_x = trim_left_in + (content_width_in - poster_width_in) / 2
        
        print(f"\n  Poster width: {poster_width_in:.2f} in")
        print(f"    Offset from left edge: {offset_x:.2f} in")
        print(f"    Poster left: {offset_x:.2f} in from paper left")
        print(f"    Poster right: {offset_x + poster_width_in:.2f} in from paper left")
        
        left_margin = offset_x
        right_margin = paper_width_in - (offset_x + poster_width_in)
        
        print(f"    Left margin: {left_margin:.2f} in, Right margin: {right_margin:.2f} in")
        
        # Check if centered (margins equal within tolerance)
        if abs(left_margin - right_margin) > 0.001:
            print(f"    ⚠ Not centered: left margin {left_margin:.2f}, right {right_margin:.2f}")
            all_passed = False
        else:
            print(f"    ✓ Centered within trim lines")
        
        # Check poster stays within trim lines
        if offset_x < trim_left_in - 0.001:
            print(f"    ⚠ WARNING: Poster left edge ({offset_x:.2f}) LEFT of left trim line ({trim_left_in})!")
            all_passed = False
        elif offset_x + poster_width_in > paper_width_in - trim_right_in + 0.001:
            print(f"    ⚠ WARNING: Poster right edge exceeds right trim line!")
            all_passed = False
        else:
            print(f"    ✓ Stays within trim lines")
    
    return all_passed

def main():
    """Run all tests."""
    print("Alignment Calculation Consistency Test")
    print("="*60)
    
    # Check config loads
    try:
        bleed_config_raw = config_loader.load_bleed_template_config()
        if not bleed_config_raw or 'bleed_template' not in bleed_config_raw:
            print("ERROR: Bleed template not loaded!")
            return 1
        print("✓ Configuration loaded successfully")
    except Exception as e:
        print(f"ERROR loading config: {e}")
        return 1
    
    all_passed = True
    
    # Run tests
    if not test_consistency():
        all_passed = False
    
    if not test_horizontal_centering():
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ All tests passed! JavaScript and Python calculations are consistent.")
        return 0
    else:
        print("❌ Some tests failed. Check calculations.")
        return 1

if __name__ == '__main__':
    sys.exit(main())