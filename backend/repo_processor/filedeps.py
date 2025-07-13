#!/usr/bin/env python3
"""
FastAPI server for file dependencies extraction

This server provides endpoints to extract repository data using GitIngest
and transform it to match the FileDependencies component interface.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from sqlalchemy import func

# Import DAifu chat router
from daifu.chat_api import router as daifu_router

# Import authentication
from auth import auth_router, get_current_user, get_current_user_optional

# Import GitHub API
from github import github_router

# Import database session
from db.database import get_db, init_db

# Import unified models
from models import (
    RepositoryRequest,
    FileItemResponse,
    Repository,
    FileItem,
    RepositoryResponse,
    FileItemDBResponse,
    User
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

@app.on_event("startup")
def on_startup():
    """Initialize the database when the application starts."""
    init_db()

# Mount authentication routes
app.include_router(auth_router)

# Mount GitHub API routes
app.include_router(github_router)

# Mount DAifu chat routes
app.include_router(daifu_router)

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

def extract_repo_info_from_url(repo_url: str) -> tuple[str, str]:
    """Extract repository name and owner from GitHub URL."""
    parsed = urlparse(repo_url)
    path_parts = parsed.path.strip('/').split('/')
    
    if len(path_parts) >= 2:
        owner = path_parts[0]
        repo_name = path_parts[1].replace('.git', '')
        return repo_name, owner
    else:
        return 'unknown', 'unknown'

def save_repository_to_db(
    db: Session, 
    repo_url: str, 
    repo_name: str, 
    repo_owner: str,
    raw_data: Dict[str, Any],
    processed_data: Dict[str, Any],
    total_files: int,
    total_tokens: int,
    max_file_size: Optional[int] = None,
    user_id: int = 1  # Default user ID for now
) -> Repository:
    """Save repository data to database."""
    
    # Check if repository already exists
    existing_repo = db.query(Repository).filter(
        Repository.repo_url == repo_url,
        Repository.user_id == user_id
    ).first()
    
    if existing_repo:
        # Update existing repository
        existing_repo.raw_data = raw_data
        existing_repo.processed_data = processed_data
        existing_repo.total_files = total_files
        existing_repo.total_tokens = total_tokens
        existing_repo.max_file_size = max_file_size
        existing_repo.status = "completed"
        existing_repo.processed_at = func.now()
        db.commit()
        return existing_repo
    else:
        # Create new repository
        repo = Repository(
            user_id=user_id,
            repo_url=repo_url,
            repo_name=repo_name,
            repo_owner=repo_owner,
            raw_data=raw_data,
            processed_data=processed_data,
            total_files=total_files,
            total_tokens=total_tokens,
            max_file_size=max_file_size,
            status="completed"
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        return repo

def save_file_items_to_db(
    db: Session,
    repository_id: int,
    file_items: List[FileItemResponse]
) -> List[FileItem]:
    """Save file items to database."""
    
    # Clear existing file items for this repository
    db.query(FileItem).filter(FileItem.repository_id == repository_id).delete()
    
    saved_items = []
    
    def save_file_item_recursive(item: FileItemResponse, parent_id: Optional[int] = None) -> FileItem:
        """Recursively save file items with their children."""
        
        db_item = FileItem(
            repository_id=repository_id,
            name=item.name,
            path=item.name,  # Use name as path for now
            file_type=item.type,
            category=item.Category,
            tokens=item.tokens,
            is_directory=item.isDirectory or False,
            parent_id=parent_id,
            content_size=item.tokens * 4  # Rough estimation
        )
        
        db.add(db_item)
        db.flush()  # Get the ID
        
        # Save children recursively
        if item.children:
            for child in item.children:
                save_file_item_recursive(child, db_item.id)
        
        saved_items.append(db_item)
        return db_item
    
    # Save all root items
    for item in file_items:
        save_file_item_recursive(item)
    
    db.commit()
    return saved_items

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
            "/repositories": "Get all repositories (optional user_id filter)",
            "/repositories/{id}": "Get specific repository by ID",
            "/repositories/{id}/files": "Get all files for a specific repository",
            "/health": "Health check endpoint"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "file-dependencies-api"}

@app.get("/repositories", response_model=List[RepositoryResponse])
async def get_repositories(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Get all repositories for the authenticated user"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    repositories = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    return repositories

@app.get("/repositories/{repository_id}", response_model=RepositoryResponse)
async def get_repository_by_id(
    repository_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific repository by ID."""
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository

@app.get("/repositories/{repository_id}/files", response_model=List[FileItemDBResponse])
async def get_repository_files(
    repository_id: int,
    db: Session = Depends(get_db)
):
    """Get all file items for a specific repository."""
    # Check if repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get all file items for this repository
    file_items = db.query(FileItem).filter(FileItem.repository_id == repository_id).all()
    return file_items

# TODO: This endpoint is currently broken due to Repository model changes.
# It needs to be refactored to align with the new database schema.
# @app.post("/extract", response_model=FileItemResponse)
# async def extract_file_dependencies(
#     request: RepositoryRequest,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """
#     Extracts repository data, saves it to the database, and returns file items.
#     """
#     repo_url = request.repo_url
#     max_file_size = request.max_file_size
# 
#     try:
#         # Extract repository information from URL
#         repo_name, repo_owner = extract_repo_info_from_url(repo_url)
# 
#         # Extract repository data using the scraper script
#         raw_data = await extract_repository_data(repo_url, max_file_size)
# 
#         # Process the raw data to get file items and other details
#         processed_data = process_gitingest_data(raw_data)
#         file_items_response = processed_data["file_items_response"]
#         
#         # Calculate totals
#         total_files = processed_data["total_files"]
#         total_tokens = processed_data["total_tokens"]
# 
#         # Save repository and file items to the database
#         repo = save_repository_to_db(
#             db=db,
#             repo_url=repo_url,
#             repo_name=repo_name,
#             repo_owner=repo_owner,
#             raw_data=raw_data,
#             processed_data=processed_data,
#             total_files=total_files,
#             total_tokens=total_tokens,
#             max_file_size=max_file_size,
#             user_id=current_user.id
#         )
# 
#         save_file_items_to_db(db, repo.id, file_items_response)
# 
#         return file_items_response
# 
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to extract file dependencies: {str(e)}"
#         )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
