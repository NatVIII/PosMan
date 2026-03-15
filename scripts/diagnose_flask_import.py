#!/usr/bin/env python3
"""
Diagnostic script to identify the root cause of "Could not import 'app.app'" error.
Run this inside the Docker container to see what's happening.
"""
import os
import sys
import traceback
import subprocess

def print_section(title):
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")

def main():
    print_section("FLASK IMPORT DIAGNOSTIC")
    
    # 1. Environment variables
    print_section("ENVIRONMENT VARIABLES")
    flask_app = os.environ.get('FLASK_APP')
    flask_env = os.environ.get('FLASK_ENV')
    config_path = os.environ.get('CONFIG_PATH')
    pythonpath = os.environ.get('PYTHONPATH')
    
    print(f"FLASK_APP: {flask_app}")
    print(f"FLASK_ENV: {flask_env}")
    print(f"CONFIG_PATH: {config_path}")
    print(f"PYTHONPATH: {pythonpath}")
    
    # 2. Current directory and files
    print_section("CURRENT DIRECTORY")
    cwd = os.getcwd()
    print(f"Current working directory: {cwd}")
    print("Contents of current directory:")
    try:
        for item in sorted(os.listdir(cwd)):
            print(f"  {item}")
    except Exception as e:
        print(f"  Error listing directory: {e}")
    
    # 3. Python path
    print_section("PYTHON PATH (sys.path)")
    for i, path in enumerate(sys.path):
        print(f"{i:2}: {path}")
    
    # 4. Check app directory
    print_section("APP DIRECTORY CHECK")
    app_dir = os.path.join(cwd, 'app')
    if os.path.exists(app_dir):
        print(f"app directory exists at: {app_dir}")
        print("Contents of app directory:")
        try:
            for item in sorted(os.listdir(app_dir)):
                print(f"  {item}")
        except Exception as e:
            print(f"  Error listing app directory: {e}")
        
        # Check for __init__.py
        init_py = os.path.join(app_dir, '__init__.py')
        if os.path.exists(init_py):
            print(f"✓ __init__.py exists at: {init_py}")
        else:
            print(f"✗ __init__.py MISSING at: {init_py}")
    else:
        print(f"✗ app directory does NOT exist at: {app_dir}")
    
    # 5. Try importing app module
    print_section("ATTEMPTING IMPORT: import app")
    try:
        import app
        print("✓ Successfully imported 'app'")
        print(f"  app module location: {app.__file__}")
        
        # Check if create_app exists
        if hasattr(app, 'create_app'):
            print("✓ 'create_app' function found in app module")
        else:
            print("✗ 'create_app' function NOT found in app module")
            
        # Check if app.app exists (what Flask might be looking for)
        if hasattr(app, 'app'):
            print("✓ 'app' attribute found in app module (app.app)")
        else:
            print("✗ 'app' attribute NOT found in app module")
            
    except ImportError as e:
        print(f"✗ ImportError: {e}")
        traceback.print_exc()
    
    # 6. Try importing app.app specifically
    print_section("ATTEMPTING IMPORT: from app import app")
    try:
        from app import app as app_app
        print("✓ Successfully imported 'app.app'")
        print(f"  app.app location: {app_app.__file__ if hasattr(app_app, '__file__') else 'N/A'}")
    except ImportError as e:
        print(f"✗ ImportError: {e}")
        traceback.print_exc()
    
    # 7. Check Flask installation and version
    print_section("FLASK VERSION CHECK")
    try:
        import flask
        version = getattr(flask, '__version__', 'unknown')
        print(f"Flask version: {version}")
        print(f"Flask location: {flask.__file__}")
    except ImportError as e:
        print(f"✗ Flask not installed: {e}")
    
    # 8. Simulate Flask's import logic
    print_section("FLASK IMPORT SIMULATION")
    if flask_app:
        print(f"FLASK_APP is set to: '{flask_app}'")
        # Flask splits on ':' and '.'
        if ':' in flask_app:
            module_name, app_name = flask_app.split(':', 1)
            print(f"  Flask would import module: '{module_name}'")
            print(f"  Flask would look for attribute: '{app_name}'")
        elif '.' in flask_app:
            module_name, app_name = flask_app.split('.', 1)
            print(f"  Flask would import module: '{module_name}'")
            print(f"  Flask would look for attribute: '{app_name}'")
        else:
            print(f"  Flask would import module: '{flask_app}'")
            print(f"  Flask would look for 'app' or 'create_app' attribute")
    
    # 9. Check if .flaskenv file exists
    print_section(".FLASKENV FILE CHECK")
    flaskenv_path = os.path.join(cwd, '.flaskenv')
    if os.path.exists(flaskenv_path):
        print(f"✓ .flaskenv file exists at: {flaskenv_path}")
        try:
            with open(flaskenv_path, 'r') as f:
                content = f.read()
                print("Contents of .flaskenv:")
                print(content)
        except Exception as e:
            print(f"  Error reading .flaskenv: {e}")
    else:
        print(f"✗ .flaskenv file does NOT exist at: {flaskenv_path}")
    
    # 10. Test actual Flask CLI
    print_section("TESTING FLASK CLI IMPORT")
    try:
        # Try to run flask --help to see if it works
        result = subprocess.run(
            [sys.executable, '-m', 'flask', '--help'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ Flask CLI works (flask --help succeeded)")
        else:
            print(f"✗ Flask CLI failed with return code {result.returncode}")
            print(f"  stderr: {result.stderr[:200]}")
    except Exception as e:
        print(f"✗ Error running Flask CLI: {e}")
    
    print_section("DIAGNOSTIC COMPLETE")
    print("\nRecommendations:")
    if not os.path.exists(app_dir):
        print("1. The 'app' directory is missing. Check volume mounts.")
    elif not os.path.exists(os.path.join(app_dir, '__init__.py')):
        print("1. The 'app' directory is missing __init__.py.")
    elif not flask_app:
        print("1. FLASK_APP environment variable is not set.")
        print("   Set it with: export FLASK_APP=app")
    else:
        print("1. Check that FLASK_APP is set correctly (should be 'app').")
    print("2. Ensure all Python dependencies are installed (pip install -r requirements.txt).")
    print("3. Check file permissions - the app directory must be readable.")

if __name__ == '__main__':
    main()