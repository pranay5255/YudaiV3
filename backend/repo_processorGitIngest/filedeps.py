#!/usr/bin/env python3
"""
FastAPI router for file dependencies extraction

This router provides endpoints to extract repository data using GitIngest
and transform it to match the FileDependencies component interface.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Import authentication
from auth.github_oauth import get_current_user

# Import database session
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException

# Import unified models
from models import (
    FileAnalysis,
    FileEmbedding,
    FileItem,
    FileItemDBResponse,
    FileItemResponse,
    Repository,
    RepositoryRequest,
    RepositoryResponse,
    User,
)
from sqlalchemy.orm import Session

# Import chunking utility
from utils.chunking import create_file_chunker

# Import functions from scraper_script.py
from .scraper_script import categorize_file, extract_repository_data

# Create router for file dependencies endpoints
router = APIRouter( tags=["file-dependencies"])

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

def get_or_create_repository(
    db: Session,
    repo_url: str,
    repo_name: str,
    repo_owner: str,
    user_id: int
) -> Repository:
    """Retrieve existing repository metadata or create a new record."""

    # First try to find existing repository by URL and user
    repository = db.query(Repository).filter(
        Repository.repo_url == repo_url,
        Repository.user_id == user_id
    ).first()

    if repository:
        return repository

    # Generate a unique github_repo_id based on URL hash
    import hashlib
    repo_hash = hashlib.md5(repo_url.encode()).hexdigest()
    # Use first 6 characters to keep within PostgreSQL integer range (max ~16M)
    github_repo_id = int(repo_hash[:6], 16)  # Use first 6 characters as integer

    repository = Repository(
        user_id=user_id,
        repo_url=repo_url,
        name=repo_name,
        owner=repo_owner,
        full_name=f"{repo_owner}/{repo_name}",
        html_url=f"https://github.com/{repo_owner}/{repo_name}",
        clone_url=f"https://github.com/{repo_owner}/{repo_name}.git",
        github_repo_id=github_repo_id,  # Use generated ID instead of None
        description=f"Repository imported from {repo_url}",
        private=False,  # Default to public
        language=None
    )
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository


def save_file_analysis_to_db(
    db: Session,
    repository_id: int,
    raw_data: Dict[str, Any],
    processed_data: Dict[str, Any],
    total_files: int,
    total_tokens: int,
    max_file_size: Optional[int] = None,
    status: str = "completed",
    error_message: Optional[str] = None,
) -> FileAnalysis:
    """Save analysis results to the FileAnalysis table."""

    # Convert dictionaries to JSON strings for database storage
    raw_data_json = json.dumps(raw_data) if raw_data else None
    processed_data_json = json.dumps(processed_data) if processed_data else None

    analysis = FileAnalysis(
        repository_id=repository_id,
        raw_data=raw_data_json,  # Store as JSON string
        processed_data=processed_data_json,  # Store as JSON string
        total_files=total_files,
        total_tokens=total_tokens,
        max_file_size=max_file_size,
        status=status,
        error_message=error_message,
    )

    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis

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
            name=os.path.basename(item.name),
            path=item.name,
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


def save_file_embeddings_to_db(
    db: Session,
    session_id: int,
    repository_id: int,
    file_chunks: List[Dict[str, Any]]
) -> List[FileEmbedding]:
    """Save file embeddings to database using the chunking system."""
    
    # Clear existing file embeddings for this session
    db.query(FileEmbedding).filter(FileEmbedding.session_id == session_id).delete()
    
    saved_embeddings = []
    
    for chunk_data in file_chunks:
        # Create file embedding record
        file_embedding = FileEmbedding(
            session_id=session_id,
            repository_id=repository_id,
            file_path=chunk_data['file_path'],
            file_name=chunk_data['file_name'],
            file_type=chunk_data['file_type'],
            chunk_index=chunk_data['chunk_index'],
            chunk_text=chunk_data['chunk_text'],
            tokens=chunk_data['tokens'],
            file_metadata={
                'chunk_size': chunk_data['chunk_size'],
                'is_complete': chunk_data['is_complete'],
                'file_type': chunk_data['file_type']
            }
        )
        
        db.add(file_embedding)
        saved_embeddings.append(file_embedding)
    
    db.commit()
    return saved_embeddings


def process_file_content_for_embeddings(
    file_path: str,
    content: str,
    chunker: Any
) -> List[Dict[str, Any]]:
    """Process file content and create chunks for embeddings."""
    
    # Use the chunker to create chunks
    chunks = chunker.chunk_file(file_path, content)
    
    return chunks

def build_file_tree(files_data: Dict[str, Any], repo_name: str) -> List[FileItemResponse]:
    """Build a hierarchical file tree from GitIngest file data."""
    
    # Create a map of directories
    directories = {}
    file_items = []
    
    # Process each file
    for file_info in files_data.get('files', []):
        file_path = file_info['path']
        content_size = file_info['content_size']
        
        # Estimate tokens
        tokens = estimate_tokens_for_file(file_path, content_size)
        
        # Get category from categorize_file function (returns tuple)
        category_info = categorize_file(file_path)
        category = category_info[0] if category_info[0] else "Uncategorized"
        
        # Create file item
        file_item = FileItemResponse(
            id=f"file_{len(file_items)}",
            name=file_path,  # Use full path as requested
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
    # content = raw_response.get('content', '')  # Unused variable
    
    # Parse tree structure to extract files
    files = []
    if tree:
        lines = tree.strip().split('\n')
        file_id = 0
        
        for line in lines:
            if line.strip() and not line.startswith('Directory structure:'):
                # Extract path from tree line (remove tree characters)
                path = line.strip()
                
                # More robust tree formatting character removal
                # Remove tree formatting characters in the correct order
                path = path.replace('├── ', '').replace('└── ', '')
                path = path.replace('│   ', '').replace('│  ', '')
                
                # Remove any remaining leading/trailing whitespace
                path = path.strip()
                
                if path and not path.endswith('/'):  # Skip directories and empty lines
                    # Clean up the path - remove any remaining tree artifacts
                    # Sometimes there might be extra spaces or characters
                    path = path.strip()
                    
                    # Skip if path is empty after cleaning
                    if not path:
                        continue
                    
                    # Get file name from path
                    file_name = os.path.basename(path)
                    
                    # Skip if filename is empty or just whitespace
                    if not file_name.strip():
                        continue
                    
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
        }
    }

# @router.get("/")
# async def root():
#     """Root endpoint with API information."""
#     return {
#         "message": "File Dependencies API",
#         "version": "1.0.0",
#         "endpoints": {
#             "/extract": "Extract repository data and return file dependencies",
#             "/repositories": "Get repository by URL",
#             "/repositories/{id}/files": "Get all files for a specific repository"
#         }
#     }


# @router.get("/repositories", response_model=RepositoryResponse)
# async def get_repository_by_url(
#     repo_url: str,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """Retrieve a repository by its exact URL."""
#     repository = db.query(Repository).filter(Repository.repo_url == repo_url).first()
#     if not repository:
#         raise HTTPException(status_code=404, detail="Repository not found")
#     return repository

# @router.get("/repositories/{repository_id}/files", response_model=List[FileItemDBResponse])
# async def get_repository_files(
#     repository_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get all file items for a specific repository."""
#     # Check if repository exists
#     repository = db.query(Repository).filter(Repository.id == repository_id).first()
#     if not repository:
#         raise HTTPException(status_code=404, detail="Repository not found")
    
#     # Get all file items for this repository
#     file_items = db.query(FileItem).filter(FileItem.repository_id == repository_id).all()
#     return file_items

@router.post("/extract", response_model=FileItemResponse)
async def extract_file_dependencies(
    request: RepositoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extract file dependencies from a GitHub repository.
    
    This endpoint uses GitIngest to analyze a repository and returns
    a hierarchical file structure that matches the FileDependencies component interface.
    The data is also persisted to the database.
    """
    try:
        print(f"Starting extraction for repository: {request.repo_url}")
        
        # Extract repository information from URL
        repo_name, repo_owner = extract_repo_info_from_url(request.repo_url)
        print(f"Extracted repo info - name: {repo_name}, owner: {repo_owner}")
        
        # Extract repository data using GitIngest (await the async function)
        print("Calling GitIngest extract_repository_data...")
        raw_repo_data = await extract_repository_data(
            repo_url=request.repo_url,
            max_file_size=request.max_file_size
        )
        print(f"GitIngest returned data with keys: {list(raw_repo_data.keys())}")
        
        # Check for errors
        if 'error' in raw_repo_data:
            print(f"GitIngest returned error: {raw_repo_data['error']}")
            raise HTTPException(status_code=400, detail=f"Failed to extract data: {raw_repo_data['error']}")
        
        # Process raw data into structured format
        print("Processing GitIngest data...")
        repo_data = process_gitingest_data(raw_repo_data)
        print(f"Processed data has {len(repo_data.get('files', []))} files")
        
        # Build file tree from the processed data
        print("Building file tree...")
        files_data = {'files': repo_data.get('files', [])}
        file_tree = build_file_tree(files_data, repo_name)
        print(f"Built file tree with {len(file_tree)} root items")
        
        # Calculate basic statistics
        total_files = len(repo_data.get('files', []))
        total_tokens = sum(estimate_tokens_for_file(f['path'], f['content_size']) for f in repo_data.get('files', []))
        print(f"Calculated stats - files: {total_files}, tokens: {total_tokens}")
        
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
        
        # Save to database (with comprehensive error handling)
        print("Attempting to save to database...")
        try:
            # Ensure repository metadata exists
            print("Creating/getting repository record...")
            repository = get_or_create_repository(
                db=db,
                repo_url=request.repo_url,
                repo_name=repo_name,
                repo_owner=repo_owner,
                user_id=current_user.id
            )
            print(f"Repository ID: {repository.id}")

            # Save analysis results
            print("Saving file analysis...")
            analysis = save_file_analysis_to_db(
                db=db,
                repository_id=repository.id,
                raw_data=raw_repo_data,
                processed_data=repo_data,
                total_files=total_files,
                total_tokens=total_tokens,
                max_file_size=request.max_file_size,
            )
            print(f"File analysis saved with ID: {analysis.id}")

            # Save file items
            print("Saving file items...")
            saved_items = save_file_items_to_db(db, repository.id, file_tree)
            print(f"Saved {len(saved_items)} file items")
            
        except Exception as db_error:
            # Log database error but don't fail the request
            print(f"Database save failed: {db_error}")
            import traceback
            traceback.print_exc()
            # Continue without database persistence for now
        
        print("Extraction completed successfully")
        return root_file_item
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error in extract_file_dependencies: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# @router.post("/sessions/{session_id}/extract", response_model=FileItemResponse)
# async def extract_file_dependencies_for_session(
#     session_id: str,
#     request: RepositoryRequest,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """
#     Extract file dependencies for a specific session and create embeddings.
    
#     This endpoint integrates with the session system and creates file embeddings
#     that can be used for semantic search and context management.
#     """
#     try:
#         print(f"Starting session-based extraction for session: {session_id}")
        
#         # First, verify the session exists and belongs to the user
#         from models import ChatSession
#         session = db.query(ChatSession).filter(
#             ChatSession.session_id == session_id,
#             ChatSession.user_id == current_user.id,
#             ChatSession.is_active
#         ).first()
        
#         if not session:
#             raise HTTPException(status_code=404, detail="Session not found")
        
#         # Extract repository information from URL
#         repo_name, repo_owner = extract_repo_info_from_url(request.repo_url)
#         print(f"Extracted repo info - name: {repo_name}, owner: {repo_owner}")
        
#         # Extract repository data using GitIngest
#         print("Calling GitIngest extract_repository_data...")
#         raw_repo_data = await extract_repository_data(
#             repo_url=request.repo_url,
#             max_file_size=request.max_file_size
#         )
        
#         if 'error' in raw_repo_data:
#             raise HTTPException(status_code=400, detail=f"Failed to extract data: {raw_repo_data['error']}")
        
#         # Process raw data into structured format
#         repo_data = process_gitingest_data(raw_repo_data)
        
#         # Build file tree
#         files_data = {'files': repo_data.get('files', [])}
#         file_tree = build_file_tree(files_data, repo_name)
        
#         # Calculate statistics
#         total_files = len(repo_data.get('files', []))
#         total_tokens = sum(estimate_tokens_for_file(f['path'], f['content_size']) for f in repo_data.get('files', []))
        
#         # Create root FileItem node
#         root_file_item = FileItemResponse(
#             id="root",
#             name=repo_name,
#             type="INTERNAL",
#             tokens=total_tokens,
#             Category="Source Code",
#             isDirectory=True,
#             children=file_tree,
#             expanded=True
#         )
        
#         # Save to database with session integration
#         try:
#             # Ensure repository metadata exists
#             repository = get_or_create_repository(
#                 db=db,
#                 repo_url=request.repo_url,
#                 repo_name=repo_name,
#                 repo_owner=repo_owner,
#                 user_id=current_user.id
#             )
            
#             # Save analysis results
#             save_file_analysis_to_db(
#                 db=db,
#                 repository_id=repository.id,
#                 raw_data=raw_repo_data,
#                 processed_data=repo_data,
#                 total_files=total_files,
#                 total_tokens=total_tokens,
#                 max_file_size=request.max_file_size,
#             )
            
#             # Save file items
#             save_file_items_to_db(db, repository.id, file_tree)
            
#             # Create file embeddings using chunking system
#             print("Creating file embeddings with chunking...")
#             chunker = create_file_chunker(max_chunk_size=1000, overlap=100)
#             all_file_chunks = []
            
#             # Process each file for embeddings
#             for file_info in repo_data.get('files', []):
#                 file_path = file_info['path']
#                 # For now, we'll use placeholder content since GitIngest doesn't return actual content
#                 # In a real implementation, you'd get the actual file content
#                 placeholder_content = f"# {file_path}\n# Placeholder content for {file_path}\n# This would be the actual file content in production"
                
#                 chunks = process_file_content_for_embeddings(file_path, placeholder_content, chunker)
#                 all_file_chunks.extend(chunks)
            
#             # Save file embeddings to session
#             if all_file_chunks:
#                 saved_embeddings = save_file_embeddings_to_db(
#                     db=db,
#                     session_id=session.id,
#                     repository_id=repository.id,
#                     file_chunks=all_file_chunks
#                 )
#                 print(f"Saved {len(saved_embeddings)} file embeddings for session")
            
#             # Update session with repository context
#             session.repo_owner = repo_owner
#             session.repo_name = repo_name
#             session.repo_branch = "main"  # Default branch
#             session.repo_context = {
#                 "repository_id": repository.id,
#                 "total_files": total_files,
#                 "total_tokens": total_tokens,
#                 "file_embeddings_count": len(all_file_chunks) if all_file_chunks else 0
#             }
#             db.commit()
            
#         except Exception as db_error:
#             print(f"Database save failed: {db_error}")
#             import traceback
#             traceback.print_exc()
#             # Continue without database persistence for now
        
#         print("Session-based extraction completed successfully")
#         return root_file_item
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"Error in extract_file_dependencies_for_session: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
