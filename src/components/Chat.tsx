import React, { useState } from 'react';
import { Send, Plus, MessageSquare, Code, FileText, Trash2 } from 'lucide-react';
import { Message, ContextCard } from '../types';
import { ApiService, ChatRequest } from '../services/api';
import { useRepository } from '../contexts/RepositoryContext';
import { useSession } from '../contexts/SessionContext';

interface ChatProps {
  onAddToContext: (message: Message) => void;
  onCreateIssue?: () => void; // Keep for backward compatibility but mark as unused
  contextCards?: ContextCard[];
  fileContext?: Record<string, unknown>[];
  onShowIssuePreview?: (previewData: Record<string, unknown>) => void;
}

export const Chat: React.FC<ChatProps> = ({ 
  onAddToContext, 
  onCreateIssue, // Keep for backward compatibility but mark as unused
  contextCards = [],
  fileContext: _fileContext = [], // Mark as unused
  onShowIssuePreview 
}) => {
  // Suppress the unused variable warning by referencing it
  void onCreateIssue;
  void _fileContext;
  
  const { selectedRepository: _selectedRepository } = useRepository();
  void _selectedRepository;
  const { currentSessionId } = useSession();
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
  const [isLoading, setIsLoading] = useState(false);
  const [isCreatingIssue, setIsCreatingIssue] = useState(false);

  // Count user messages (messages that are not the initial system messages)
  // const userMessageCount = messages.filter(msg => 
  //   msg.id !== '1' && msg.id !== '2'
  // ).length;

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
        conversation_id: currentSessionId || undefined, // Fixed: use conversation_id instead of session_id
        message: {
          content: currentInput,
          is_code: userMessage.isCode,
        },
        // Add context cards if available
        context_cards: contextCards.map(card => card.id) || [],
      };
      
      const response = await ApiService.sendChatMessage(request);
      
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

  const handleAddToContext = (message: Message) => {
    onAddToContext(message);
  };

  const handleCreateIssueFromChat = async () => {
    if (!currentSessionId) {
      console.error('No active session for issue creation');
      return;
    }

    setIsCreatingIssue(true);
    try {
      // Use the enhanced session-based issue creation
      const userIssue = await ApiService.createIssueFromSessionEnhanced({
        session_id: currentSessionId,
        title: 'Issue from Chat Session',
        description: 'Issue created from chat conversation',
        priority: 'medium',
        use_code_inspector: true,
        create_github_issue: false
      });

      console.log('Issue created successfully:', userIssue);
      
      if (onShowIssuePreview) {
        onShowIssuePreview(userIssue as unknown as Record<string, unknown>);
      }
    } catch (error) {
      console.error('Failed to create issue from chat:', error);
    } finally {
      setIsCreatingIssue(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">Chat with Daifu</h2>
        </div>
        <div className="flex items-center gap-2">
          {currentSessionId && (
            <div className="text-xs text-fg/60 bg-zinc-800/50 px-2 py-1 rounded">
              Session: {currentSessionId.substring(0, 8)}...
            </div>
          )}
          <button
            onClick={handleCreateIssueFromChat}
            disabled={isCreatingIssue || !currentSessionId}
            className="flex items-center gap-2 px-3 py-1.5 bg-primary hover:bg-primary/80 text-white rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCreatingIssue ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
                <span>Creating...</span>
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" />
                <span>Create Issue</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-3 ${
              message.isCode ? 'bg-zinc-800/50 rounded-lg p-3' : ''
            }`}
            onMouseEnter={() => setHoveredMessage(message.id)}
            onMouseLeave={() => setHoveredMessage(null)}
          >
            <div className="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center">
              {message.isCode ? (
                <Code className="w-4 h-4 text-white" />
              ) : (
                <FileText className="w-4 h-4 text-white" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-fg">
                  {message.isCode ? 'Code' : 'Message'}
                </span>
                <span className="text-xs text-fg/60">
                  {message.timestamp.toLocaleTimeString()}
                </span>
              </div>
              <div className="text-sm text-fg/90 whitespace-pre-wrap">
                {message.content}
              </div>
              
              {/* Action buttons on hover */}
              {hoveredMessage === message.id && (
                <div className="flex items-center gap-2 mt-2">
                  <button
                    onClick={() => handleAddToContext(message)}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded transition-colors"
                  >
                    <Plus className="w-3 h-3" />
                    Add to Context
                  </button>
                  <button
                    onClick={() => {
                      setMessages(prev => prev.filter(m => m.id !== message.id));
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-red-600 hover:bg-red-500 rounded transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                    Delete
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            </div>
            <div className="text-sm text-fg/60">Daifu is thinking...</div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message here... Use backticks for code blocks"
            className="flex-1 p-3 bg-zinc-800 border border-zinc-700 rounded-lg text-fg placeholder-fg/50 resize-none focus:outline-none focus:border-primary"
            rows={3}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="px-4 py-3 bg-primary hover:bg-primary/80 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        
        {/* Context Cards Info */}
        {contextCards.length > 0 && (
          <div className="mt-2 text-xs text-fg/60">
            {contextCards.length} context card{contextCards.length !== 1 ? 's' : ''} available
          </div>
        )}
      </div>
    </div>
  );
};