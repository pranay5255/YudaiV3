import React, { useState, useCallback } from 'react';
import { Plus, File, RefreshCw } from 'lucide-react';
import { FileItem } from '../types';
import { useSessionStore } from '../stores/sessionStore';
import { useRepository } from '../hooks/useRepository';
import {
  useFileDependencies,
  useAddContextCard
} from '../hooks/useSessionQueries';
import { logger } from '../utils/logger';
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
    logger.info('[FileDependencies] Refreshing file dependencies...');
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
    return items.map((item, index) => (
      <div
        key={item.id}
        className="select-none animate-fade-in"
        style={{ animationDelay: `${index * 30}ms` }}
      >
        <div className="flex items-center py-3 px-4 hover:bg-bg-tertiary cursor-pointer text-sm group border-b border-border/50 transition-all duration-200">
          <div className="flex items-center mr-3">
            <div className="w-8 h-8 rounded-lg bg-bg-tertiary border border-border flex items-center justify-center group-hover:border-amber/30 transition-colors">
              <File size={14} className="text-muted group-hover:text-amber transition-colors" />
            </div>
          </div>

          <div className="flex-1 min-w-0">
            <span
              className="block text-fg font-mono text-sm truncate hover:text-amber cursor-pointer transition-colors"
              onClick={() => onShowDetails(item)}
              title={item.name}
            >
              {item.name}
            </span>
            {item.path && (
              <span className="text-xs text-muted font-mono truncate block" title={item.path}>
                {item.path}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <span className="text-xs text-muted font-mono bg-bg-tertiary border border-border px-2 py-1 rounded-lg">
              {item.tokens} tokens
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleAddToContext(item);
              }}
              className="p-2 text-muted hover:text-success hover:bg-success/10 rounded-lg border border-transparent hover:border-success/20 transition-all duration-200"
              title="Add to context"
              disabled={loadingStates[item.id]}
            >
              {loadingStates[item.id] ? (
                <RefreshCw size={14} className="animate-spin" />
              ) : (
                <Plus size={14} />
              )}
            </button>
          </div>
        </div>
      </div>
    ));
  }, [handleAddToContext, onShowDetails, loadingStates]);

  return (
    <div className="h-full flex flex-col bg-bg terminal-noise">
      <div className="flex items-center justify-between p-4 border-b border-border bg-bg-secondary">
        <div>
          <h3 className="font-mono font-semibold text-fg text-sm">File Dependencies</h3>
          <p className="text-xs text-muted font-mono truncate mt-0.5">
            {selectedRepository?.repository.full_name || 'No repository selected'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="p-2 text-muted hover:text-fg hover:bg-bg-tertiary rounded-lg transition-all duration-200 disabled:opacity-50 border border-border hover:border-border-accent"
            title="Refresh dependencies"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-amber' : ''}`} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="flex items-center gap-3">
              <RefreshCw className="w-5 h-5 animate-spin text-amber" />
              <span className="text-sm text-muted font-mono">Loading...</span>
            </div>
          </div>
        ) : fileContext.length === 0 ? (
          <div className="text-center py-12 animate-fade-in">
            <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-bg-tertiary border border-border flex items-center justify-center">
              <File className="w-8 h-8 text-muted" />
            </div>
            <div className="space-y-2">
              <p className="font-mono font-medium text-fg-secondary text-sm">No file dependencies found</p>
              <p className="text-xs text-muted font-mono max-w-xs mx-auto">
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
        <div className="p-3 border-t border-border bg-bg-secondary">
          <div className="flex justify-between items-center text-xs font-mono text-muted">
            <span>
              Files: {fileContext.length} &bull; Total tokens: {fileContext.reduce((sum, file) => sum + (file.tokens || 0), 0).toLocaleString()}
            </span>
            <span className="text-muted/60">Session: {activeSessionId?.slice(-8) || 'None'}</span>
          </div>
          <div className="mt-2 text-xs font-mono flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan" />
            <span className="text-cyan/80">Files are automatically included in chat context and GitHub issue creation</span>
          </div>
        </div>
      )}
    </div>
  );
};
