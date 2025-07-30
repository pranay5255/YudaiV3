#!/usr/bin/env python3
"""
Entry point script to run the File Dependencies FastAPI server
"""

import sys
from pathlib import Path

import uvicorn

# Add the backend directory to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from backend.repo_processor.filedeps import app

if __name__ == "__main__":
    print("Starting File Dependencies API server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000) 