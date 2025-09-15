#!/usr/bin/env python3
"""
Script to pre-download the sentence-transformers model during Docker build
This ensures the model is cached and available at runtime, avoiding download delays
"""

import logging
import os
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_model():
    """Download and cache the sentence-transformers model"""
    try:
        from sentence_transformers import SentenceTransformer

        # Model configuration
        model_name = "all-MiniLM-L6-v2"

        # Cache directory configuration (use HF_HOME as recommended)
        hf_home = os.getenv("HF_HOME", "/tmp/huggingface_cache")

        # Ensure cache directory exists
        os.makedirs(hf_home, exist_ok=True)

        # Set environment variable
        os.environ["HF_HOME"] = hf_home

        logger.info(f"Downloading model: {model_name}")
        logger.info(f"Using HF cache directory: {hf_home}")

        # Download and load the model (this will cache it)
        model = SentenceTransformer(
            model_name,
            cache_folder=hf_home,
            local_files_only=False
        )

        # Test the model with a simple encoding to ensure it's working
        test_embedding = model.encode("test sentence", convert_to_numpy=False)
        logger.info(f"Model downloaded and tested successfully. Embedding dimension: {len(test_embedding)}")

        return True

    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        return False

if __name__ == "__main__":
    success = download_model()
    sys.exit(0 if success else 1)
