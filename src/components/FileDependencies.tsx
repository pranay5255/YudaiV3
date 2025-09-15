import React, { useState, useCallback } from 'react';
import { Plus, File, RefreshCw } from 'lucide-react';
import { FileItem } from '../types';
import { useSessionStore } from '../stores/sessionStore';
import { useRepository } from '../hooks/useRepository';
import {
  useFileDependencies,
  useAddContextCard
} from '../hooks/useSessionQueries';
// react-query not needed here currently

interface FileDependenciesProps {
  onShowDetails: (file: FileItem) => void;
  onShowError?: (error: string) => void;
}

export const FileDependencies: React.FC<FileDependenciesProps> = ({
  onShowDetails,
  onShowError
}) => {
  // Zustand store for session ID, repository hook for repository state
  const { activeSessionId } = useSessionStore();
  const { selectedRepository } = useRepository();
  
  // React Query hooks for data and mutations
  const { data: fileContext = [], isLoading, refetch } = useFileDependencies(activeSessionId || '');
  const addContextCardMutation = useAddContextCard();
  
  // no queryClient needed; extraction is deprecated
  const [loadingStates, setLoadingStates] = useState<{[key: string]: boolean}>({});

  const showError = useCallback((message: string) => {
    if (onShowError) {
      onShowError(message);
    }
  }, [onShowError]);

  const handleRefresh = async () => {
    console.log('[FileDependencies] Refreshing file dependencies...');
    refetch();
  };

  // Extraction is deprecated; indexing happens automatically.

  const handleAddToContext = useCallback(async (item: FileItem) => {
    if (!activeSessionId) {
      showError?.('No active session to add context to');
      return;
    }

    setLoadingStates(prev => ({ ...prev, [item.id]: true }));
    
    addContextCardMutation.mutate({
      sessionId: activeSessionId,
      card: {
        title: item.name,
        description: item.path || '',
        source: 'file-deps',
        tokens: item.tokens,
      },
    }, {
      onError: () => showError?.('Failed to add file to context'),
      onSettled: () => setLoadingStates(prev => ({ ...prev, [item.id]: false })),
    });
  }, [activeSessionId, showError, addContextCardMutation]);

  // Simple file list rendering
  const renderFileList = useCallback((items: FileItem[]) => {
    return items.map((item) => (
      <div key={item.id} className="select-none">
        <div className="flex items-center py-2 px-3 hover:bg-gray-100 cursor-pointer text-sm group border-b border-gray-100">
          <div className="flex items-center mr-3">
            <File size={16} className="text-gray-500" />
          </div>
          
          <div className="flex-1 min-w-0">
            <span
              className="block text-gray-900 truncate hover:text-blue-600"
              onClick={() => onShowDetails(item)}
              title={item.name}
            >
              {item.name}
            </span>
            {item.path && (
              <span className="text-xs text-gray-500 truncate block" title={item.path}>
                {item.path}
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="text-xs text-gray-400 font-mono">
              {item.tokens} tokens
            </span>
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
          </div>
        </div>
      </div>
    ));
  }, [handleAddToContext, onShowDetails, loadingStates]);

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="flex items-center justify-between p-4 border-b bg-gray-50">
        <div>
          <h3 className="font-semibold text-gray-800">File Dependencies</h3>
          <p className="text-sm text-gray-600 truncate">
            {selectedRepository?.repository.full_name || 'No repository selected'}
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
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            <span className="ml-2 text-gray-600">
              Loading...
            </span>
          </div>
        ) : fileContext.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <File className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <div className="space-y-2">
              <p className="font-medium">No file dependencies found</p>
              <p className="text-sm">
                {selectedRepository
                  ? 'Indexing happens automatically after repository selection. Please wait or refresh.'
                  : 'Select a repository to analyze file dependencies'}
              </p>
            </div>
          </div>
        ) : (
          <div>
            {renderFileList(fileContext)}
          </div>
        )}
      </div>

      {fileContext.length > 0 && (
        <div className="p-3 border-t bg-gray-50 text-xs text-gray-500">
          <div className="flex justify-between items-center">
            <span>
              Files: {fileContext.length} | Total tokens: {fileContext.reduce((sum, file) => sum + (file.tokens || 0), 0)}
            </span>
            <span>Session: {activeSessionId?.slice(-8) || 'None'}</span>
          </div>
          <div className="mt-1 text-xs text-blue-600">
            💡 Files are automatically included in chat context and GitHub issue creation
          </div>
        </div>
      )}
    </div>
  );
};
