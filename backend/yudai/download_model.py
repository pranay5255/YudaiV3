#!/usr/bin/env python3
"""
Pre-download sentence-transformers model to avoid runtime delays.
This is optional - models will be downloaded on first use if not pre-cached.
"""

import os

# Set cache directories
os.environ["TRANSFORMERS_CACHE"] = "/tmp/transformers_cache"
os.environ["HF_HOME"] = "/tmp/huggingface_cache"

try:
    # Try to import and download the model
    from sentence_transformers import SentenceTransformer
    print("Pre-downloading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"Model cached successfully at: {os.environ['TRANSFORMERS_CACHE']}")
except ImportError:
    print("sentence-transformers not installed, skipping model download")
except Exception as e:
    print(f"Model download skipped: {e}")
    print("Models will be downloaded on first use")

print("Model setup complete")
