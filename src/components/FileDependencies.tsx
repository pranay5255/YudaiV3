import React, { useState, useEffect, useCallback } from 'react';
import { ChevronRight, ChevronDown, Plus, Folder, File, RefreshCw } from 'lucide-react';
import { FileItem } from '../types/fileDependencies';
import { ApiService } from '../services/api';

interface FileDependenciesProps {
  onAddToContext: (file: FileItem) => void;
  onShowDetails: (file: FileItem) => void;
  repoUrl?: string; // Optional repository URL to analyze
}

// Note: buildFileTreeFromDb function available for future database integration
// Currently using API-based file structure from GitIngest

interface ApiFileItem {
  id: string;
  name: string;
  type: 'INTERNAL' | 'EXTERNAL';
  tokens: number;
  Category: string;
  isDirectory?: boolean;
  children?: ApiFileItem[];
  expanded?: boolean;
}

export const FileDependencies: React.FC<FileDependenciesProps> = ({ 
  onAddToContext, 
  onShowDetails, 
  repoUrl 
}) => {
  // Repository context removed - using repoUrl prop directly
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingStates, setLoadingStates] = useState<{[key: string]: boolean}>({});

  // Use the repoUrl prop directly
  const targetRepoUrl = repoUrl;

  useEffect(() => {
    if (targetRepoUrl) {
      loadFileDependencies();
    }
  }, [targetRepoUrl]);

  const loadFileDependencies = async () => {
    if (!targetRepoUrl) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await ApiService.extractFileDependencies(targetRepoUrl);
      if (data && data.children) {
        setFiles(transformData(data.children));
      } else {
        setFiles([]);
      }
    } catch (err) {
      console.error('Failed to load file dependencies:', err);
      setError('Failed to load file dependencies');
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  const transformData = (items: ApiFileItem[]): FileItem[] => {
    return items.map(item => ({
      id: item.id,
      file_name: item.name,
      file_path: item.name,
      file_type: item.type,
      content_summary: item.Category,
      tokens: item.tokens,
      created_at: new Date().toISOString(),
      children: item.children ? transformData(item.children) : [],
      expanded: item.expanded || false
    }));
  };

  const updateFiles = (items: (FileItem & { children: FileItem[], expanded: boolean })[]): (FileItem & { children: FileItem[], expanded: boolean })[] => {
    return items.map(item => {
      if (item.children && item.children.length > 0) {
        return { ...item, children: updateFiles(item.children as (FileItem & { children: FileItem[], expanded: boolean })[]) };
      }
      return item;
    });
  };

  const handleRefresh = () => {
    setFiles(updateFiles(files as (FileItem & { children: FileItem[], expanded: boolean })[]));
  };

  const toggleExpanded = useCallback((targetId: string) => {
    const toggleInTree = (items: FileItem[]): FileItem[] => {
      return items.map(item => {
        if (item.id === targetId) {
          return { ...item, expanded: !(item as any).expanded };
        }
        if ((item as any).children) {
          return { ...item, children: toggleInTree((item as any).children) };
        }
        return item;
      });
    };
    setFiles(toggleInTree(files));
  }, [files]);

  const renderFileTree = useCallback((items: (FileItem & { children: FileItem[], expanded: boolean })[], depth = 0) => {
    return items.map((item) => {
      const hasChildren = item.children && item.children.length > 0;
      const isDirectory = hasChildren;
      
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
              {item.file_name}
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
              {renderFileTree(item.children as (FileItem & { children: FileItem[], expanded: boolean })[], depth + 1)}
            </div>
          )}
        </div>
      );
    });
  }, [onAddToContext, onShowDetails, toggleExpanded, loadingStates]);



  if (!targetRepoUrl) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Folder className="w-12 h-12 mx-auto mb-2 text-gray-300" />
        <p>No repository selected</p>
        <p className="text-sm">Select a repository to view file dependencies</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="flex items-center justify-between p-4 border-b bg-gray-50">
        <div>
          <h3 className="font-semibold text-gray-800">File Dependencies</h3>
          <p className="text-sm text-gray-600 truncate">
            {targetRepoUrl}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-md disabled:opacity-50"
          title="Refresh dependencies"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            <span className="ml-2 text-gray-600">Analyzing repository...</span>
          </div>
        ) : error ? (
          <div className="p-4 text-center">
            <div className="text-red-500 mb-2">⚠️ {error}</div>
            <button
              onClick={loadFileDependencies}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Retry
            </button>
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <File className="w-12 h-12 mx-auto mb-2 text-gray-300" />
            <p>No files found</p>
            <p className="text-sm">Try refreshing or check the repository URL</p>
          </div>
        ) : (
          <div className="p-2">
            {renderFileTree(files as (FileItem & { children: FileItem[], expanded: boolean })[])}
          </div>
        )}
      </div>

      <div className="p-2 border-t bg-gray-50 text-xs text-gray-500">
        Total files: {files.length} | Total tokens: {files.reduce((sum, file) => sum + file.tokens, 0)}
      </div>
    </div>
  );
};