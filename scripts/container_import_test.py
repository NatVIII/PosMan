#!/usr/bin/env python3
"""
Test script to verify that the application can be imported inside the Docker container.
This helps diagnose import errors that cause "Could not import 'app.app'" errors.
"""
import sys
import traceback

def test_imports():
    """Test importing the app module and its dependencies."""
    errors = []
    
    # Try importing core dependencies first
    deps = [
        'flask',
        'yaml',
        'portalocker',
        'bcrypt',
        'PIL',
        'qrcode',
        'pypdf',
        'reportlab',
        'pdf2image',
        'pandas',
        'dotenv',
    ]
    
    for dep in deps:
        try:
            __import__(dep)
            print(f"✓ {dep}")
        except ImportError as e:
            errors.append(f"{dep}: {e}")
            print(f"✗ {dep}: {e}")
    
    # Try importing the app module
    print("\n--- Testing app module import ---")
    # Ensure the app module can be found (add parent directory to sys.path)
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        import app
        print("✓ app module imported successfully")
        # Try accessing config_loader
        from app.config import config_loader
        print("✓ config_loader imported successfully")
        # Try creating app instance
        from app import create_app
        app_instance = create_app()
        print("✓ Flask app created successfully")
    except Exception as e:
        errors.append(f"app import: {e}")
        print(f"✗ app import failed: {e}")
        traceback.print_exc()
    
    if errors:
        print(f"\n❌ Found {len(errors)} import error(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n✅ All imports successful!")
        sys.exit(0)

if __name__ == '__main__':
    test_imports()