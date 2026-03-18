#!/usr/bin/env python3
"""
Test ID generator.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set config path
os.environ['CONFIG_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'config')

# Import after setting env var
from app.id_generator import IDGenerator, id_generator

def test_id_generator():
    print("Testing IDGenerator...")
    
    # Create instance
    generator = IDGenerator()
    
    # Test template parsing
    pattern = "P{{category_code}}{{source_code}}-{{seq:04d}}"
    format_str, vars = generator.parse_template(pattern)
    print(f"Pattern: {pattern}")
    print(f"Format string: {format_str}")
    print(f"Variables: {vars}")
    
    # Test preview with sample context
    context = {'category_code': 'AW', 'source_code': 'N'}
    preview = generator.preview_id(context)
    print(f"Preview ID: {preview}")
    
    # Test actual generation (will increment counter)
    try:
        generated = generator.generate_id(context)
        print(f"Generated ID: {generated}")
    except Exception as e:
        print(f"Generation failed: {e}")
    
    # Test with another context
    context2 = {'category_code': 'LAB', 'source_code': 'L'}
    preview2 = generator.preview_id(context2)
    print(f"Preview ID 2: {preview2}")
    
    print("Test complete.")

if __name__ == '__main__':
    test_id_generator()