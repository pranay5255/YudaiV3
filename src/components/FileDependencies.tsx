import React, { useState, useEffect, useCallback } from 'react';
import { ChevronRight, ChevronDown, Plus, Folder, File, RefreshCw } from 'lucide-react';
import { FileItem, FileItemAPIResponse } from '../types';

interface FileDependenciesProps {
  onAddToContext: (file: FileItem) => void;
  onShowDetails: (file: FileItem) => void;
  repoUrl?: string; // Optional repository URL to analyze
}

// Default repository URL - you can change this to your preferred default
const DEFAULT_REPO_URL = "https://github.com/pranay5255/pranay5255";


export const FileDependencies: React.FC<FileDependenciesProps> = ({ 
  onAddToContext, 
  onShowDetails,
  repoUrl 
}) => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRepositoryData = useCallback(async (url: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/extract', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_url: url,
          max_file_size: 30000, // 30KB limit
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Transform the API response to match our FileItem structure
      const transformData = (items: FileItemAPIResponse[]): FileItem[] => {
        return items.map((item, index) => ({
          id: item.id || `item-${index}`,
          name: item.name || item.path || 'Unknown',
          path: item.path,
          type: normalizeFileType(item.type), // Convert to proper type
          tokens: item.tokens || 0,
          Category: item.category || item.Category || 'File',
          isDirectory: item.isDirectory || false,
          expanded: item.isDirectory ? false : undefined,
          children: item.children ? transformData(item.children) : undefined
        }));
      };

      // Use the transformed data or fallback to empty array
      const transformedData = data.children ? transformData(data.children) : [];
      setFiles(transformedData);
    } catch (err) {
      console.error('Failed to fetch repository data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch repository data');
      setFiles([]); // Set empty array instead of sample data
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch repository data when repoUrl changes
  useEffect(() => {
    const urlToUse = repoUrl || DEFAULT_REPO_URL;
    fetchRepositoryData(urlToUse);
  }, [repoUrl, fetchRepositoryData]);

  // Helper function to normalize file type to match our enum
  const normalizeFileType = (type?: string): 'INTERNAL' | 'EXTERNAL' => {
    if (!type) return 'INTERNAL';
    
    // Normalize common variations
    const normalizedType = type.toUpperCase().trim();
    if (normalizedType === 'INTERNAL' || normalizedType === 'EXTERNAL') {
      return normalizedType as 'INTERNAL' | 'EXTERNAL';
    }
    
    // Default mapping based on common patterns
    if (normalizedType.includes('EXTERNAL') || normalizedType.includes('DEPENDENCY')) {
      return 'EXTERNAL';
    }
    
    return 'INTERNAL'; // Default fallback
  };

  const handleRefresh = () => {
    const urlToUse = repoUrl || DEFAULT_REPO_URL;
    fetchRepositoryData(urlToUse);
  };

  const toggleExpanded = (id: string) => {
    const updateFiles = (items: FileItem[]): FileItem[] => {
      return items.map(item => {
        if (item.id === id) {
          return { ...item, expanded: !item.expanded };
        }
        if (item.children) {
          return { ...item, children: updateFiles(item.children) };
        }
        return item;
      });
    };
    setFiles(updateFiles(files));
  };
  const getTokenBadgeColor = (tokens: number) => {
    if (tokens === 0) return 'bg-zinc-700 text-fg/60';
    if (tokens < 10000) return 'bg-red-900/20 text-red-900';
    if (tokens < 8000) return 'bg-red-600/20 text-red-600';
    if (tokens < 7000) return 'bg-red-500/20 text-red-500';
    if (tokens < 6000) return 'bg-red-400/20 text-red-400';
    if (tokens < 5000) return 'bg-orange-500/20 text-orange-500';
    if (tokens < 4000) return 'bg-amber-500/20 text-amber-500';
    if (tokens < 3000) return 'bg-yellow-500/20 text-yellow-500';
    if (tokens < 2000) return 'bg-lime-500/20 text-lime-500';
    if (tokens < 1000) return 'bg-green-500/20 text-green-500';
    return 'bg-emerald-500/20 text-emerald-500';
  };

  const renderFileTree = (items: FileItem[], depth = 0) => {
    return items.map((item) => (
      <React.Fragment key={item.id}>
        <tr 
          className="hover:bg-zinc-800/50 transition-colors cursor-pointer group"
          onClick={() => item.isDirectory ? toggleExpanded(item.id) : onShowDetails(item)}
        >
          <td className="px-4 py-3">
            <div className="flex items-center gap-2" style={{ marginLeft: `${depth * 1.5}rem` }}>
              {item.isDirectory ? (
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
              <span className="text-sm text-fg">{item.name}</span>
            </div>
          </td>
          <td className="px-4 py-3">
            <span className={`
              px-2 py-0.5 rounded text-xs font-medium
              ${item.type === 'INTERNAL' 
                ? 'bg-primary/20 text-primary' 
                : 'bg-zinc-700 text-fg/80'
              }
            `}>
              {item.type}
            </span>
          </td>
          <td className="px-4 py-3">
            <span className="text-sm text-fg/80">
              {item.Category}
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
            {!item.isDirectory && (
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
        {item.isDirectory && item.expanded && item.children && (
          renderFileTree(item.children, depth + 1)
        )}
      </React.Fragment>
    ));
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <h3 className="text-sm font-medium text-fg">File Dependencies</h3>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="p-2 hover:bg-zinc-800 rounded transition-colors disabled:opacity-50"
          aria-label="Refresh repository data"
        >
          <RefreshCw className={`w-4 h-4 text-fg ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center p-8">
          <div className="flex items-center gap-2 text-fg/60">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Analyzing repository...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="p-4 border-b border-zinc-800">
          <div className="text-sm text-error bg-error/10 p-3 rounded">
            <p className="font-medium">Failed to load repository data</p>
            <p className="text-xs mt-1">{error}</p>
            <p className="text-xs mt-1 text-fg/60">Showing sample data instead.</p>
          </div>
        </div>
      )}

      {/* File tree table */}
      <div className="flex-1 overflow-auto">
        {!repoUrl && !loading && !error && (
          <div className="flex items-center justify-center p-8">
            <div className="text-center text-fg/60">
              <p className="text-sm">Using default repository: {DEFAULT_REPO_URL}</p>
              <p className="text-xs mt-1">Pass a repoUrl prop to analyze a different repository</p>
            </div>
          </div>
        )}
        
        {(repoUrl || files.length > 0) && (
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
              {renderFileTree(files)}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};