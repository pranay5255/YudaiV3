import React, { useState, useCallback, useEffect } from 'react';
import { Send, Plus } from 'lucide-react';
import { Message, FileItem, ContextCard, SelectedRepository } from '../types';
import type {
  CreateIssueWithContextRequest,
  ChatContextMessage,
  FileContextItem,
  GitHubIssuePreview
} from '../types/api';
import { UserIssueResponse } from '../types';
import { useRepository } from '../hooks/useRepository';
import { useApi } from '../hooks/useApi';
import { useSession } from '../contexts/SessionProvider';

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
  onAddToContext: (content: string) => void;
  contextCards?: ContextCard[];
  fileContext?: FileItem[];
  onShowIssuePreview?: (issuePreview: IssuePreviewData) => void;
  onShowError?: (error: string) => void;
}

export const Chat: React.FC<ChatProps> = ({
  onAddToContext,
  contextCards = [],
  fileContext = [],
  onShowIssuePreview,
  onShowError
}) => {
  const { sessionId, createSession } = useSession();
  const { selectedRepository } = useRepository();
  const api = useApi();
  
  console.log('[Chat] Initial render with props:', {
    contextCards,
    fileContext,
    sessionId,
    selectedRepository
  });

  // Simplified messages state without session management
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Hi, I am Daifu, your spirit guide across the chaos of context. I will help you create github issues and pull requests by adding the right context required for a given task.You can add the individual text messages to context such as the one below to prioritize text messages in conversations',
      timestamp: new Date(),
      sessionId: sessionId || 'default',
    },
    {
      id: '2',
      content: `function getSpiritGuideMessage(): string {
  const messages = [
    "In the chaos of code, find your inner peace... or just look at cat memes.",

  ];
  return messages[Math.floor(Math.random() * messages.length)];
}`,
      timestamp: new Date(),
      sessionId: sessionId || 'default',
    },
  ]);
  
  const [input, setInput] = useState('');
  const [hoveredMessage, setHoveredMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreatingIssue, setIsCreatingIssue] = useState(false);

  // Count user messages (messages that are not the initial system messages)
  const userMessageCount = messages.filter(msg =>
    msg.id !== '1' && msg.id !== '2'
  ).length;

  const showError = useCallback((message: string) => {
    console.error('[Chat] Error occurred:', message);
    if (onShowError) {
      onShowError(message);
    } else {
      console.error('Chat Error:', message);
    }
  }, [onShowError]);

  // Generate UUID4-like session ID using crypto API
  const generateSessionId = (): string => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };

  // Repository selection handler
  const handleRepositorySelection = useCallback((repository: SelectedRepository) => {
    console.log('[Chat] Repository selected:', repository);
    
    // Generate unique session ID
    const newSessionId = generateSessionId();
    console.log('[Chat] Generated new session ID:', newSessionId);
    
    // Create session with repository context
    handleCreateSession(repository, newSessionId);
  }, []);

  // Separate session creation function
  const handleCreateSession = useCallback(async (repository: SelectedRepository, sessionId: string) => {
    try {
      console.log('[Chat] Creating session for repository:', repository);
      
      const repoOwner = repository.repository.owner?.login || repository.repository.full_name.split('/')[0];
      const repoName = repository.repository.name;
      
      await createSession(repoOwner, repoName, repository.branch);
      
      // Add default welcome message after successful session creation
      const welcomeMessage: Message = {
        id: `welcome-${Date.now()}`,
        content: `Welcome to your new chat session with repository **${repoOwner}/${repoName}**!

I'm ready to help you with:
• Creating GitHub issues from our conversations
• Analyzing code and dependencies
• Planning development tasks
• Providing technical guidance

What would you like to work on today?`,
        timestamp: new Date(),
        sessionId: sessionId,
      };
      
      // Add welcome message to the chat
      setMessages(prev => [...prev, welcomeMessage]);
      
      console.log('[Chat] Session created successfully with welcome message');
    } catch (error) {
      console.error('[Chat] Failed to create session:', error);
      showError('Failed to create session. Please try again.');
    }
  }, [createSession, showError]);

  // Auto-create session when repository is selected
  useEffect(() => {
    console.log('[Chat] Repository or session changed:', {
      selectedRepository,
      sessionId
    });

    if (selectedRepository && !sessionId) {
      console.log('[Chat] Auto-creating session for selected repository');
      handleRepositorySelection(selectedRepository);
    }
  }, [selectedRepository, sessionId, handleRepositorySelection]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isLoading || !sessionId) {
      console.log('[Chat] Send blocked:', { 
        hasInput: !!input.trim(), 
        isLoading, 
        hasSession: !!sessionId 
      });
      return;
    }
    
    const currentInput = input;
    setInput('');
    setIsLoading(true);
    
    console.log('[Chat] Sending message:', {
      input: currentInput,
      sessionId,
      contextCards: contextCards.map(card => card.id)
    });

    // Add user message to chat immediately
    const userMessage: Message = {
      id: Date.now().toString(),
      content: currentInput,
      timestamp: new Date(),
      sessionId: sessionId,
    };
    setMessages(prev => [...prev, userMessage]);
    
          try {
        // Send to chat API for AI response
        console.log('[Chat] Calling chat API with payload:', {
          session_id: sessionId,
          message: {
            content: currentInput
          },
          context_cards: contextCards.map(card => card.id),
          repo_owner: selectedRepository?.repository.owner?.login || selectedRepository?.repository.full_name.split('/')[0],
          repo_name: selectedRepository?.repository.name
        });

        const response = await api.sendChatMessage({
          session_id: sessionId,
          message: {
            content: currentInput
          },
          context_cards: contextCards.map(card => card.id),
          repository: selectedRepository ? {
            owner: selectedRepository.repository.owner?.login || selectedRepository.repository.full_name.split('/')[0],
            name: selectedRepository.repository.name,
            branch: selectedRepository.branch
          } : undefined,
        });
      
        console.log('[Chat] Received API response:', response);

      // Add assistant response to chat
      const assistantMessage: Message = {
        id: response.message_id,
        content: response.reply,
        timestamp: new Date(),
        sessionId: sessionId,
      };
      setMessages(prev => [...prev, assistantMessage]);
      
    } catch (error) {
      console.error('[Chat] API call failed:', error);
      showError('Failed to send message. Please try again.');
      // Remove the user message that failed to send
      setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));
    } finally {
      // Always reset loading state
      setIsLoading(false);
    }
  }, [input, isLoading, sessionId, contextCards, selectedRepository, api, showError]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCreateGitHubIssue = useCallback(async () => {
    if (isCreatingIssue || !selectedRepository) {
      console.log('[Chat] Issue creation blocked:', {
        isCreatingIssue,
        hasRepository: !!selectedRepository
      });
      return;
    }
    
    setIsCreatingIssue(true);
    console.log('[Chat] Starting issue creation');
    
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

      console.log('[Chat] Prepared file context:', fileContextItems);

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

      console.log('[Chat] Sending create issue request:', request);

      // Use the proper API method for creating issues with context
      const response = await api.createIssueWithContext(request);
      
      console.log('[Chat] Received issue creation response:', response);

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
                    onClick={() => onAddToContext(message.content)}
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