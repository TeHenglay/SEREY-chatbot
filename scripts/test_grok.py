# Standalone script to verify Grok API connectivity.
# Run from the backend/ directory: python scripts/test_grok.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from services.grok import test_connection

if test_connection():
    print("✅ Grok connected")
else:
    print("❌ Grok failed")
