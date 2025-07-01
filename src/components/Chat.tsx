import React, { useState } from 'react';
import { Send, Plus } from 'lucide-react';
import { Message } from '../types';

interface ChatProps {
  onAddToContext: (content: string) => void;
}

export const Chat: React.FC<ChatProps> = ({ onAddToContext }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Welcome to the Development Assistant! How can I help you today?',
      isCode: false,
      timestamp: new Date(),
    },
    {
      id: '2',
      content: `function calculateComplexity(code: string): number {
  const lines = code.split('\\n').length;
  const conditions = (code.match(/if|else|while|for|switch/g) || []).length;
  return lines * 0.1 + conditions * 0.5;
}`,
      isCode: true,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [hoveredMessage, setHoveredMessage] = useState<string | null>(null);

  const handleSend = () => {
    if (!input.trim()) return;
    
    const newMessage: Message = {
      id: Date.now().toString(),
      content: input,
      isCode: input.includes('function') || input.includes('const ') || input.includes('class '),
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, newMessage]);
    setInput('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
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
            disabled={!input.trim()}
            className="bg-primary hover:bg-primary/80 disabled:opacity-50 
                     disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg 
                     transition-colors flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};