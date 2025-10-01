# File Tree Structure Implementation Guide

## Overview
This document provides a detailed, step-by-step breakdown for implementing a hierarchical file tree structure in the File Dependencies tab. The implementation will add tree visualization capabilities alongside the existing list view, with dependency analysis and search functionality.

## Current Architecture Analysis

### Backend Current State
- **File Storage**: Files are stored in `FileItem` model with basic metadata
- **API Endpoint**: `GET /sessions/{session_id}/file-deps/session` returns flat list of files
- **Service Layer**: `FileDepsService` handles basic file operations
- **Database**: PostgreSQL with `file_items` table storing file metadata

### Frontend Current State
- **Component**: `FileDependencies.tsx` displays files in a simple list format
- **State Management**: Uses Zustand store (`sessionStore.ts`) for file context
- **Data Flow**: React Query hooks fetch data from backend API
- **Types**: `FileItem` interface defines file structure

## Implementation Plan

---

## Phase 1: Backend Implementation

### Step 1.1: Create File Tree Service
**File**: `backend/daifuUserAgent/services/file_tree_service.py`

```python
"""
File Tree Service - Builds hierarchical tree structures from repository files
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import networkx as nx
from sqlalchemy.orm import Session

from models import FileItem

logger = logging.getLogger(__name__)

@dataclass
class FileTreeNode:
    """Represents a node in the file tree structure"""
    id: str
    name: str
    path: str
    type: str  # 'file' or 'directory'
    tokens: int = 0
    category: str = "unknown"
    is_directory: bool = False
    content_size: Optional[int] = None
    children: List['FileTreeNode'] = field(default_factory=list)
    parent_id: Optional[str] = None
    level: int = 0
    expanded: bool = False
    
    # Dependency information
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "tokens": self.tokens,
            "category": self.category,
            "is_directory": self.is_directory,
            "content_size": self.content_size,
            "children": [child.to_dict() for child in self.children],
            "parent_id": self.parent_id,
            "level": self.level,
            "expanded": self.expanded,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
        }

@dataclass
class FileTreeResponse:
    """Response structure for file tree API"""
    root_nodes: List[FileTreeNode]
    total_files: int
    total_directories: int
    total_tokens: int
    max_depth: int
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "root_nodes": [node.to_dict() for node in self.root_nodes],
            "total_files": self.total_files,
            "total_directories": self.total_directories,
            "total_tokens": self.total_tokens,
            "max_depth": self.max_depth,
            "dependency_graph": self.dependency_graph,
        }

class FileTreeService:
    """Service for building file tree structures from repository files"""
    
    @staticmethod
    def build_tree_from_file_items(file_items: List[FileItem]) -> FileTreeResponse:
        """
        Build a hierarchical tree structure from file items.
        
        Args:
            file_items: List of FileItem objects from database
            
        Returns:
            FileTreeResponse with tree structure and metadata
        """
        logger.info(f"Building file tree from {len(file_items)} file items")
        
        # Create a path-based tree structure
        tree_nodes = {}
        root_nodes = []
        
        # Sort files by path to ensure proper hierarchy
        sorted_items = sorted(file_items, key=lambda x: x.path or "")
        
        for item in sorted_items:
            if not item.path:
                continue
                
            # Create tree node
            node = FileTreeNode(
                id=str(item.id),
                name=item.name,
                path=item.path,
                type="directory" if item.is_directory else "file",
                tokens=item.tokens or 0,
                category=item.category or "unknown",
                is_directory=bool(item.is_directory),
                content_size=item.content_size,
            )
            
            tree_nodes[item.path] = node
            
            # Find parent directory
            parent_path = str(Path(item.path).parent)
            if parent_path == "." or parent_path == item.path:
                # This is a root-level item
                root_nodes.append(node)
                node.level = 0
            else:
                # Find parent node
                parent_node = tree_nodes.get(parent_path)
                if parent_node:
                    parent_node.children.append(node)
                    node.parent_id = parent_node.id
                    node.level = parent_node.level + 1
                else:
                    # Parent not found yet, add to root for now
                    root_nodes.append(node)
                    node.level = 0
        
        # Calculate statistics
        total_files = sum(1 for item in file_items if not item.is_directory)
        total_directories = sum(1 for item in file_items if item.is_directory)
        total_tokens = sum(item.tokens or 0 for item in file_items)
        max_depth = max((node.level for node in tree_nodes.values()), default=0)
        
        # Build dependency graph
        dependency_graph = FileTreeService._analyze_dependencies(file_items)
        
        return FileTreeResponse(
            root_nodes=root_nodes,
            total_files=total_files,
            total_directories=total_directories,
            total_tokens=total_tokens,
            max_depth=max_depth,
            dependency_graph=dependency_graph,
        )
    
    @staticmethod
    def _analyze_dependencies(file_items: List[FileItem]) -> Dict[str, List[str]]:
        """
        Analyze file dependencies using simple heuristics.
        
        Args:
            file_items: List of FileItem objects
            
        Returns:
            Dictionary mapping file paths to their dependencies
        """
        dependency_graph = {}
        
        # Create a NetworkX graph for dependency analysis
        G = nx.DiGraph()
        
        for item in file_items:
            if item.is_directory or not item.path:
                continue
                
            file_path = item.path
            G.add_node(file_path)
            
            # Simple dependency detection based on file extensions and imports
            dependencies = FileTreeService._detect_file_dependencies(item)
            dependency_graph[file_path] = dependencies
            
            # Add edges to graph
            for dep in dependencies:
                if dep in [i.path for i in file_items if i.path]:
                    G.add_edge(file_path, dep)
        
        return dependency_graph
    
    @staticmethod
    def _detect_file_dependencies(file_item: FileItem) -> List[str]:
        """
        Detect file dependencies using simple heuristics.
        
        Args:
            file_item: FileItem object
            
        Returns:
            List of dependency file paths
        """
        dependencies = []
        
        if not file_item.path:
            return dependencies
            
        file_path = file_item.path
        file_ext = Path(file_path).suffix.lower()
        
        # Python dependencies
        if file_ext == '.py':
            # This is a simplified approach - in reality, you'd parse the file content
            # For now, we'll use path-based heuristics
            parent_dir = Path(file_path).parent
            if parent_dir.name in ['utils', 'services', 'models']:
                # Common dependency patterns
                dependencies.extend([
                    str(parent_dir / '__init__.py'),
                    str(parent_dir.parent / 'models.py'),
                    str(parent_dir.parent / 'utils.py'),
                ])
        
        # JavaScript/TypeScript dependencies
        elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
            # Common JS dependency patterns
            if 'components' in file_path:
                dependencies.append(file_path.replace('components', 'utils'))
            if 'hooks' in file_path:
                dependencies.append(file_path.replace('hooks', 'services'))
        
        # Filter out non-existent dependencies
        return [dep for dep in dependencies if dep != file_path]
    
    @staticmethod
    def get_file_dependencies(file_path: str, dependency_graph: Dict[str, List[str]]) -> List[str]:
        """
        Get direct dependencies for a specific file.
        
        Args:
            file_path: Path to the file
            dependency_graph: Dependency graph from build_tree_from_file_items
            
        Returns:
            List of dependency file paths
        """
        return dependency_graph.get(file_path, [])
    
    @staticmethod
    def get_file_dependents(file_path: str, dependency_graph: Dict[str, List[str]]) -> List[str]:
        """
        Get files that depend on the specified file.
        
        Args:
            file_path: Path to the file
            dependency_graph: Dependency graph from build_tree_from_file_items
            
        Returns:
            List of dependent file paths
        """
        dependents = []
        for file, deps in dependency_graph.items():
            if file_path in deps:
                dependents.append(file)
        return dependents
```

**Dependencies to Add:**
- `networkx` (already available in requirements.txt)
- `pathlib` (built-in Python library)

### Step 1.2: Update Services __init__.py
**File**: `backend/daifuUserAgent/services/__init__.py`

```python
"""Repository services module."""

from .facts_and_memories import (
    EmbeddingChunk,
    EmbeddingPipeline,
    FactsAndMemoriesResult,
    FactsAndMemoriesService,
    RepositoryFile,
    RepositorySnapshot,
    RepositorySnapshotService,
)

# Add file tree service imports
from .file_tree_service import (
    FileTreeNode,
    FileTreeResponse,
    FileTreeService,
)

__all__ = [
    "EmbeddingChunk",
    "EmbeddingPipeline",
    "FactsAndMemoriesResult",
    "FactsAndMemoriesService",
    "RepositoryFile",
    "RepositorySnapshot",
    "RepositorySnapshotService",
    # Add file tree exports
    "FileTreeNode",
    "FileTreeResponse", 
    "FileTreeService",
]
```

### Step 1.3: Add New API Endpoints
**File**: `backend/daifuUserAgent/session_routes.py`

Add these imports at the top:
```python
from .services.file_tree_service import FileTreeService, FileTreeResponse
```

Add these new endpoints after the existing file dependencies endpoint:

```python
@router.get("/sessions/{session_id}/file-tree", response_model=dict)
async def get_file_tree_structure(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get hierarchical file tree structure for a session.
    This endpoint provides a tree view of the repository structure.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Get file items for this session
        file_items = (
            db.query(FileItem)
            .filter(FileItem.session_id == db_session.id)
            .order_by(FileItem.path)
            .all()
        )

        if not file_items:
            return {
                "root_nodes": [],
                "total_files": 0,
                "total_directories": 0,
                "total_tokens": 0,
                "max_depth": 0,
                "dependency_graph": {},
                "message": "No files found for this session"
            }

        # Build tree structure
        tree_response = FileTreeService.build_tree_from_file_items(file_items)
        
        return tree_response.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file tree structure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file tree structure: {str(e)}",
        )


@router.get("/sessions/{session_id}/file-tree/{file_id}/dependencies", response_model=dict)
async def get_file_dependencies(
    session_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get dependencies for a specific file.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Get the specific file
        file_item = (
            db.query(FileItem)
            .filter(
                FileItem.id == file_id,
                FileItem.session_id == db_session.id,
            )
            .first()
        )

        if not file_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Get all file items to build dependency graph
        all_file_items = (
            db.query(FileItem)
            .filter(FileItem.session_id == db_session.id)
            .all()
        )

        # Build dependency graph
        tree_response = FileTreeService.build_tree_from_file_items(all_file_items)
        
        # Get dependencies for this specific file
        dependencies = FileTreeService.get_file_dependencies(
            file_item.path, tree_response.dependency_graph
        )
        dependents = FileTreeService.get_file_dependents(
            file_item.path, tree_response.dependency_graph
        )

        return {
            "file_id": file_id,
            "file_path": file_item.path,
            "dependencies": dependencies,
            "dependents": dependents,
            "total_dependencies": len(dependencies),
            "total_dependents": len(dependents),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file dependencies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file dependencies: {str(e)}",
        )
```

### Step 1.4: Update API Routes Configuration
**File**: `backend/config/routes.py`

Add new route definitions:
```python
# Add these to the APIRoutes class

# Session File Tree routes
SESSIONS_FILE_TREE = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/file-tree"
SESSIONS_FILE_DEPENDENCIES = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/file-tree/{{fileId}}/dependencies"
```

---

## Phase 2: Frontend Implementation

### Step 2.1: Update TypeScript Types
**File**: `src/types/sessionTypes.ts`

Add these new interfaces after the existing FileItem interface:

```typescript
// ============================================================================
// FILE TREE TYPES
// ============================================================================

export interface FileTreeNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  tokens: number;
  category: string;
  is_directory: boolean;
  content_size?: number;
  children: FileTreeNode[];
  parent_id?: string;
  level: number;
  expanded: boolean;
  dependencies: string[];
  dependents: string[];
}

export interface FileTreeResponse {
  root_nodes: FileTreeNode[];
  total_files: number;
  total_directories: number;
  total_tokens: number;
  max_depth: number;
  dependency_graph: Record<string, string[]>;
}

export interface FileDependenciesResponse {
  file_id: string;
  file_path: string;
  dependencies: string[];
  dependents: string[];
  total_dependencies: number;
  total_dependents: number;
}
```

### Step 2.2: Add React Query Hooks
**File**: `src/hooks/useSessionQueries.ts`

Add these new hooks after the existing file dependencies hook:

```typescript
// ============================================================================
// FILE TREE QUERIES
// ============================================================================

export const useFileTree = (sessionId: string) => {
  const { sessionToken, clearSession } = useSessionStore();

  return useQuery({
    queryKey: QueryKeys.fileTree(sessionId),
    queryFn: async (): Promise<FileTreeResponse> => {
      try {
        const response = await fetch(buildApiUrl(API.SESSIONS.FILE_TREE, { sessionId }), {
          method: 'GET',
          headers: getAuthHeaders(sessionToken || ''),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          throw new Error('Session expired');
        }
        throw error;
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useFileDependencies = (sessionId: string, fileId: string) => {
  const { sessionToken, clearSession } = useSessionStore();

  return useQuery({
    queryKey: QueryKeys.fileDependencies(sessionId, fileId),
    queryFn: async (): Promise<FileDependenciesResponse> => {
      try {
        const response = await fetch(buildApiUrl(API.SESSIONS.FILE_DEPENDENCIES, { sessionId, fileId }), {
          method: 'GET',
          headers: getAuthHeaders(sessionToken || ''),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          throw new Error('Session expired');
        }
        throw error;
      }
    },
    enabled: !!sessionId && !!fileId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};
```

### Step 2.3: Update Query Keys
**File**: `src/hooks/useSessionQueries.ts`

Add these to the QueryKeys object:
```typescript
// Add to the QueryKeys object
fileTree: (sessionId: string) => ['fileTree', sessionId] as const,
fileDependencies: (sessionId: string, fileId: string) => ['fileDependencies', sessionId, fileId] as const,
```

### Step 2.4: Update API Configuration
**File**: `src/config/api.ts`

Add these new API endpoints:
```typescript
// Add to the API.SESSIONS object
FILE_TREE: '/sessions/{sessionId}/file-tree',
FILE_DEPENDENCIES: '/sessions/{sessionId}/file-tree/{fileId}/dependencies',
```

### Step 2.5: Create File Tree Viewer Component
**File**: `src/components/FileTreeViewer.tsx`

```typescript
import React, { useState, useCallback, useMemo } from 'react';
import { ChevronRight, ChevronDown, File, Folder, FolderOpen, Search, Filter } from 'lucide-react';
import { FileTreeNode, FileTreeResponse } from '../types/sessionTypes';
import { useSessionStore } from '../stores/sessionStore';
import { useFileTree } from '../hooks/useSessionQueries';

interface FileTreeViewerProps {
  onFileSelect?: (file: FileTreeNode) => void;
  onShowError?: (error: string) => void;
}

export const FileTreeViewer: React.FC<FileTreeViewerProps> = ({
  onFileSelect,
  onShowError
}) => {
  const { activeSessionId } = useSessionStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState<'all' | 'files' | 'directories'>('all');
  
  const { data: treeData, isLoading, error } = useFileTree(activeSessionId || '');

  const filteredTree = useMemo(() => {
    if (!treeData?.root_nodes) return [];
    
    const filterNodes = (nodes: FileTreeNode[]): FileTreeNode[] => {
      return nodes
        .filter(node => {
          // Filter by type
          if (filterType === 'files' && node.is_directory) return false;
          if (filterType === 'directories' && !node.is_directory) return false;
          
          // Filter by search term
          if (searchTerm) {
            const matchesSearch = node.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                                 node.path.toLowerCase().includes(searchTerm.toLowerCase());
            if (!matchesSearch && !node.children.some(child => 
              child.name.toLowerCase().includes(searchTerm.toLowerCase())
            )) {
              return false;
            }
          }
          
          return true;
        })
        .map(node => ({
          ...node,
          children: filterNodes(node.children)
        }));
    };
    
    return filterNodes(treeData.root_nodes);
  }, [treeData, searchTerm, filterType]);

  const toggleExpanded = useCallback((nodeId: string) => {
    setExpandedNodes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  }, []);

  const handleFileClick = useCallback((node: FileTreeNode) => {
    if (!node.is_directory) {
      onFileSelect?.(node);
    } else {
      toggleExpanded(node.id);
    }
  }, [onFileSelect, toggleExpanded]);

  const renderTreeNode = useCallback((node: FileTreeNode, depth: number = 0) => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children.length > 0;
    
    return (
      <div key={node.id} className="select-none">
        <div
          className={`flex items-center py-1 px-2 hover:bg-gray-100 cursor-pointer text-sm group ${
            node.is_directory ? 'font-medium' : ''
          }`}
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
          onClick={() => handleFileClick(node)}
        >
          <div className="flex items-center mr-2">
            {node.is_directory ? (
              hasChildren ? (
                isExpanded ? (
                  <ChevronDown size={14} className="text-gray-500" />
                ) : (
                  <ChevronRight size={14} className="text-gray-500" />
                )
              ) : (
                <div className="w-3.5" />
              )
            ) : (
              <div className="w-3.5" />
            )}
          </div>
          
          <div className="flex items-center mr-2">
            {node.is_directory ? (
              isExpanded ? (
                <FolderOpen size={16} className="text-blue-500" />
              ) : (
                <Folder size={16} className="text-blue-500" />
              )
            ) : (
              <File size={16} className="text-gray-500" />
            )}
          </div>
          
          <div className="flex-1 min-w-0">
            <span className="block text-gray-900 truncate">
              {node.name}
            </span>
            {node.path && node.path !== node.name && (
              <span className="text-xs text-gray-500 truncate block" title={node.path}>
                {node.path}
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="text-xs text-gray-400 font-mono">
              {node.tokens} tokens
            </span>
            {node.dependencies.length > 0 && (
              <span className="text-xs text-blue-500" title={`${node.dependencies.length} dependencies`}>
                {node.dependencies.length} deps
              </span>
            )}
          </div>
        </div>
        
        {node.is_directory && isExpanded && (
          <div>
            {node.children.map(child => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  }, [expandedNodes, handleFileClick]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <span className="ml-2 text-gray-600">Loading file tree...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500">
        <p>Failed to load file tree</p>
        <p className="text-sm text-gray-500">{error.message}</p>
      </div>
    );
  }

  if (!treeData || treeData.root_nodes.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Folder className="w-12 h-12 mx-auto mb-4 text-gray-300" />
        <p className="font-medium">No files found</p>
        <p className="text-sm">Repository indexing may still be in progress</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header with controls */}
      <div className="flex items-center justify-between p-4 border-b bg-gray-50">
        <div>
          <h3 className="font-semibold text-gray-800">File Tree</h3>
          <p className="text-sm text-gray-600">
            {treeData.total_files} files, {treeData.total_directories} directories
          </p>
        </div>
      </div>

      {/* Search and filter controls */}
      <div className="p-3 border-b bg-gray-50">
        <div className="flex gap-2 mb-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search files..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as 'all' | 'files' | 'directories')}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="files">Files</option>
            <option value="directories">Directories</option>
          </select>
        </div>
        
        <div className="flex justify-between items-center text-xs text-gray-500">
          <span>Total tokens: {treeData.total_tokens.toLocaleString()}</span>
          <span>Max depth: {treeData.max_depth}</span>
        </div>
      </div>

      {/* Tree content */}
      <div className="flex-1 overflow-auto">
        {filteredTree.map(node => renderTreeNode(node))}
      </div>
    </div>
  );
};
```

### Step 2.6: Update FileDependencies Component
**File**: `src/components/FileDependencies.tsx`

Add these imports at the top:
```typescript
import { TreePine, List } from 'lucide-react';
import { FileTreeViewer } from './FileTreeViewer';
```

Add this type definition:
```typescript
type ViewMode = 'list' | 'tree';
```

Update the component state:
```typescript
const [viewMode, setViewMode] = useState<ViewMode>('list');
```

Update the header section to include view mode toggle:
```typescript
<div className="flex gap-2">
  {/* View mode toggle */}
  <div className="flex border border-gray-300 rounded-md">
    <button
      onClick={() => setViewMode('list')}
      className={`px-3 py-1 text-sm ${
        viewMode === 'list' 
          ? 'bg-blue-500 text-white' 
          : 'bg-white text-gray-700 hover:bg-gray-50'
      }`}
    >
      <List size={16} />
    </button>
    <button
      onClick={() => setViewMode('tree')}
      className={`px-3 py-1 text-sm ${
        viewMode === 'tree' 
          ? 'bg-blue-500 text-white' 
          : 'bg-white text-gray-700 hover:bg-gray-50'
      }`}
    >
      <TreePine size={16} />
    </button>
  </div>
  
  <button
    onClick={handleRefresh}
    disabled={isLoading}
    className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-md disabled:opacity-50"
    title="Refresh dependencies"
  >
    <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
  </button>
</div>
```

Update the main content area:
```typescript
<div className="flex-1 overflow-auto">
  {viewMode === 'tree' ? (
    <FileTreeViewer 
      onFileSelect={(file) => {
        // Convert FileTreeNode to FileItem for compatibility
        const fileItem: FileItem = {
          id: file.id,
          name: file.name,
          path: file.path,
          type: file.type === 'directory' ? 'INTERNAL' : 'INTERNAL',
          tokens: file.tokens,
          category: file.category,
          isDirectory: file.is_directory,
          content_size: file.content_size,
        };
        onShowDetails(fileItem);
      }}
      onShowError={onShowError}
    />
  ) : (
    // ... existing list view code ...
  )}
</div>
```

---

## Phase 3: Testing and Validation

### Step 3.1: Backend Testing
1. **Test file tree service** with sample data
2. **Test API endpoints** with Postman/curl
3. **Verify dependency analysis** works correctly
4. **Test error handling** for edge cases

### Step 3.2: Frontend Testing
1. **Test tree rendering** with various file structures
2. **Test search and filtering** functionality
3. **Test expand/collapse** behavior
4. **Test integration** with existing FileDependencies component

### Step 3.3: Integration Testing
1. **Test end-to-end flow** from repository selection to tree display
2. **Test performance** with large repositories
3. **Test error states** and loading states
4. **Test responsive design** on different screen sizes

---

## Dependencies and Requirements

### Backend Dependencies
- ✅ `networkx` - Already available in requirements.txt
- ✅ `pathlib` - Built-in Python library
- ✅ `sqlalchemy` - Already available
- ✅ `fastapi` - Already available

### Frontend Dependencies
- ✅ `react` - Already available
- ✅ `@tanstack/react-query` - Already available
- ✅ `zustand` - Already available
- ✅ `lucide-react` - Already available
- ✅ `tailwindcss` - Already available

### Optional Enhancements
- `react-tree-beautiful` - For advanced tree visualization
- `@tanstack/react-virtual` - For performance with large trees
- `anytree` - For advanced tree operations in Python

---

## File Structure Changes

### New Files Created
```
backend/daifuUserAgent/services/file_tree_service.py
src/components/FileTreeViewer.tsx
```

### Files Modified
```
backend/daifuUserAgent/services/__init__.py
backend/daifuUserAgent/session_routes.py
backend/config/routes.py
src/types/sessionTypes.ts
src/hooks/useSessionQueries.ts
src/config/api.ts
src/components/FileDependencies.tsx
```

### Database Changes
- No database schema changes required
- Uses existing `file_items` table
- Leverages existing relationships

---

## Performance Considerations

### Backend Optimizations
- **Caching**: Tree structure can be cached in session context
- **Lazy Loading**: Load tree nodes on demand for large repositories
- **Dependency Analysis**: Use background tasks for complex dependency analysis

### Frontend Optimizations
- **Virtual Scrolling**: For large file trees
- **Memoization**: Use React.memo for tree nodes
- **Debounced Search**: Prevent excessive filtering operations
- **Lazy Rendering**: Only render visible tree nodes

---

## Security Considerations

### Backend Security
- **Authentication**: All endpoints require valid session
- **Authorization**: Users can only access their own sessions
- **Input Validation**: Validate session IDs and file IDs
- **Path Sanitization**: Prevent directory traversal attacks

### Frontend Security
- **XSS Prevention**: Sanitize file names and paths
- **CSRF Protection**: Use proper authentication headers
- **Input Validation**: Validate user inputs before API calls

---

## Future Enhancements

### Phase 4: Advanced Features
1. **Real-time Updates**: WebSocket integration for live tree updates
2. **File Content Preview**: Click to preview file contents
3. **Dependency Visualization**: Graph view of file dependencies
4. **Bulk Operations**: Select multiple files for operations
5. **Export Functionality**: Export tree structure to various formats

### Phase 5: Performance Optimizations
1. **Virtual Scrolling**: Handle repositories with thousands of files
2. **Incremental Loading**: Load tree nodes as needed
3. **Background Processing**: Process large repositories in background
4. **Caching Strategy**: Implement Redis caching for tree structures

This implementation provides a solid foundation for the file tree structure feature while maintaining compatibility with the existing codebase and following the established patterns and conventions.
