import React, { useState, useCallback, useEffect } from 'react';
import { Trash2, FileText, MessageCircle, Upload } from 'lucide-react';
import type {
  ChatContextMessage,
  FileContextItem,
  GitHubIssuePreview,
  CreateIssueWithContextRequest,
  UserIssueResponse,
  ContextCard
} from '../types/sessionTypes';
import { useRepository } from '../hooks/useRepository';
import { useCreateIssueWithContext } from '../hooks/useSessionQueries';
import { useSessionStore } from '../stores/sessionStore';
import { logger } from '../utils/logger';

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

  const { deleteContextCard } = useSessionStore();
  const [isLoading, setIsLoading] = useState(false);

  // FIXED: Move hook call to top level
  const createIssueMutation = useCreateIssueWithContext();

  const showError = useCallback((message: string) => {
    if (onShowError) {
      onShowError(message);
    } else {
      logger.error('[Context] Error:', message);
    }
  }, [onShowError]);

  // Load context cards when session changes (cards are now passed as props from parent)
  useEffect(() => {
    if (activeSessionId && cards.length === 0) {
      logger.info('[Context] Context cards available:', cards.length);
    }
  }, [activeSessionId, cards]);

  const removeContextCard = useCallback(async (cardId: string) => {
    if (!activeSessionId) return;

    try {
      logger.info('[Context] Removing context card:', cardId);
      await deleteContextCard(cardId);
      logger.info('[Context] Context card removed successfully');
      // Call the onRemoveCard callback to update the parent state
      onRemoveCard(cardId);
    } catch (error) {
      logger.error('[Context] Failed to remove context card:', error);
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
    if (tokens < 300) return 'from-success to-success';
    if (tokens < 700) return 'from-success to-amber';
    return 'from-amber to-error';
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

      // FIXED: Use the hook result instead of calling hook inside callback
      const response = await createIssueMutation.mutateAsync(request);

      if (response && response.success && onShowIssuePreview) {
        const previewData: IssuePreviewData = {
          ...response.github_preview,
          userIssue: response.user_issue as UserIssueResponse,
          conversationContext: conversationMessages,
          fileContext: fileContextItems,
          canCreateGitHubIssue: true,
          repositoryInfo: repoInfo
        };
        onShowIssuePreview(previewData);
      }
    } catch (error) {
      logger.error('[Context] Failed to create issue with context:', error);
      showError('Failed to create issue with context. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [
    isLoading,
    repositoryInfo,
    selectedRepository,
    cards,
    onShowIssuePreview,
    showError,
    // FIXED: Add hook dependency
    createIssueMutation
  ]);

  return (
    <div className="h-full flex flex-col bg-bg terminal-noise">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <h2 className="font-mono font-semibold text-fg text-sm">Context Cards</h2>
        <p className="text-xs text-muted font-mono mt-1">Curated context for issue generation</p>
      </div>

      {/* Cards List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {cards.length === 0 ? (
          <div className="text-center py-12 animate-fade-in">
            <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-bg-tertiary border border-border flex items-center justify-center">
              <FileText className="w-8 h-8 text-muted" />
            </div>
            <p className="text-fg-secondary font-mono text-sm mb-1">No context cards yet</p>
            <p className="text-muted text-xs font-mono">Add items from chat or file dependencies</p>
          </div>
        ) : (
          cards.map((card, index) => {
            const SourceIcon = getSourceIcon(card.source);

            return (
              <div
                key={card.id}
                className="bg-bg-secondary border border-border rounded-xl p-4 group hover:border-border-accent transition-all duration-200 animate-fade-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Token Heat Bar */}
                <div className="h-1 w-full rounded-full bg-bg-tertiary mb-3 overflow-hidden">
                  <div
                    className={`h-full bg-gradient-to-r ${getTokenHeatColor(card.tokens)} transition-all duration-300`}
                    style={{ width: `${Math.min((card.tokens / 100000) * 100, 100)}%` }}
                  />
                </div>

                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-mono font-medium text-fg text-sm mb-1 truncate">
                      {card.title}
                    </h3>
                    <p className="text-fg-secondary text-xs font-mono line-clamp-2 mb-3">
                      {card.description}
                    </p>

                    <div className="flex items-center gap-3">
                      <span className="bg-bg-tertiary border border-border px-2.5 py-1 rounded-lg text-xs font-mono text-fg-secondary">
                        {card.tokens.toLocaleString()} tokens
                      </span>
                      <div className="flex items-center gap-1.5">
                        <SourceIcon className="w-3 h-3 text-muted" />
                        <span className="text-xs uppercase font-mono text-muted tracking-wider">
                          {card.source}
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => removeContextCard(card.id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-2 hover:bg-error/10 rounded-lg text-error border border-transparent hover:border-error/20"
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
      <div className="p-4 border-t border-border bg-bg-secondary">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-muted font-mono">
            {cards.length} cards &bull; {totalTokens.toLocaleString()} total tokens
          </span>
        </div>
        <button
          onClick={handleCreateGitHubIssue}
          disabled={cards.length === 0 || isLoading || (!repositoryInfo && !selectedRepository)}
          className="w-full h-11 bg-amber hover:bg-amber/90 disabled:bg-bg-tertiary disabled:border-border disabled:text-muted text-bg-primary rounded-xl font-mono font-semibold text-sm transition-all duration-200 disabled:cursor-not-allowed border border-amber disabled:border-border glow-amber disabled:shadow-none flex items-center justify-center gap-2"
          title={
            !repositoryInfo && !selectedRepository
              ? 'Select a repository first'
              : cards.length === 0
                ? 'Add context cards first'
                : 'Create GitHub issue from context cards'
          }
        >
          {isLoading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-bg-primary/20 border-t-bg-primary" />
              <span>Creating...</span>
            </>
          ) : (
            <span>Create GitHub Issue</span>
          )}
        </button>
      </div>
    </div>
  );
};
