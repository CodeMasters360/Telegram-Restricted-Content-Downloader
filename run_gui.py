#!/usr/bin/env python3
"""
Telegram Content Downloader - GUI Launcher
"""

import sys
import os

# Add the src directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from gui_app import TelegramDownloaderGUI
    
    if __name__ == "__main__":
        print("Starting Telegram Content Downloader GUI...")
        app = TelegramDownloaderGUI()
        app.run()
        
except ImportError as e:
    print(f"Missing dependencies. Please install requirements:")
    print("pip install -r requirements.txt")
    print(f"Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Failed to start GUI: {e}")
    sys.exit(1)
