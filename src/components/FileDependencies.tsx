import React, { useState, useEffect, useCallback } from 'react';
import { ChevronRight, ChevronDown, Plus, Folder, File, RefreshCw } from 'lucide-react';
import { UnifiedFileEmbedding } from '../types/unifiedState';
import { useRepository } from '../hooks/useRepository';
import { ApiService } from '../services/api';

interface FileDependenciesProps {
  onAddToContext: (file: UnifiedFileEmbedding) => void;
  onShowDetails: (file: UnifiedFileEmbedding) => void;
  repoUrl?: string; // Optional repository URL to analyze
}


// Flat file item returned from database
interface DbFileItem {
  id: number;
  name: string;
  path: string;
  file_type: 'INTERNAL' | 'EXTERNAL';
  category: string;
  tokens: number;
  is_directory: boolean;
}

const buildFileTreeFromDb = (items: DbFileItem[]): UnifiedFileEmbedding[] => {
  const fileMap: { [key: string]: UnifiedFileEmbedding & { children: UnifiedFileEmbedding[] } } = {};
  const roots: UnifiedFileEmbedding[] = [];

  items.forEach(item => {
    fileMap[item.path] = {
        id: item.id,
        session_id: '',
        file_name: item.name,
        file_path: item.path,
        file_type: item.file_type,
        tokens: item.tokens,
        created_at: new Date().toISOString(),
        children: []
    };
  });

  items.forEach(item => {
    const parentPath = item.path.substring(0, item.path.lastIndexOf('/'));
    if (parentPath && fileMap[parentPath]) {
      fileMap[parentPath].children.push(fileMap[item.path]);
    } else {
      roots.push(fileMap[item.path]);
    }
  });

  return roots;
};



export const FileDependencies: React.FC<FileDependenciesProps> = ({ 
  onAddToContext, 
  onShowDetails,
  repoUrl 
}) => {
  const { selectedRepository } = useRepository();
  const [files, setFiles] = useState<UnifiedFileEmbedding[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRepositoryData = useCallback(async (url: string) => {
    setLoading(true);
    setError(null);

    try {
      console.log(`Fetching repository data for: ${url}`);

      // First check if repository exists in the database
      const repoInDb = await ApiService.getRepositoryByUrl(url);
      if (repoInDb && repoInDb.id) {
        console.log('Repository found in database');
        const dbFiles: DbFileItem[] = await ApiService.getRepositoryFiles(repoInDb.id);
        if (dbFiles.length > 0) {
          const tree = buildFileTreeFromDb(dbFiles);
          setFiles(tree);
          setLoading(false);
          return;
        }
      }

      // If not found or no files, fall back to extraction endpoint
      // const data: ApiFileItem = await ApiService.extractFileDependencies(url, 30000);

      // const transformData = (item: ApiFileItem): UnifiedFileEmbedding => ({
      //   id: Number(item.id) || 0,
      //   session_id: '',
      //   file_name: item.name || 'Unknown',
      //   file_path: item.name,
      //   file_type: 'INTERNAL',
      //   tokens: item.tokens || 0,
      //   created_at: new Date().toISOString()
      // });

       // const rootItem = transformData(data);
       // const transformedData = rootItem.children || [];
       // setFiles(transformedData);
    } catch (err) {
      console.error('Failed to fetch repository data:', err);
      
      // Provide more specific error messages
      let errorMessage = 'Failed to fetch repository data';
      if (err instanceof Error) {
        if (err.message.includes('fetch')) {
          errorMessage = 'Unable to connect to the server. Please check your connection.';
        } else if (err.message.includes('Invalid repository')) {
          errorMessage = err.message;
        } else if (err.message.includes('not found')) {
          errorMessage = err.message;
        } else if (err.message.includes('Server error')) {
          errorMessage = err.message;
        } else {
          errorMessage = err.message;
        }
      }
      
      setError(errorMessage);
      setFiles([]); // Set empty array instead of sample data
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch repository data when selectedRepository changes
  useEffect(() => {
    if (selectedRepository) {
      // Construct the repository URL from the selected repository
      const repoUrl = selectedRepository.repository.html_url;
      fetchRepositoryData(repoUrl);
    } else if (repoUrl) {
      // Fallback to provided repoUrl prop if no repository selected
      fetchRepositoryData(repoUrl);
    } else {
      // No repository selected and no repoUrl provided
      setFiles([]);
      setError(null);
    }
  }, [selectedRepository, repoUrl, fetchRepositoryData]);

  const handleRefresh = useCallback(() => {
    if (selectedRepository) {
      const repoUrl = selectedRepository.repository.html_url;
      fetchRepositoryData(repoUrl);
    } else if (repoUrl) {
      fetchRepositoryData(repoUrl);
    }
  }, [selectedRepository, repoUrl, fetchRepositoryData]);

  const toggleExpanded = useCallback((id: number) => {
    const updateFiles = (items: (UnifiedFileEmbedding & { children: UnifiedFileEmbedding[], expanded: boolean })[]): (UnifiedFileEmbedding & { children: UnifiedFileEmbedding[], expanded: boolean })[] => {
      return items.map(item => {
        if (item.id === id) {
          return { ...item, expanded: !item.expanded };
        }
        if (item.children) {
          return { ...item, children: updateFiles(item.children as (UnifiedFileEmbedding & { children: UnifiedFileEmbedding[], expanded: boolean })[]) };
        }
        return item;
      });
    };
    setFiles(updateFiles(files as (UnifiedFileEmbedding & { children: UnifiedFileEmbedding[], expanded: boolean })[]));
  }, [files]);

  const getTokenBadgeColor = useCallback((tokens: number) => {
    if (tokens === 0) return 'bg-zinc-700 text-fg/60';
    if (tokens < 1000) return 'bg-red-900/20 text-red-900';
    if (tokens < 800) return 'bg-red-600/20 text-red-600';
    if (tokens < 700) return 'bg-red-500/20 text-red-500';
    if (tokens < 600) return 'bg-red-400/20 text-red-400';
    if (tokens < 500) return 'bg-orange-500/20 text-orange-500';
    if (tokens < 400) return 'bg-amber-500/20 text-amber-500';
    if (tokens < 300) return 'bg-yellow-500/20 text-yellow-500';
    if (tokens < 200) return 'bg-lime-500/20 text-lime-500';
    if (tokens < 100) return 'bg-green-500/20 text-green-500';
    return 'bg-emerald-500/20 text-emerald-500';
  }, []);

  const renderFileTree = useCallback((items: (UnifiedFileEmbedding & { children: UnifiedFileEmbedding[], expanded: boolean })[], depth = 0) => {
    return items.map((item) => (
      <React.Fragment key={item.id}>
        <tr
          className="hover:bg-zinc-800/50 transition-colors cursor-pointer group"
          onClick={() => (item.children && item.children.length > 0) ? toggleExpanded(item.id) : onShowDetails(item)}
        >
          <td className="px-4 py-3">
            <div className="flex items-center gap-2" style={{ marginLeft: `${depth * 1.5}rem` }}>
              {(item.children && item.children.length > 0) ? (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpanded(item.id);
                    }}
                    className="p-0.5 hover:bg-zinc-700 rounded transition-transform"
                  >
                    {item.expanded ? (
                      <ChevronDown className="w-4 h-4 text-fg" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-fg" />
                    )}
                  </button>
                  <Folder className="w-4 h-4 text-accent" />
                </>
              ) : (
                <>
                  <div className="w-5" />
                  <File className="w-4 h-4 text-fg/60" />
                </>
              )}
              <span className="text-sm text-fg">{item.file_name}</span>
            </div>
          </td>
          <td className="px-4 py-3">
            <span className={`
              px-2 py-0.5 rounded text-xs font-medium
              ${item.file_type === 'INTERNAL'
                ? 'bg-primary/20 text-primary'
                : 'bg-zinc-700 text-fg/80'
              }
            `}>
              {item.file_type}
            </span>
          </td>
          <td className="px-4 py-3">
            <span className="text-sm text-fg/80">
              File
            </span>
          </td>
          <td className="px-4 py-3">
            {item.tokens > 0 && (
              <span className={`
                px-2 py-0.5 rounded-full text-xs font-medium
                ${getTokenBadgeColor(item.tokens)}
              `}>
                {item.tokens.toLocaleString()}
              </span>
            )}
          </td>
          <td className="px-4 py-3">
            {!(item.children && item.children.length > 0) && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onAddToContext(item);
                }}
                className="opacity-0 group-hover:opacity-100 transition-opacity
                         p-1 hover:bg-primary/20 rounded text-primary"
                aria-label="Add to context"
              >
                <Plus className="w-4 h-4" />
              </button>
            )}
          </td>
        </tr>
        {(item.children && item.children.length > 0) && item.expanded && (
          renderFileTree(item.children as (UnifiedFileEmbedding & { children: UnifiedFileEmbedding[], expanded: boolean })[], depth + 1)
        )}
      </React.Fragment>
    ));
  }, [toggleExpanded, onShowDetails, onAddToContext, getTokenBadgeColor]);

  return (
    <div className="h-full flex flex-col">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div>
          <h3 className="text-sm font-medium text-fg">File Dependencies</h3>
          {selectedRepository && (
            <p className="text-xs text-fg/60 mt-1">
              {selectedRepository.repository.full_name} ({selectedRepository.branch})
            </p>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading || (!selectedRepository && !repoUrl)}
          className="p-2 hover:bg-zinc-800 rounded transition-colors disabled:opacity-50"
          aria-label="Refresh repository data"
        >
          <RefreshCw className={`w-4 h-4 text-fg ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="p-8 space-y-2 animate-pulse">
          <div className="flex items-center gap-2 text-fg/60">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Analyzing repository...</span>
          </div>
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-4 bg-zinc-800 rounded" />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="p-4 border-b border-zinc-800">
          <div className="text-sm text-error bg-error/10 p-3 rounded">
            <p className="font-medium">Failed to load repository data</p>
            <p className="text-xs mt-1">{error}</p>
            <button
              onClick={handleRefresh}
              className="mt-2 text-xs text-error hover:underline"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {/* File tree table */}
      <div className="flex-1 overflow-auto">
        {!selectedRepository && !repoUrl && !loading && !error && (
          <div className="flex items-center justify-center p-8">
            <div className="text-center text-fg/60">
              <p className="text-sm">No repository selected</p>
              <p className="text-xs mt-1">Please select a repository from the user profile menu</p>
            </div>
          </div>
        )}
        
        {(selectedRepository || repoUrl || files.length > 0) && !loading && !error && (
          <table className="w-full">
            <thead className="border-b border-zinc-800 sticky top-0 bg-bg">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-fg">Name</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-fg">Type</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-fg">Category</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-fg">Tokens</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-fg"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 text-sm">
              {renderFileTree(files as (UnifiedFileEmbedding & { children: UnifiedFileEmbedding[], expanded: boolean })[])}
            </tbody>
          </table>
        )}
        
        {/* Empty state when no files found */}
        {!loading && !error && files.length === 0 && (selectedRepository || repoUrl) && (
          <div className="flex items-center justify-center p-8">
            <div className="text-center text-fg/60">
              <p className="text-sm">No files found</p>
              <p className="text-xs mt-1">This repository appears to be empty or contains no analyzable files</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};