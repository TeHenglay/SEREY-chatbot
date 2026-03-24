# Standalone script to verify Gemini API connectivity.
# Run from the backend/ directory: python scripts/test_gemini.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from services.gemini import test_connection

if test_connection():
    print("✅ Gemini connected")
else:
    print("❌ Gemini failed")
