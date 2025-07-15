#!/usr/bin/env python3
"""
Simple script to run the File Dependencies FastAPI server
"""

import uvicorn
from repo_processorGitIngest.filedeps import app


if __name__ == "__main__":
    print("Starting File Dependencies API server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)