import React, { useState, useCallback, useMemo } from 'react';
import { Send, Plus } from 'lucide-react';
import { Message } from '../types';
import type {
  CreateIssueWithContextRequest,
  ChatContextMessage,
  FileContextItem,
  GitHubIssuePreview
} from '../types/api';
import { UserIssueResponse } from '../types';
import { useRepository } from '../hooks/useRepository';
import { useApi } from '../hooks/useApi';
import { useSessionManagement } from '../hooks/useSessionManagement';
import {
  useChatMessages,
  useContextCards,
  useFileDependencies,
  useAddContextCard
} from '../hooks/useSessionQueries';
import { useQueryClient } from '@tanstack/react-query';

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

interface ChatProps {
  onShowIssuePreview?: (issuePreview: IssuePreviewData) => void;
  onShowError?: (error: string) => void;
}

export const Chat: React.FC<ChatProps> = ({
  onShowIssuePreview,
  onShowError
}) => {
  // Session management hook for state management
  const { activeSessionId } = useSessionManagement();
  const { selectedRepository } = useRepository();
  
  // React Query hooks for data and mutations
  const { data: chatMessages = [] } = useChatMessages(activeSessionId || '');
  const { data: contextCards = [] } = useContextCards(activeSessionId || '');
  const { data: fileContext = [] } = useFileDependencies(activeSessionId || '');
  const addContextCardMutation = useAddContextCard();
  
  const api = useApi();
  const queryClient = useQueryClient();
  
  // Convert API messages to Message format for display
  const messages: Message[] = chatMessages.map(msg => ({
    id: msg.message_id,
    content: msg.message_text,
    timestamp: new Date(msg.created_at),
    sessionId: activeSessionId || 'default',
  }));



  // Simplified messages state without session management
  const [input, setInput] = useState('');
  const [hoveredMessage, setHoveredMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreatingIssue, setIsCreatingIssue] = useState(false);

  // Count user messages (messages that are not the initial system messages)
  const userMessageCount = messages.filter(msg =>
    msg.id !== '1' && msg.id !== '2'
  ).length;

  // Get relevant files based on current conversation context
  const relevantFiles = useMemo(() => {
    if (!fileContext || fileContext.length === 0) return [];
    
    // Simple relevance scoring based on file type and recent messages
    const recentMessages = messages.slice(-3); // Last 3 messages
    const messageText = recentMessages.map(m => m.content).join(' ').toLowerCase();
    
    return fileContext
      .filter(file => {
        // Prioritize files that might be relevant to the conversation
        const fileName = (file.name || file.file_name || '').toLowerCase();
        const filePath = (file.path || file.file_path || '').toLowerCase();
        
        // Check if file name or path contains keywords from recent messages
        const keywords = messageText.split(' ').filter(word => word.length > 3);
        return keywords.some(keyword => 
          fileName.includes(keyword) || filePath.includes(keyword)
        );
      })
      .slice(0, 3); // Show top 3 relevant files
  }, [fileContext, messages]);

  const showError = useCallback((message: string) => {
    console.error('[Chat] Error occurred:', message);
    if (onShowError) {
      onShowError(message);
    } else {
      console.error('Chat Error:', message);
    }
  }, [onShowError]);

  // Session creation is now handled by useSessionManagement hook
  // This component no longer needs to create sessions directly

  const handleAddToContext = useCallback(async (content: string) => {
    if (!activeSessionId) {
      showError('No active session to add context to');
      return;
    }

    addContextCardMutation.mutate({
      sessionId: activeSessionId,
      card: {
        title: 'Chat Message',
        description: content.length > 100 ? content.substring(0, 100) + '...' : content,
        source: 'chat',
        tokens: Math.ceil(content.length / 4),
        content,
      },
    }, {
      onError: () => showError('Failed to add to context'),
    });
  }, [activeSessionId, addContextCardMutation, showError]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isLoading || !activeSessionId) {
      return;
    }
    
    const currentInput = input;
    setInput('');
    setIsLoading(true);

    try {
      // Send to chat API for AI response (messages are handled by backend)
      const response = await api.sendChatMessage({
        session_id: activeSessionId,
        message: { message_text: currentInput },
        context_cards: contextCards.map(card => card.id),
        repository: selectedRepository ? {
          owner: selectedRepository.repository.owner?.login || selectedRepository.repository.full_name.split('/')[0],
          name: selectedRepository.repository.name,
          branch: selectedRepository.branch
        } : undefined,
      });

      // Chat messages are now handled by the backend through the existing chat endpoint
      console.log('[Chat] Message sent successfully:', response.message_id);
      
      // Invalidate and refetch the messages to show the updated conversation
      await queryClient.invalidateQueries({ 
        queryKey: ['messages', activeSessionId] 
      });
      
    } catch (error) {
      console.error('[Chat] Message sending failed:', error);
      showError('Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, activeSessionId, contextCards, selectedRepository, api, showError, queryClient]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCreateGitHubIssue = useCallback(async () => {
    if (isCreatingIssue || !selectedRepository) {
      return;
    }
    
    setIsCreatingIssue(true);
    
    try {
      // Filter out system messages and convert to ChatContextMessage format
      const conversationMessages: ChatContextMessage[] = messages
        .filter(msg => msg.id !== '1' && msg.id !== '2')
        .map(msg => ({
          id: msg.id,
          content: msg.content,
          timestamp: msg.timestamp.toISOString()
        }));

      console.log('[Chat] Prepared conversation messages:', conversationMessages);

      // Convert file context to FileContextItem format
      const fileContextItems: FileContextItem[] = fileContext.map(file => ({
        id: file.id,
        name: file.name || file.file_name || '',
        type: file.type || file.file_type || 'INTERNAL',
        tokens: file.tokens,
        category: file.category || file.content_summary || '',
        path: file.path || file.file_path
      }));

      // Prepare the request using the proper API method
      const request: CreateIssueWithContextRequest = {
        title: `Issue from Chat Session - ${selectedRepository.repository.name}`,
        description: 'This issue was generated from a chat conversation with file dependency context.',
        chat_messages: conversationMessages,
        file_context: fileContextItems,
        repository_info: {
          owner: selectedRepository.repository.full_name.split('/')[0],
          name: selectedRepository.repository.full_name.split('/')[1],
          branch: selectedRepository.branch
        },
        priority: 'medium'
      };

      // Use the proper API method for creating issues with context
      const response = await api.createIssueWithContext(request);

      if (response.success && onShowIssuePreview) {
        const issuePreview: IssuePreviewData = {
          ...response.github_preview,
          userIssue: response.user_issue as UserIssueResponse,
          conversationContext: conversationMessages,
          fileContext: fileContextItems,
          canCreateGitHubIssue: true,
          repositoryInfo: request.repository_info
        };
        
        onShowIssuePreview(issuePreview);
      }
      
    } catch (error) {
      console.error('[Chat] Issue creation failed:', error);
      const errorText = `Failed to create GitHub issue: ${error instanceof Error ? error.message : 'Unknown error'}`;
      showError(errorText);
    } finally {
      setIsCreatingIssue(false);
    }
  }, [isCreatingIssue, selectedRepository, messages, fileContext, api, onShowIssuePreview, showError]);



  return (
    <div className="h-full flex flex-col">
      {/* Session Status Indicator */}
      {!selectedRepository && (
        <div className="bg-yellow-600/20 border border-yellow-600/30 rounded-lg p-4 mb-4">
          <div className="text-yellow-400 font-medium mb-2">No Active Repository</div>
          <div className="text-yellow-300 text-sm mb-3">
            Please select a repository to start a new session and begin chatting with Daifu.
          </div>
          <button
            onClick={() => {
              // Trigger repository selection manually
              window.location.reload();
            }}
            className="bg-yellow-600 hover:bg-yellow-700 text-white px-3 py-1 rounded text-sm"
          >
            Select Repository
          </button>
        </div>
      )}
      
      {/* File Context Display */}
      {relevantFiles.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-700 rounded-lg p-3 mx-4 mb-4">
          <div className="text-sm text-zinc-400 mb-2">📁 Relevant Files</div>
          <div className="space-y-1">
            {relevantFiles.map((file) => (
              <div key={file.id} className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 truncate flex-1">
                  {file.name || file.file_name}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500">{file.tokens} tokens</span>
                  <button
                    onClick={() => handleAddToContext(`File: ${file.name || file.file_name} (${file.path || file.file_path})`)}
                    className="text-blue-400 hover:text-blue-300 text-xs"
                    title="Add file to context"
                  >
                    Add
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.id === '2' ? 'justify-start' : 'justify-end'}`}
            onMouseEnter={() => setHoveredMessage(message.id)}
            onMouseLeave={() => setHoveredMessage(null)}
          >
            <div
              className={`max-w-[70%] rounded-lg p-3 ${
                message.id === '2'
                  ? 'bg-zinc-800 text-zinc-200'
                  : 'bg-blue-600 text-white'
              }`}
            >
              <div className="whitespace-pre-wrap">{message.content}</div>
              {hoveredMessage === message.id && message.id !== '1' && message.id !== '2' && (
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => handleAddToContext(message.content)}
                    className="text-xs bg-zinc-700 hover:bg-zinc-600 px-2 py-1 rounded"
                  >
                    Add to Context
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800 text-zinc-200 rounded-lg p-3">
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-zinc-400"></div>
                <span>Daifu is thinking...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-zinc-700 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={selectedRepository ? "Type your message..." : "Select a repository to start chatting..."}
            disabled={!selectedRepository || isLoading}
            className="flex-1 bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-white placeholder-zinc-400 focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading || !selectedRepository}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-600 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg flex items-center gap-2"
          >
            {isLoading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Send size={16} />
            )}
            {isLoading ? 'Sending...' : 'Send'}
          </button>
          <button
            onClick={handleCreateGitHubIssue}
            disabled={isCreatingIssue || userMessageCount < 1 || !selectedRepository}
            className="bg-green-600 hover:bg-green-700 disabled:bg-zinc-600 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg flex items-center gap-2"
            title={!selectedRepository ? 'Select a repository first' : userMessageCount < 1 ? 'Send at least one message' : 'Create GitHub issue from conversation'}
          >
            {isCreatingIssue ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Plus size={16} />
            )}
            {isCreatingIssue ? 'Creating...' : 'Create Issue'}
          </button>
        </div>
      </div>
    </div>
  );
};