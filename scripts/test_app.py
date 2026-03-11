#!/usr/bin/env python3
"""Test Flask application startup."""

import os
import sys
import time
import threading
import requests
from pathlib import Path

# Set config path
os.environ['CONFIG_PATH'] = './config'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

def run_app():
    """Run Flask app in background thread."""
    app = create_app()
    app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)

def main():
    print("Starting test application...")
    
    # Start Flask app in background thread
    thread = threading.Thread(target=run_app, daemon=True)
    thread.start()
    
    # Wait for app to start
    print("Waiting for app to start...")
    time.sleep(3)
    
    # Test health endpoint
    try:
        response = requests.get('http://127.0.0.1:5001/health', timeout=5)
        print(f"Health check: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            print("✓ Application started successfully")
            return 0
        else:
            print("✗ Application health check failed")
            return 1
    except requests.exceptions.ConnectionError:
        print("✗ Application failed to start (connection error)")
        return 1
    finally:
        # The thread will be killed when main exits (daemon thread)
        pass

if __name__ == '__main__':
    sys.exit(main())