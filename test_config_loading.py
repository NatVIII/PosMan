#!/usr/bin/env python3
"""
Test bleed configuration loading and template rendering.
"""

import sys
import os
sys.path.insert(0, '.')

# Mock Flask app context
os.environ['FLASK_APP'] = 'app'

from app.config import config_loader
from app.poster_routes import get_bleed_config

def test_config_loading():
    """Test that bleed config loads correctly."""
    print("Testing bleed configuration loading...")
    
    # Load raw config
    bleed_config = config_loader.load_bleed_template_config()
    print(f"Raw config loaded: {bleed_config}")
    
    template = bleed_config.get('bleed_template', {})
    print(f"\nBleed template keys: {list(template.keys())}")
    
    # Check all required fields
    required_fields = ['paper_width', 'paper_height', 'trim_top', 'trim_bottom', 'trim_left', 'trim_right']
    for field in required_fields:
        value = template.get(field)
        print(f"  {field}: {value} (type: {type(value)})")
        if value is None:
            print(f"  ⚠ WARNING: {field} is None!")
    
    # Test get_bleed_config() function
    print("\nTesting get_bleed_config() from poster_routes.py:")
    route_config = get_bleed_config()
    print(f"Returned config: {route_config}")
    print(f"Keys: {list(route_config.keys())}")
    
    # Check JSON serialization
    import json
    try:
        json_str = json.dumps(route_config)
        print(f"\nJSON serialization test: OK")
        print(f"JSON: {json_str[:200]}...")
    except Exception as e:
        print(f"\nJSON serialization failed: {e}")
    
    # Simulate template rendering
    print("\nSimulating template rendering with tojson filter:")
    print(f"Template would receive: {route_config}")
    
    # Check JavaScript compatibility
    print("\nJavaScript compatibility check:")
    print(f"  Would be accessed as: window.bleedConfig.trim_top = {route_config.get('trim_top')}")
    print(f"  Would be accessed as: window.bleedConfig.trim_left = {route_config.get('trim_left')}")
    print(f"  Would be accessed as: window.bleedConfig.trim_right = {route_config.get('trim_right')}")
    
    # Verify symmetric left/right
    trim_left = route_config.get('trim_left')
    trim_right = route_config.get('trim_right')
    if trim_left != trim_right:
        print(f"  ⚠ WARNING: trim_left ({trim_left}) != trim_right ({trim_right})")
    else:
        print(f"  ✓ trim_left == trim_right == {trim_left}")
    
    return route_config

def test_calculations(config):
    """Test actual calculations with loaded config."""
    print("\n" + "="*60)
    print("Testing calculations with actual config...")
    
    paper_width = config.get('paper_width', 12.0)
    paper_height = config.get('paper_height', 18.0)
    trim_top = config.get('trim_top', 0.25)
    trim_bottom = config.get('trim_bottom', 0.5)
    trim_left = config.get('trim_left', 0.5)
    trim_right = config.get('trim_right', 0.5)
    
    print(f"Paper: {paper_width} x {paper_height} inches")
    print(f"Trim: top={trim_top}, bottom={trim_bottom}, left={trim_left}, right={trim_right}")
    
    # Content area
    content_width = paper_width - trim_left - trim_right
    content_height = paper_height - trim_top - trim_bottom
    print(f"Content area: {content_width:.2f} x {content_height:.2f} inches")
    
    # Test horizontal centering
    poster_width = 8.0  # inches
    offset_x = trim_left + (content_width - poster_width) / 2
    print(f"\nHorizontal centering test (poster width {poster_width} inches):")
    print(f"  Offset from left edge: {offset_x:.2f} inches")
    print(f"  Poster left: {offset_x:.2f} inches from paper left")
    print(f"  Poster right: {offset_x + poster_width:.2f} inches from paper left")
    
    left_margin = offset_x
    right_margin = paper_width - (offset_x + poster_width)
    print(f"  Left margin: {left_margin:.2f} inches, Right margin: {right_margin:.2f} inches")
    
    if abs(left_margin - right_margin) < 0.001:
        print("  ✓ Poster is horizontally centered")
    else:
        print(f"  ⚠ Poster not centered: left margin {left_margin}, right {right_margin}")
    
    # Check if poster would be at paper edge
    if offset_x < trim_left - 0.001:
        print(f"  ⚠ WARNING: Poster left edge ({offset_x:.2f}) is LEFT of left trim line ({trim_left})!")
    elif abs(offset_x - trim_left) < 0.001:
        print(f"  Note: Poster left edge at left trim line (poster fills content width)")
    else:
        print(f"  ✓ Poster left edge is right of left trim line")
    
    return True

if __name__ == '__main__':
    try:
        config = test_config_loading()
        test_calculations(config)
        print("\n" + "="*60)
        print("Configuration loading test completed.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)