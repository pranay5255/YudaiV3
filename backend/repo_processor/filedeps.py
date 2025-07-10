#!/usr/bin/env python3
"""
FastAPI server for file dependencies extraction

This server provides endpoints to extract repository data using GitIngest
and transform it to match the FileDependencies component interface.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path

# Import types from the unified models module
from models import (
    RepositoryRequest,
    FileItemResponse
)

# Import functions from scraper_script.py
from .scraper_script import (
    extract_repository_data,
    categorize_file
)

app = FastAPI(
    title="File Dependencies API",
    description="API for extracting repository file dependencies using GitIngest",
    version="1.0.0"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def estimate_tokens_for_file(file_path: str, content_size: int) -> int:
    """Estimate tokens for a file based on its size and type."""
    # Rough estimation: 1 token ≈ 4 characters for code files
    # This is a simplified approach - in production you'd use a proper tokenizer
    
    # Get file extension
    ext = Path(file_path).suffix.lower()
    
    # Different ratios for different file types
    token_ratios = {
        '.py': 4,      # Python: ~4 chars per token
        '.js': 4,      # JavaScript: ~4 chars per token
        '.ts': 4,      # TypeScript: ~4 chars per token
        '.jsx': 4,     # React JSX: ~4 chars per token
        '.tsx': 4,     # React TSX: ~4 chars per token
        '.md': 3,      # Markdown: ~3 chars per token
        '.json': 5,    # JSON: ~5 chars per token
        '.yaml': 3,    # YAML: ~3 chars per token
        '.yml': 3,     # YAML: ~3 chars per token
        '.txt': 3,     # Text: ~3 chars per token
        '.html': 4,    # HTML: ~4 chars per token
        '.css': 4,     # CSS: ~4 chars per token
        '.sql': 4,     # SQL: ~4 chars per token
        '.sh': 4,      # Shell: ~4 chars per token
    }
    
    ratio = token_ratios.get(ext, 4)  # Default to 4 chars per token
    return max(1, content_size // ratio)



def build_file_tree(files_data: Dict[str, Any], repo_name: str) -> List[FileItemResponse]:
    """Build a hierarchical file tree from GitIngest file data."""
    
    # Create a map of directories
    directories = {}
    file_items = []
    
    # Process each file
    for file_info in files_data.get('files', []):
        file_path = file_info['path']
        file_name = file_info['name']
        content_size = file_info['content_size']
        
        # Estimate tokens
        tokens = estimate_tokens_for_file(file_path, content_size)
        
        # Get category from categorize_file function (returns tuple)
        category_info = categorize_file(file_path)
        category = category_info[0] if category_info[0] else "Uncategorized"
        
        # Create file item
        file_item = FileItemResponse(
            id=f"file_{len(file_items)}",
            name=file_name,  # Use full path as requested
            type="INTERNAL",
            tokens=tokens,
            Category=category,
            isDirectory=False,
            children=None,
            expanded=False
        )
        
        # Build directory structure
        path_parts = Path(file_path).parts
        current_path = ""
        
        for i, part in enumerate(path_parts[:-1]):  # Skip the filename
            current_path = str(Path(current_path) / part) if current_path else part
            
            if current_path not in directories:
                # Get category for directory
                dir_category_info = categorize_file(current_path)
                dir_category = dir_category_info[0] if dir_category_info[0] else "Directory"
                
                dir_item = FileItemResponse(
                    id=f"dir_{current_path}",
                    name=current_path,  # Use full path as requested
                    type="INTERNAL",
                    tokens=0,
                    Category=dir_category,
                    isDirectory=True,
                    children=[],
                    expanded=False
                )
                directories[current_path] = dir_item
                
                # Add to parent directory or root
                if i == 0:  # Root level
                    file_items.append(dir_item)
                else:
                    parent_path = str(Path(current_path).parent)
                    if parent_path in directories:
                        directories[parent_path].children.append(dir_item)
        
        # Add file to its directory
        if len(path_parts) > 1:
            parent_dir = str(Path(file_path).parent)
            if parent_dir in directories:
                directories[parent_dir].children.append(file_item)
        else:
            # File is in root
            file_items.append(file_item)
    
    
    return file_items

def process_gitingest_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process raw GitIngest data into structured format for build_file_tree."""
    
    # Extract raw response data
    raw_response = raw_data.get('raw_response', {})
    tree = raw_response.get('tree', '')
    content = raw_response.get('content', '')
    
    # Parse tree structure to extract files
    files = []
    if tree:
        lines = tree.strip().split('\n')
        file_id = 0
        
        for line in lines:
            if line.strip() and not line.startswith('Directory structure:'):
                # Extract path from tree line (remove tree characters)
                path = line.strip()
                # Remove tree formatting characters
                path = path.replace('├── ', '').replace('└── ', '').replace('│   ', '').replace('│  ', '')
                
                if path and not path.endswith('/'):  # Skip directories and empty lines
                    # Get file name from path
                    file_name = os.path.basename(path)
                    
                    # Estimate content size (rough approximation)
                    # In a real implementation, you'd get this from the actual file content
                    content_size = len(path) * 100  # Placeholder estimation
                    
                    files.append({
                        'id': f"file_{file_id}",
                        'path': path,
                        'name': file_name,
                        'content_size': content_size
                    })
                    file_id += 1
    
    # Extract repository metadata
    extraction_info = raw_data.get('extraction_info', {})
    repo_url = extraction_info.get('source_url', '')
    repo_name = repo_url.split('/')[-1] if repo_url else 'unknown'
    
    return {
        'files': files,
        'repository_metadata': {
            'repository': repo_name,
            'url': repo_url
        },
        'statistics': {
            'total_files': len(files),
            'estimated_tokens': sum(estimate_tokens_for_file(f['path'], f['content_size']) for f in files)
        }
    }

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "File Dependencies API",
        "version": "1.0.0",
        "endpoints": {
            "/extract": "Extract repository data and return file dependencies",
            "/health": "Health check endpoint"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "file-dependencies-api"}

@app.post("/extract", response_model=FileItemResponse)
async def extract_file_dependencies(request: RepositoryRequest):
    """
    Extract file dependencies from a GitHub repository.
    
    This endpoint uses GitIngest to analyze a repository and returns
    a hierarchical file structure that matches the FileDependencies component interface.
    """
    try:
        # Extract repository data using GitIngest (await the async function)
        raw_repo_data = await extract_repository_data(
            repo_url=request.repo_url,
            max_file_size=request.max_file_size
        )
        
        # Check for errors
        if 'error' in raw_repo_data:
            raise HTTPException(status_code=400, detail=f"Failed to extract data: {raw_repo_data['error']}")
        
        # Process raw data into structured format
        repo_data = process_gitingest_data(raw_repo_data)
        
        # Build file tree from the processed data
        files_data = {'files': repo_data.get('files', [])}
        repo_name = repo_data.get('repository_metadata', {}).get('repository', 'unknown')
        
        file_tree = build_file_tree(files_data, repo_name)
        
        # Calculate statistics
        total_files = repo_data.get('statistics', {}).get('total_files', 0)
        total_tokens = repo_data.get('statistics', {}).get('estimated_tokens', 0)
        
        # Create root FileItem node
        root_file_item = FileItemResponse(
            id="root",
            name=repo_name,
            type="INTERNAL",
            tokens=total_tokens,
            Category="Source Code",
            isDirectory=True,
            children=file_tree,
            expanded=True
        )

        return root_file_item
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
