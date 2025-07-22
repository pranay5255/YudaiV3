import React, { useState } from 'react';
import { Trash2, FileText, MessageCircle, Upload } from 'lucide-react';
import { ContextCard } from '../types';
import { ApiService, CreateIssueWithContextRequest, ChatContextMessage, FileContextItem, GitHubIssuePreview, UserIssueResponse } from '../services/api';

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
  onCreateIssue?: () => void; // <-- add this
  onShowIssuePreview?: (issuePreview: IssuePreviewData) => void;
  repositoryInfo?: {
    owner: string;
    name: string;
    branch?: string;
  };
}

export const ContextCards: React.FC<ContextCardsProps> = ({ 
  cards, 
  onRemoveCard, 
  onCreateIssue, // <-- add this
  onShowIssuePreview,
  repositoryInfo
}) => {
  const [isCreatingIssue, setIsCreatingIssue] = useState(false);

  const getSourceIcon = (source: ContextCard['source']) => {
    switch (source) {
      case 'chat': return MessageCircle;
      case 'file-deps': return FileText;
      case 'upload': return Upload;
    }
  };

  const getTokenHeatColor = (tokens: number) => {
    if (tokens < 3000) return 'from-teal-500 to-teal-500';
    if (tokens < 7000) return 'from-teal-500 to-amber-500';
    return 'from-amber-500 to-red-500';
  };

  const totalTokens = cards.reduce((sum, card) => sum + card.tokens, 0);

  // Replicate Chat.tsx: handle create GitHub issue with context cards
  const handleCreateGitHubIssue = async () => {
    if (isCreatingIssue) return;
    setIsCreatingIssue(true);
    try {
      // Separate chat and file context
      const chatCards = cards.filter(card => card.source === 'chat');
      const fileCards = cards.filter(card => card.source === 'file-deps');

      // Convert to API formats
      const conversationMessages: ChatContextMessage[] = chatCards.map(card => ({
        id: card.id,
        content: card.title + '\n' + card.description,
        isCode: false,
        timestamp: new Date().toISOString(),
      }));
      const fileContextItems: FileContextItem[] = fileCards.map(card => ({
        id: card.id,
        name: card.title,
        type: 'INTERNAL',
        tokens: card.tokens,
        category: 'Context File',
        path: card.title,
      }));

      const request: CreateIssueWithContextRequest = {
        title: `Issue from Context Cards`,
        description: 'This issue was generated from context cards.',
        chat_messages: conversationMessages,
        file_context: fileContextItems,
        repository_info: repositoryInfo,
        priority: 'medium',
      };

      const response = await ApiService.createIssueWithContext(request, true, true);
      if (response.success && onShowIssuePreview) {
        onShowIssuePreview({
          ...response.github_preview,
          userIssue: response.user_issue,
          conversationContext: conversationMessages,
          fileContext: fileContextItems,
          canCreateGitHubIssue: !!repositoryInfo,
          repositoryInfo: request.repository_info,
        });
      }
    } catch (error) {
      // Optionally show error toast or message
      // eslint-disable-next-line no-console
      console.error('Failed to create GitHub issue from context cards:', error);
    } finally {
      setIsCreatingIssue(false);
    }
  };

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
                    onClick={() => onRemoveCard(card.id)}
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
          onClick={onCreateIssue ? onCreateIssue : handleCreateGitHubIssue}
          disabled={cards.length === 0 || isCreatingIssue}
          className="w-full h-11 bg-primary hover:bg-primary/80 disabled:opacity-50 
                   disabled:cursor-not-allowed text-white rounded-xl font-medium 
                   transition-colors"
        >
          {isCreatingIssue ? 'Creating...' : 'Create GitHub Issue'}
        </button>
      </div>
    </div>
  );
};