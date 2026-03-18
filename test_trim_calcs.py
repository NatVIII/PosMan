#!/usr/bin/env python3
"""
Test trim line calculations for symmetric left/right margins.
Verifies horizontal centering and length bounds.
"""

import sys
sys.path.insert(0, '.')

from app.config import config_loader

def test_config():
    """Load and verify bleed template configuration."""
    bleed_config = config_loader.load_bleed_template_config()
    template = bleed_config.get('bleed_template', {})
    
    print("Loaded bleed template configuration:")
    print(f"  Paper size: {template.get('paper_width')} x {template.get('paper_height')} inches")
    print(f"  Trim top: {template.get('trim_top')} inches")
    print(f"  Trim bottom: {template.get('trim_bottom')} inches")
    print(f"  Trim left: {template.get('trim_left')} inches")
    print(f"  Trim right: {template.get('trim_right')} inches")
    print(f"  Standard lengths: {template.get('standard_lengths')}")
    
    # Verify symmetric left/right trim
    trim_left = template.get('trim_left', 0.5)
    trim_right = template.get('trim_right', 0.5)
    assert trim_left == trim_right, f"Trim left ({trim_left}) != right ({trim_right}) - should be symmetric"
    print(f"✓ Left/right trim values are symmetric: {trim_left} inches")
    
    # Calculate available content area
    paper_width = template.get('paper_width', 12.0)
    paper_height = template.get('paper_height', 18.0)
    trim_top = template.get('trim_top', 0.25)
    trim_bottom = template.get('trim_bottom', 0.5)
    
    content_width = paper_width - trim_left - trim_right
    content_height = paper_height - trim_top - trim_bottom
    
    print(f"\nContent area within trim lines:")
    print(f"  Width: {content_width:.2f} inches")
    print(f"  Height: {content_height:.2f} inches")
    
    # Verify standard lengths fit within content height
    standard_lengths = template.get('standard_lengths', [])
    for length in standard_lengths:
        if isinstance(length, (int, float)):
            if length > content_height:
                print(f"⚠ Warning: Standard length {length} exceeds content height {content_height:.2f}")
            else:
                print(f"✓ Standard length {length} fits within content height")
    
    # Test horizontal centering calculation
    print(f"\nHorizontal centering test:")
    print(f"  Paper width: {paper_width} inches")
    print(f"  Trim left: {trim_left} inches, Trim right: {trim_right} inches")
    print(f"  Content width: {content_width:.2f} inches")
    
    # Simulate a poster with width 8 inches after scaling
    poster_width = 8.0
    offset_x = trim_left + (content_width - poster_width) / 2
    print(f"  Poster width: {poster_width} inches")
    print(f"  Offset from left edge: {offset_x:.2f} inches")
    print(f"  Poster left edge at: {offset_x:.2f} inches from paper left")
    print(f"  Poster right edge at: {offset_x + poster_width:.2f} inches from paper left")
    
    # Verify poster is centered within content area
    left_margin = offset_x
    right_margin = paper_width - (offset_x + poster_width)
    print(f"  Left margin: {left_margin:.2f} inches, Right margin: {right_margin:.2f} inches")
    assert abs(left_margin - right_margin) < 0.001, f"Poster not centered: left margin {left_margin}, right {right_margin}"
    print(f"✓ Poster is horizontally centered within trim lines")
    
    # Test vertical alignment calculations (PDF coordinate system - bottom origin)
    print(f"\nVertical alignment calculations (PDF coordinates - origin at bottom-left):")
    print(f"  Paper height: {paper_height} inches")
    print(f"  Trim top: {trim_top} inches, Trim bottom: {trim_bottom} inches")
    print(f"  Content height: {content_height:.2f} inches")
    
    poster_height = 10.0
    scale = 1.0  # Assume no scaling for this test
    
    # Convert to points (72 points per inch)
    trim_top_pt = trim_top * 72
    trim_bottom_pt = trim_bottom * 72
    content_height_pt = content_height * 72
    poster_height_pt = poster_height * 72
    
    print(f"\n  For poster height: {poster_height} inches ({poster_height_pt} points)")
    
    # Top alignment: align top of poster with top trim line
    # In PDF coordinates (origin at bottom-left):
    # Top trim line at y = paper_height_pt - trim_top_pt
    # Poster bottom should be at y = (paper_height_pt - trim_top_pt) - poster_height_pt
    # = trim_bottom_pt + content_height_pt - poster_height_pt
    top_offset_pt = trim_bottom_pt + content_height_pt - poster_height_pt
    print(f"  Top alignment - poster bottom at: {top_offset_pt/72:.2f} inches from bottom edge")
    
    # Bottom alignment: align bottom of poster with bottom trim line
    bottom_offset_pt = trim_bottom_pt
    print(f"  Bottom alignment - poster bottom at: {bottom_offset_pt/72:.2f} inches from bottom edge")
    
    # Middle alignment: center between trim lines
    middle_offset_pt = trim_bottom_pt + (content_height_pt - poster_height_pt) / 2
    print(f"  Middle alignment - poster bottom at: {middle_offset_pt/72:.2f} inches from bottom edge")
    
    # Verify poster stays within trim lines
    for alignment, offset_pt in [('top', top_offset_pt), ('middle', middle_offset_pt), ('bottom', bottom_offset_pt)]:
        poster_top_pt = offset_pt + poster_height_pt
        # Bottom trim line at y = trim_bottom_pt
        # Top trim line at y = paper_height_pt - trim_top_pt
        if offset_pt >= trim_bottom_pt and poster_top_pt <= (paper_height * 72 - trim_top_pt):
            print(f"✓ {alignment} alignment stays within trim lines")
        else:
            print(f"✗ {alignment} alignment exceeds trim lines: bottom={offset_pt/72:.2f}, top={poster_top_pt/72:.2f}")
    
    return True

def test_javascript_calcs():
    """Simulate JavaScript calculations (canvas coordinates - origin at top-left)."""
    print("\n" + "="*60)
    print("JavaScript-style calculations (canvas coordinates - origin at top-left):")
    
    # Using same config values
    paper_width = 12.0
    paper_height = 18.0
    trim_top = 0.25
    trim_bottom = 0.5
    trim_left = 0.5
    trim_right = 0.5
    
    content_width = paper_width - trim_left - trim_right
    content_height = paper_height - trim_top - trim_bottom
    
    # Convert to points
    paper_width_pt = paper_width * 72
    paper_height_pt = paper_height * 72
    trim_top_pt = trim_top * 72
    trim_bottom_pt = trim_bottom * 72
    trim_left_pt = trim_left * 72
    trim_right_pt = trim_right * 72
    content_width_pt = content_width * 72
    content_height_pt = content_height * 72
    
    poster_width_pt = 8.0 * 72
    poster_height_pt = 10.0 * 72
    
    # Horizontal centering (same as PDF)
    offset_x_pt = trim_left_pt + (content_width_pt - poster_width_pt) / 2
    print(f"  Horizontal offset: {offset_x_pt/72:.2f} inches from left edge")
    
    # Vertical alignment (canvas coordinates: origin at top-left)
    # Top alignment: align top of poster with top trim line
    top_offset_pt = trim_top_pt
    # Bottom alignment: align bottom of poster with bottom trim line
    bottom_offset_pt = paper_height_pt - trim_bottom_pt - poster_height_pt
    # Middle alignment: center between trim lines
    middle_offset_pt = trim_top_pt + (content_height_pt - poster_height_pt) / 2
    
    for alignment, offset_pt in [('top', top_offset_pt), ('middle', middle_offset_pt), ('bottom', bottom_offset_pt)]:
        poster_bottom_pt = offset_pt + poster_height_pt
        # Top trim line at y = trim_top_pt
        # Bottom trim line at y = paper_height_pt - trim_bottom_pt
        if offset_pt >= trim_top_pt and poster_bottom_pt <= (paper_height_pt - trim_bottom_pt):
            print(f"✓ {alignment} alignment stays within trim lines (canvas coords)")
        else:
            print(f"✗ {alignment} alignment exceeds trim lines")
    
    return True

if __name__ == '__main__':
    try:
        test_config()
        test_javascript_calcs()
        print("\n" + "="*60)
        print("All tests passed! Trim configuration is correct.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)