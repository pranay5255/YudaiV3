import React, { useState } from 'react';
import { Send, Plus } from 'lucide-react';
import { Message, FileItem } from '../types';
import { ApiService, ChatRequest, CreateIssueWithContextRequest, ChatContextMessage, FileContextItem, GitHubIssuePreview, UserIssueResponse } from '../services/api';
import { useRepository } from '../hooks/useRepository';

interface ContextCard {
  id: string;
  title: string;
  description: string;
  tokens: number;
  source: string;
}

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
  onCreateIssue?: (conversationContext: Message[]) => void; // Made optional for backward compatibility
  contextCards?: ContextCard[]; // Context cards from other components
  fileContext?: FileItem[]; // File dependencies context
  onShowIssuePreview?: (issuePreview: IssuePreviewData) => void; // Callback to show issue preview in modal
}

export const Chat: React.FC<ChatProps> = ({ 
  onAddToContext, 
  onCreateIssue, // Keep for backward compatibility but mark as unused
  contextCards = [],
  fileContext = [],
  onShowIssuePreview 
}) => {
  // Suppress the unused variable warning by referencing it
  void onCreateIssue;
  
  const { selectedRepository } = useRepository();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Hi, I am Daifu, your spirit guide across the chaos of context. I will help you create github issues and pull requests by adding the right context required for a given task.You can add the individual text messages to context such as the one below to prioritize text messages in conversations',
      isCode: false,
      timestamp: new Date(),
    },
    {
      id: '2',
      content: `function getSpiritGuideMessage(): string {
  const messages = [
    "In the chaos of code, find your inner peace... or just look at cat memes.",

  ];
  return messages[Math.floor(Math.random() * messages.length)];
}`,
      isCode: true,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [hoveredMessage, setHoveredMessage] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [isCreatingIssue, setIsCreatingIssue] = useState(false);

  // Count user messages (messages that are not the initial system messages)
  const userMessageCount = messages.filter(msg => 
    msg.id !== '1' && msg.id !== '2'
  ).length;

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      isCode: input.includes('`') && input.includes('`'),
      timestamp: new Date(),
    };
    
    // Add user message immediately
    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setIsLoading(true);
    
    try {
      // Send to Daifu agent
      const request: ChatRequest = {
        session_id: sessionId,
        message: {
          content: currentInput,
          is_code: userMessage.isCode,
        },
        // Add context cards if available
        context_cards: contextCards.map(card => card.id) || [],
      };
      
      const response = await ApiService.sendChatMessage(request);
      
      // Update session ID if provided in response
      if (response.session_id && !sessionId) {
        setSessionId(response.session_id);
      }
      
      // Add Daifu's response
      const daifuMessage: Message = {
        id: response.message_id,
        content: response.reply,
        isCode: false,
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, daifuMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      
      let errorText = 'Sorry, I encountered an error. Please try again.';
      if (error instanceof Error) {
        if (error.message === 'Authentication required') {
          errorText = 'Please log in to continue chatting.';
        } else {
          errorText = `Error: ${error.message}`;
        }
      }
      
      // Add error message
      const errorMessage: Message = {
        id: Date.now().toString(),
        content: errorText,
        isCode: false,
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCreateGitHubIssue = async () => {
    if (isCreatingIssue) return;
    
    setIsCreatingIssue(true);
    
    try {
      // Filter out system messages and convert to ChatContextMessage format
      const conversationMessages: ChatContextMessage[] = messages
        .filter(msg => msg.id !== '1' && msg.id !== '2')
        .map(msg => ({
          id: msg.id,
          content: msg.content,
          isCode: msg.isCode,
          timestamp: msg.timestamp.toISOString()
        }));

      // Convert file context to FileContextItem format
      const fileContextItems: FileContextItem[] = fileContext.map(file => ({
        id: file.id,
        name: file.name,
        type: file.type,
        tokens: file.tokens,
        category: file.Category,
        path: file.path
      }));

      // Prepare the request
      const request: CreateIssueWithContextRequest = {
        title: `Issue from Chat Session ${sessionId || 'default'}`,
        description: 'This issue was generated from a chat conversation with file dependency context.',
        chat_messages: conversationMessages,
        file_context: fileContextItems,
        repository_info: selectedRepository ? {
          owner: selectedRepository.repository.full_name.split('/')[0],
          name: selectedRepository.repository.full_name.split('/')[1],
          branch: selectedRepository.branch
        } : undefined,
        priority: 'medium'
      };

      // Create issue preview
      const response = await ApiService.createIssueWithContext(request, true, true);
      
      if (response.success && onShowIssuePreview) {
        // Show the issue preview in the DiffModal
        onShowIssuePreview({
          ...response.github_preview,
          userIssue: response.user_issue,
          conversationContext: conversationMessages,
          fileContext: fileContextItems,
          canCreateGitHubIssue: !!selectedRepository,
          repositoryInfo: request.repository_info
        });
      }
      
    } catch (error) {
      console.error('Failed to create GitHub issue:', error);
      
      // Add error message to chat
      const errorMessage: Message = {
        id: Date.now().toString(),
        content: `Failed to create GitHub issue: ${error instanceof Error ? error.message : 'Unknown error'}`,
        isCode: false,
        timestamp: new Date(),
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsCreatingIssue(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className="group relative"
            onMouseEnter={() => setHoveredMessage(message.id)}
            onMouseLeave={() => setHoveredMessage(null)}
          >
            <div className={`
              p-4 rounded-xl
              ${message.isCode 
                ? 'bg-zinc-900 border border-zinc-800' 
                : 'bg-zinc-800/50'
              }
            `}>
              {message.isCode ? (
                <pre className="text-sm text-fg font-mono overflow-x-auto">
                  <code>{message.content}</code>
                </pre>
              ) : (
                <p className="text-fg prose dark:prose-invert max-w-none">
                  {message.content}
                </p>
              )}
            </div>
            
            {/* Add to Context Button */}
            {hoveredMessage === message.id && (
              <button
                onClick={() => onAddToContext(message.content)}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 
                         transition-opacity duration-200 bg-primary hover:bg-primary/80 
                         text-white p-1 rounded text-xs flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                Add to Context
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message... Use /add to add context"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 
                     text-fg placeholder-fg/50 focus:outline-none focus:ring-2 
                     focus:ring-primary focus:border-transparent"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="bg-primary hover:bg-primary/80 disabled:opacity-50 
                     disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg 
                     transition-colors flex items-center gap-2"
          >
            {isLoading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
          {userMessageCount >= 2 && (
            <button
              onClick={handleCreateGitHubIssue}
              disabled={isCreatingIssue}
              className="bg-green-600 hover:bg-green-700 disabled:opacity-50 
                       disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg 
                       transition-colors flex items-center gap-2"
            >
              {isCreatingIssue ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              ) : (
                'Create Github Issue'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};