import React, { useState, useCallback, useEffect } from 'react';
import { ChevronRight, ChevronDown, Plus, Folder, File, RefreshCw } from 'lucide-react';
import { FileItem } from '../types';
import { useSessionState, useFileDependencyManagement, useContextCardManagement } from '../hooks/useSessionState';

interface FileDependenciesProps {
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
  onShowDetails,
  onShowError,
  repoUrl
}) => {
  const sessionState = useSessionState();
  const { loadFileDependencies: loadFileDeps, extractFileDependenciesForSession } = useFileDependencyManagement();
  const { addContextCard } = useContextCardManagement();
  const [files, setFiles] = useState<ExtendedFileItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStates, setLoadingStates] = useState<{[key: string]: boolean}>({});
  const [loaded, setLoaded] = useState(false);

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

  const loadDeps = useCallback(async () => {
    if (loaded) return;
    if (!sessionState.sessionId) {
      setFiles([]);
      return;
    }

    if (sessionState.fileContext && sessionState.fileContext.length > 0) {
      const converted: ExtendedFileItem[] = sessionState.fileContext.map(dep => ({
        id: dep.id.toString(),
        name: dep.name || dep.file_name || '',
        path: dep.path || dep.file_path,
        type: dep.type || 'INTERNAL',
        tokens: dep.tokens,
        category: dep.category || dep.file_type || 'unknown',
        isDirectory: false,
        children: [],
        expanded: false,
      }));
      setFiles(converted);
      setLoaded(true);
    } else if (repoUrl) {
      setIsLoading(true);
      try {
        await extractFileDependenciesForSession(repoUrl);
      } catch (error) {
        showError('Failed to load file dependencies');
      } finally {
        setIsLoading(false);
      }
    }
  }, [loaded, sessionState.sessionId, sessionState.fileContext, repoUrl, extractFileDependenciesForSession, showError]);

  // Load file dependencies when session changes
  useEffect(() => {
    loadDeps();
  }, [loadDeps, sessionState.fileContext, sessionState.sessionId]);

  const handleRefresh = async () => {
    console.log('[FileDependencies] Refreshing file dependencies...');
    setIsLoading(true);
    try {
      await loadFileDeps();
      setLoaded(false);
      await loadDeps();
    } finally {
      setIsLoading(false);
    }
  };

  const handleForceExtract = async () => {
    if (!repoUrl) {
      console.log('[FileDependencies] Cannot force extract: no repository URL');
      return;
    }

    console.log('[FileDependencies] Force extracting file dependencies from repository:', repoUrl);
    setIsLoading(true);

    try {
      await extractFileDependenciesForSession(repoUrl);
      await loadFileDeps();
      setLoaded(false);
      await loadDeps();
    } catch (error) {
      console.error('[FileDependencies] Error force extracting file dependencies:', error);
      showError('Failed to extract file dependencies from repository');
      setFiles([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddToContext = async (item: ExtendedFileItem) => {
    setLoadingStates(prev => ({ ...prev, [item.id]: true }));
    try {
      await addContextCard({
        title: item.name || item.file_name || 'File',
        description: item.path || '',
        source: 'file-deps',
        tokens: item.tokens,
      });
    } catch {
      showError?.('Failed to add file to context');
    } finally {
      setLoadingStates(prev => ({ ...prev, [item.id]: false }));
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
                    handleAddToContext(item);
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
  }, [handleAddToContext, onShowDetails, toggleExpanded, loadingStates]);

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
        <div className="flex justify-between items-center">
          <span>Files: {files.length} | Total tokens: {files.reduce((sum, file) => sum + (file.tokens || 0), 0)}</span>
          <span>Session files: {sessionState.fileContext.length}</span>
        </div>
        {sessionState.fileContext.length > 0 && (
          <div className="mt-1 text-xs text-blue-600">
            💡 Tip: Files are automatically included in chat context and GitHub issue creation
          </div>
        )}
      </div>
    </div>
  );
};