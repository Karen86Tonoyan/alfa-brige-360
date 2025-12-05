#!/usr/bin/env python3
"""
☁️ ALFA CLOUD OFFLINE - Quick Launcher
Run: python run_cloud.py

Options:
  --api     Start API server only
  --sync    Start sync daemon only
  --cli     Interactive CLI mode
  --health  Check system health
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    from alfa_cloud.__main__ import main
    main()
