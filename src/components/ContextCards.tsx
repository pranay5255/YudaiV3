import React, { useState, useCallback, useEffect } from 'react';
import { Trash2, FileText, MessageCircle, Upload } from 'lucide-react';
import type {
  ChatContextMessage,
  FileContextItem,
  GitHubIssuePreview
} from '../types/api';
import type { CreateIssueWithContextRequest } from '../types/sessionTypes';
import { UserIssueResponse, ContextCard } from '../types';
import { useSessionStore } from '../stores/sessionStore';
import { useRepository } from '../hooks/useRepository';

interface IssuePreviewData extends GitHubIssuePreview {
  userIssue?: UserIssueResponse;
  conversationContext: ChatContextMessage[];
  fileContext: FileContextItem[];
  canCreateGitHubIssue: boolean;
  repositoryInfo?: {
    owner: string;
    name: string;
    branch?: string;
  };
}

interface ContextCardsProps {
  cards: ContextCard[];
  onRemoveCard: (id: string) => void;
  onCreateIssue?: () => void;
  onShowIssuePreview?: (issuePreview: IssuePreviewData) => void;
  onShowError?: (error: string) => void;
  repositoryInfo?: {
    owner: string;
    name: string;
    branch?: string;
  };
}

export const ContextCards: React.FC<ContextCardsProps> = ({ 
  cards = [], 
  onRemoveCard = () => {}, 
  onShowIssuePreview, 
  onShowError, 
  repositoryInfo 
}) => {
  // Zustand store for state management
  const { activeSessionId } = useSessionStore();
  const { selectedRepository } = useRepository();
  
  const { deleteContextCard, createIssueWithContext } = useSessionStore();
  const [isLoading, setIsLoading] = useState(false);

  const showError = useCallback((message: string) => {
    if (onShowError) {
      onShowError(message);
    } else {
      console.error('ContextCards Error:', message);
    }
  }, [onShowError]);

  // Load context cards when session changes (cards are now passed as props from parent)
  useEffect(() => {
    if (activeSessionId && cards.length === 0) {
      console.log('Context cards available:', cards.length);
    }
  }, [activeSessionId, cards]);

  const removeContextCard = useCallback(async (cardId: string) => {
    if (!activeSessionId) return;
    
    try {
      console.log('Removing context card:', cardId);
      await deleteContextCard(cardId);
      console.log('Context card removed successfully');
      // Call the onRemoveCard callback to update the parent state
      onRemoveCard(cardId);
    } catch (error) {
      console.error('Failed to remove context card:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to remove context card';
      showError(`Failed to remove context card: ${errorMessage}`);
    }
  }, [activeSessionId, deleteContextCard, onRemoveCard, showError]);

  const getSourceIcon = (source: ContextCard['source']) => {
    switch (source) {
      case 'chat': return MessageCircle;
      case 'file-deps': return FileText;
      case 'upload': return Upload;
      default: return FileText;
    }
  };

  const getTokenHeatColor = (tokens: number) => {
    if (tokens < 300) return 'from-teal-500 to-teal-500';
    if (tokens < 700) return 'from-teal-500 to-amber-500';
    return 'from-amber-500 to-red-500';
  };

  const totalTokens = cards.reduce((sum, card) => sum + card.tokens, 0);

  // Handle create GitHub issue with context cards using unified API
  const handleCreateGitHubIssue = useCallback(async () => {
    const repoInfo = repositoryInfo || (selectedRepository ? {
      owner: selectedRepository.repository.owner?.login || selectedRepository.repository.full_name.split('/')[0],
      name: selectedRepository.repository.name,
      branch: selectedRepository.branch
    } : null);
    
    if (isLoading || !repoInfo) {
      if (!repoInfo) {
        showError('No repository selected. Please select a repository first.');
      }
      return;
    }
    
    setIsLoading(true);
    
    try {
      // Separate chat and file context
      const chatCards = cards.filter(card => card.source === 'chat');
      const fileCards = cards.filter(card => card.source === 'file-deps');

      // Convert to API formats with proper typing
      const conversationMessages: ChatContextMessage[] = chatCards.map(card => ({
        id: card.id,
        content: `${card.title}\n${card.description}`,
        isCode: false,
        timestamp: new Date().toISOString(),
      }));
      
      const fileContextItems: FileContextItem[] = fileCards.map(card => ({
        id: card.id,
        name: card.title,
        type: 'INTERNAL',
        tokens: card.tokens,
        category: card.source,
        path: card.title,
      }));

      const request: CreateIssueWithContextRequest = {
        title: `Issue from Context Cards - ${repoInfo.name}`,
        description: 'This issue was generated from context cards including chat messages and file dependencies.',
        chat_messages: conversationMessages,
        file_context: fileContextItems,
        repository_info: repoInfo,
        priority: 'medium',
      };

      const response = await createIssueWithContext(request);
      
      if (response.success && onShowIssuePreview) {
        const previewData: IssuePreviewData = {
          ...response.github_preview,
          userIssue: response.user_issue as UserIssueResponse,
          conversationContext: conversationMessages,
          fileContext: fileContextItems,
          canCreateGitHubIssue: true,
          repositoryInfo: request.repository_info,
        };
        
        onShowIssuePreview(previewData);
      }
    } catch (error) {
      console.error('Failed to create GitHub issue from context cards:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create issue';
      showError(`Failed to create GitHub issue: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, repositoryInfo, selectedRepository, cards, api, onShowIssuePreview, showError]);

  return (
    <div className="h-full flex flex-col">
      {/* Cards List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {cards.length === 0 ? (
          <div className="text-center py-12 text-fg/60">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No context cards yet</p>
            <p className="text-sm">Add items from chat or file dependencies</p>
          </div>
        ) : (
          cards.map((card) => {
            const SourceIcon = getSourceIcon(card.source);
            
            return (
              <div
                key={card.id}
                className="bg-zinc-800/50 rounded-xl p-4 group hover:bg-zinc-800 
                         transition-colors border border-zinc-700/50"
              >
                {/* Token Heat Bar */}
                <div className="h-1 w-full rounded-full bg-zinc-700 mb-3 overflow-hidden">
                  <div 
                    className={`h-full bg-gradient-to-r ${getTokenHeatColor(card.tokens)}`}
                    style={{ width: `${Math.min((card.tokens / 100000) * 100, 100)}%` }}
                  />
                </div>

                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-fg text-sm mb-1 truncate">
                      {card.title}
                    </h3>
                    <p className="text-fg/70 text-sm line-clamp-2 mb-3">
                      {card.description}
                    </p>
                    
                    <div className="flex items-center gap-3">
                      <span className="bg-zinc-800 px-2 py-0.5 rounded-full text-xs text-fg/80">
                        {card.tokens.toLocaleString()} tokens
                      </span>
                      <div className="flex items-center gap-1">
                        <SourceIcon className="w-3 h-3 text-fg/60" />
                        <span className="text-xs uppercase font-mono text-fg/60">
                          {card.source}
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => removeContextCard(card.id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity
                             p-1 hover:bg-error/20 rounded text-error"
                    aria-label="Remove card"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-fg/70">
            {cards.length} cards • {totalTokens.toLocaleString()} total tokens
          </span>
        </div>
        <button
          onClick={handleCreateGitHubIssue}
          disabled={cards.length === 0 || isLoading || (!repositoryInfo && !selectedRepository)}
          className="w-full h-11 bg-primary hover:bg-primary/80 disabled:opacity-50
                   disabled:cursor-not-allowed text-white rounded-xl font-medium
                   transition-colors"
          title={
            !repositoryInfo && !selectedRepository
              ? 'Select a repository first'
              : cards.length === 0
                ? 'Add context cards first'
                : 'Create GitHub issue from context cards'
          }
        >
          {isLoading ? (
            <div className="flex items-center justify-center gap-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Creating...
            </div>
          ) : (
            'Create GitHub Issue'
          )}
        </button>
      </div>
    </div>
  );
};