import React, { useState } from 'react';
import { Send, Plus } from 'lucide-react';
import { Message } from '../types';
import { ApiService, ChatRequest } from '../services/api';

interface ChatProps {
  onAddToContext: (content: string) => void;
  onCreateIssue: (conversationContext: Message[]) => void;
}

export const Chat: React.FC<ChatProps> = ({ onAddToContext, onCreateIssue }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Hi, I am Daifu, your spirit guide across the chaos of context. I will help you create github issues and pull requests by adding the right context reqiured for a given task.',
      isCode: false,
      timestamp: new Date(),
    },
    {
      id: '2',
      content: `function getSpiritGuideMessage(): string {
  const messages = [
    "In the chaos of code, find your inner peace... or just look at cat memes.",
    "When the bugs are many, remember: cats always land on their feet.",
    "The path to enlightenment is paved with console.logs and cat gifs.",
    "In the darkest debugging sessions, let cat memes be your light.",
    "The wise developer knows when to refactor... and when to watch cat videos."
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

  // Count user messages (messages that are not the initial system messages)
  const userMessageCount = messages.filter(msg => 
    msg.id !== '1' && msg.id !== '2'
  ).length;

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      isCode: input.includes('function') || input.includes('const ') || input.includes('class '),
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
        context_cards: [], // TODO: Add actual context cards from props
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

  const handleCreateGitHubIssue = () => {
    // Filter out system messages and pass conversation context
    const conversationMessages = messages.filter(msg => 
      msg.id !== '1' && msg.id !== '2'
    );
    onCreateIssue(conversationMessages);
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
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg 
                       transition-colors flex items-center gap-2"
            >
              Create Github Issue
            </button>
          )}
        </div>
      </div>
    </div>
  );
};