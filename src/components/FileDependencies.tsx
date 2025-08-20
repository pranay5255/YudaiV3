import React, { useState, useCallback, useEffect } from 'react';
import { ChevronRight, ChevronDown, Plus, Folder, File, RefreshCw } from 'lucide-react';
import { FileItem } from '../types';
import { useSessionState, useFileDependencyManagement } from '../hooks/useSessionState';
import { ApiService } from '../services/api';
import type { FileDependencyNode } from '../types/api';

interface FileDependenciesProps {
  onAddToContext: (file: FileItem) => void;
  onShowDetails: (file: FileItem) => void;
  onShowError?: (error: string) => void;
  repoUrl?: string; // Optional repository URL to analyze
}

// Extended FileItem type with frontend-specific properties
interface ExtendedFileItem extends FileItem {
  children: ExtendedFileItem[];
  expanded: boolean;
}

export const FileDependencies: React.FC<FileDependenciesProps> = ({
  onAddToContext,
  onShowDetails,
  onShowError,
  repoUrl
}) => {
  const sessionState = useSessionState();
  const { addMultipleFileDependencies } = useFileDependencyManagement();
  const [files, setFiles] = useState<ExtendedFileItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStates, setLoadingStates] = useState<{[key: string]: boolean}>({});

  const showError = useCallback((message: string) => {
    if (onShowError) {
      onShowError(message);
    }
  }, [onShowError]);

  const toggleExpanded = useCallback((targetId: string) => {
    const toggleInTree = (items: ExtendedFileItem[]): ExtendedFileItem[] => {
      return items.map(item => {
        if (item.id === targetId) {
          return { ...item, expanded: !item.expanded };
        }
        if (item.children) {
          return { ...item, children: toggleInTree(item.children) };
        }
        return item;
      });
    };
    setFiles(toggleInTree(files));
  }, [files]);

  const loadFileDependencies = useCallback(async () => {
    if (!sessionState.sessionId) {
      console.log('[FileDependencies] No active session found');
      setFiles([]);
      return;
    }

    console.log('[FileDependencies] Loading file dependencies for session:', sessionState.sessionId);
    setIsLoading(true);
    
    try {
      // First, try to get file dependencies from session
      const sessionDependencies = await ApiService.getFileDependenciesSession(
        sessionState.sessionId
      );
      
      if (sessionDependencies && sessionDependencies.length > 0) {
        console.log('[FileDependencies] Found session dependencies:', sessionDependencies.length);
        
        // Convert session file embeddings to ExtendedFileItem format
        const convertedFiles: ExtendedFileItem[] = sessionDependencies.map(dep => ({
          id: dep.id.toString(),
          name: dep.file_name,
          path: dep.file_path,
          type: 'INTERNAL',
          tokens: dep.tokens,
          category: dep.file_type,
          isDirectory: false,
          children: [],
          expanded: false
        }));
        setFiles(convertedFiles);
      } else if (repoUrl && sessionState.repositoryInfo) {
        console.log('[FileDependencies] No session dependencies, extracting from repository:', repoUrl);
        
        // If no session dependencies, try to extract from repository
        const repoDependencies = await ApiService.extractFileDependencies(
          repoUrl
        );
        
        if (repoDependencies && repoDependencies.children) {
          console.log('[FileDependencies] Extracted dependencies from repository, adding to session');
          
          // Convert FileDependencyNode to CreateFileEmbeddingRequest format
          const convertToFileEmbeddingRequests = (items: FileDependencyNode[], parentPath: string = ''): Array<{
            file_path: string;
            file_name: string;
            file_type: string;
            chunk_index: number;
            tokens: number;
            file_metadata?: Record<string, unknown>;
          }> => {
            const requests: Array<{
              file_path: string;
              file_name: string;
              file_type: string;
              chunk_index: number;
              tokens: number;
              file_metadata?: Record<string, unknown>;
            }> = [];
            
            items.forEach(item => {
              const currentPath = parentPath ? `${parentPath}/${item.name}` : item.name;
              
              // Add the current item
              requests.push({
                file_path: currentPath,
                file_name: item.name,
                file_type: item.Category || 'unknown',
                chunk_index: 0, // Default chunk index
                tokens: item.tokens || 0,
                file_metadata: {
                  isDirectory: item.isDirectory || false,
                  type: item.type || 'INTERNAL',
                  category: item.Category || 'unknown',
                }
              });
              
              // Recursively add children
              if (item.children && item.children.length > 0) {
                requests.push(...convertToFileEmbeddingRequests(item.children, currentPath));
              }
            });
            
            return requests;
          };
          
          const fileEmbeddingRequests = convertToFileEmbeddingRequests(repoDependencies.children);
          
          // Add file dependencies to session
          await addMultipleFileDependencies(fileEmbeddingRequests);
          
          // Convert to ExtendedFileItem format for display
          const convertToExtendedItems = (items: FileDependencyNode[]): ExtendedFileItem[] => {
            return items.map(item => ({
              id: item.id,
              name: item.name,
              path: undefined, // FileDependencyNode doesn't have path property
              type: (item.type as 'INTERNAL' | 'EXTERNAL') || 'INTERNAL',
              tokens: item.tokens || 0,
              category: item.Category || 'unknown',
              isDirectory: item.isDirectory || false,
              children: item.children ? convertToExtendedItems(item.children) : [],
              expanded: false
            }));
          };
          
          setFiles(convertToExtendedItems(repoDependencies.children));
        } else {
          setFiles([]);
        }
      } else {
        console.log('[FileDependencies] No dependencies found');
        setFiles([]);
      }
    } catch (error) {
      console.error('[FileDependencies] Error loading file dependencies:', error);
      
      // Don't show error for 404 - just set empty files
      if (error instanceof Error && error.message.includes('404')) {
        console.log('[FileDependencies] 404 error - no file dependencies found for session');
        setFiles([]);
      } else {
        showError('Failed to load file dependencies');
        setFiles([]);
      }
    } finally {
      setIsLoading(false);
    }
  }, [sessionState.sessionId, sessionState.repositoryInfo, repoUrl, showError, addMultipleFileDependencies]);

  // Load file dependencies when session changes
  useEffect(() => {
    if (sessionState.sessionId) {
      loadFileDependencies();
    } else {
      // Clear files when no session
      setFiles([]);
    }
  }, [sessionState.sessionId, sessionState.repositoryInfo, loadFileDependencies]);

  const handleRefresh = async () => {
    console.log('[FileDependencies] Refreshing file dependencies...');
    
    // Clear existing files first
    setFiles([]);
    
    // Reload file dependencies
    await loadFileDependencies();
  };

  const handleForceExtract = async () => {
    if (!repoUrl || !sessionState.repositoryInfo) {
      console.log('[FileDependencies] Cannot force extract: no repository URL or info');
      return;
    }

    console.log('[FileDependencies] Force extracting file dependencies from repository:', repoUrl);
    setIsLoading(true);
    
    try {
      // Force extract from repository
      const repoDependencies = await ApiService.extractFileDependencies(repoUrl);
      
      if (repoDependencies && repoDependencies.children) {
        console.log('[FileDependencies] Force extracted dependencies, adding to session');
        
        // Convert FileDependencyNode to CreateFileEmbeddingRequest format
        const convertToFileEmbeddingRequests = (items: FileDependencyNode[], parentPath: string = ''): Array<{
          file_path: string;
          file_name: string;
          file_type: string;
          chunk_index: number;
          tokens: number;
          file_metadata?: Record<string, unknown>;
        }> => {
          const requests: Array<{
            file_path: string;
            file_name: string;
            file_type: string;
            chunk_index: number;
            tokens: number;
            file_metadata?: Record<string, unknown>;
          }> = [];
          
          items.forEach(item => {
            const currentPath = parentPath ? `${parentPath}/${item.name}` : item.name;
            
            // Add the current item
            requests.push({
              file_path: currentPath,
              file_name: item.name,
              file_type: item.Category || 'unknown',
              chunk_index: 0, // Default chunk index
              tokens: item.tokens || 0,
              file_metadata: {
                isDirectory: item.isDirectory || false,
                type: item.type || 'INTERNAL',
                category: item.Category || 'unknown',
              }
            });
            
            // Recursively add children
            if (item.children && item.children.length > 0) {
              requests.push(...convertToFileEmbeddingRequests(item.children, currentPath));
            }
          });
          
          return requests;
        };
        
        const fileEmbeddingRequests = convertToFileEmbeddingRequests(repoDependencies.children);
        
        // Add file dependencies to session
        await addMultipleFileDependencies(fileEmbeddingRequests);
        
        // Convert to ExtendedFileItem format for display
        const convertToExtendedItems = (items: FileDependencyNode[]): ExtendedFileItem[] => {
          return items.map(item => ({
            id: item.id,
            name: item.name,
            path: undefined, // FileDependencyNode doesn't have path property
            type: (item.type as 'INTERNAL' | 'EXTERNAL') || 'INTERNAL',
            tokens: item.tokens || 0,
            category: item.Category || 'unknown',
            isDirectory: item.isDirectory || false,
            children: item.children ? convertToExtendedItems(item.children) : [],
            expanded: false
          }));
        };
        
        setFiles(convertToExtendedItems(repoDependencies.children));
      } else {
        setFiles([]);
      }
    } catch (error) {
      console.error('[FileDependencies] Error force extracting file dependencies:', error);
      showError('Failed to extract file dependencies from repository');
      setFiles([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Optimized file tree rendering with proper TypeScript types
  const renderFileTree = useCallback((items: ExtendedFileItem[], depth = 0) => {
    return items.map((item) => {
      const hasChildren = item.children && item.children.length > 0;
      const isDirectory = item.isDirectory || hasChildren;
      
      return (
        <div key={item.id} className="select-none">
          <div
            className="flex items-center py-1 px-2 hover:bg-gray-100 cursor-pointer text-sm group"
            style={{ paddingLeft: `${depth * 20 + 8}px` }}
          >
            {hasChildren ? (
              <button
                onClick={() => toggleExpanded(item.id)}
                className="flex items-center justify-center w-4 h-4 mr-1 text-gray-400 hover:text-gray-600"
              >
                {item.expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            ) : (
              <div className="w-4 h-4 mr-1" />
            )}
            
            <div className="flex items-center mr-2">
              {isDirectory ? (
                <Folder size={16} className="text-blue-500" />
              ) : (
                <File size={16} className="text-gray-500" />
              )}
            </div>
            
            <span
              className="flex-1 truncate"
              onClick={() => !isDirectory && onShowDetails(item)}
            >
              {item.name || item.file_name}
            </span>
            
            <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {!isDirectory && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setLoadingStates(prev => ({ ...prev, [item.id]: true }));
                    onAddToContext(item);
                    setTimeout(() => {
                      setLoadingStates(prev => ({ ...prev, [item.id]: false }));
                    }, 1000);
                  }}
                  className="p-1 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded"
                  title="Add to context"
                  disabled={loadingStates[item.id]}
                >
                  {loadingStates[item.id] ? (
                    <RefreshCw size={12} className="animate-spin" />
                  ) : (
                    <Plus size={12} />
                  )}
                </button>
              )}
              
              <span className="text-xs text-gray-400 min-w-[3rem] text-right">
                {item.tokens}
              </span>
            </div>
          </div>
          
          {hasChildren && item.expanded && (
            <div>
              {renderFileTree(item.children, depth + 1)}
            </div>
          )}
        </div>
      );
    });
  }, [onAddToContext, onShowDetails, toggleExpanded, loadingStates]);

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="flex items-center justify-between p-4 border-b bg-gray-50">
        <div>
          <h3 className="font-semibold text-gray-800">File Dependencies</h3>
          <p className="text-sm text-gray-600 truncate">
            {sessionState.repositoryInfo?.full_name || 'No repository selected'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-md disabled:opacity-50"
            title="Refresh dependencies"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          {repoUrl && sessionState.repositoryInfo && (
            <button
              onClick={handleForceExtract}
              disabled={isLoading}
              className="p-2 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded-md disabled:opacity-50"
              title="Force extract from repository"
            >
              <Plus className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            <span className="ml-2 text-gray-600">
              {sessionState.fileContext.length === 0 ? 'Extracting file dependencies...' : 'Analyzing repository...'}
            </span>
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <File className="w-12 h-12 mx-auto mb-2 text-gray-300" />
            <p>No files found</p>
            <p className="text-sm">
              {sessionState.repositoryInfo ? 
                'Try refreshing or use the extract button to analyze the repository' : 
                'Select a repository to analyze file dependencies'
              }
            </p>
          </div>
        ) : (
          <div className="p-2">
            {renderFileTree(files)}
          </div>
        )}
      </div>

      <div className="p-2 border-t bg-gray-50 text-xs text-gray-500">
        Displayed files: {files.length} | Session files: {sessionState.fileContext.length} | Total tokens: {files.reduce((sum, file) => sum + (file.tokens || 0), 0)}
      </div>
    </div>
  );
};