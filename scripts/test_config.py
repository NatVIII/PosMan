#!/usr/bin/env python3
"""
Test the new configuration system.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import config module directly without triggering app.__init__
import importlib.util
spec = importlib.util.spec_from_file_location("config", "app/config.py")
config_module = importlib.util.module_from_spec(spec)
sys.modules["config"] = config_module
spec.loader.exec_module(config_module)
config_loader = config_module.config_loader

def test_config_loader():
    print("Testing ConfigLoader...")
    
    # Create config loader with explicit path
    from pathlib import Path
    config_path = Path(__file__).parent.parent / "config"
    print(f"Config path: {config_path}")
    loader = config_module.ConfigLoader(str(config_path))
    
    # Test taxonomy config
    taxonomy = loader.load_taxonomy_config()
    print(f"Taxonomy: {len(taxonomy.get('sources', []))} sources, {len(taxonomy.get('categories', []))} categories")
    
    # Test ID templates
    id_templates = loader.load_id_templates_config()
    templates = id_templates.get('templates', [])
    print(f"ID Templates: {len(templates)} templates")
    for t in templates:
        print(f"  - {t.get('name')}: {t.get('pattern')} (default: {t.get('is_default', False)})")
    
    # Test bleed template
    bleed = loader.load_bleed_template_config()
    print(f"Bleed template configured: {'bleed_template' in bleed}")
    if 'bleed_template' in bleed:
        bt = bleed['bleed_template']
        print(f"  Paper: {bt.get('paper_width')}x{bt.get('paper_height')} inches")
        print(f"  Bleed: {bt.get('bleed_margin')} inches")
        print(f"  Safe: {bt.get('safe_margin')} inches")
    
    # Test system readiness
    ready = loader.is_system_ready_for_uploads()
    print(f"System ready for uploads: {ready}")
    
    return ready

if __name__ == '__main__':
    success = test_config_loader()
    sys.exit(0 if success else 1)