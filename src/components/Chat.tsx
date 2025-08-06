import React, { useState } from 'react';
import { Send, Plus } from 'lucide-react';
import { Message, FileItem } from '../types';
import { ApiService, CreateIssueWithContextRequest, ChatContextMessage, FileContextItem, GitHubIssuePreview } from '../services/api';
import { UserIssueResponse } from '../types';
import { useRepository } from '../hooks/useRepository';
import { useAuth } from '../hooks/useAuth';

// Simple toast utility (replace with your own or a library if available)
// This function is used to show a toast when the user clicks on "Create Issue"
function showToast(message: string) {
  // This is a placeholder. Replace with your toast library or implementation.
  // For example, if using react-toastify: toast.error(message)
  if (typeof window !== 'undefined') {
    // You can replace this with a more sophisticated toast system
    window.alert(message);
  }
}

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
  contextCards?: ContextCard[]; // Context cards from other components #TODO: Remove this
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
  void contextCards; // Suppress unused variable warning
  
  const { selectedRepository } = useRepository();
  const { sessionToken } = useAuth();
  
  // Simplified messages state without session management
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
  const userMessageCount = messages.filter(msg => 
    msg.id !== '1' && msg.id !== '2'
  ).length;

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    // Check if we have an active session
    if (!selectedRepository) {
      const errorText = 'No active repository selected. Please select a repository first.';
      showToast(errorText);
      return;
    }
    
    const currentInput = input;
    setInput('');
    setIsLoading(true);
    
    try {
      // Simulate sending message to a backend
      const newMessage: Message = {
        id: Date.now().toString(),
        content: currentInput,
        isCode: false,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, newMessage]);
      
    } catch (error) {
      console.error('Failed to send message:', error);
      
      let errorText = 'Sorry, I encountered an error. Please try again.';
      if (error instanceof Error) {
        if (error.message === 'Authentication required') {
          errorText = 'Please log in to continue chatting.';
        } else if (error.message === 'No active session') {
          errorText = 'Please select a repository to start a session.';
        } else {
          errorText = `Error: ${error.message}`;
        }
      }
      // Show error as toast
      showToast(errorText);

      // Refresh session to get latest state after error
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
        title: `Issue from Chat Session ${selectedRepository?.repository.full_name || 'default'}`,
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

      // Create issue from chat (this method may need to be implemented)
      // For now, using the existing createIssueFromChat method
      const chatRequest = {
        session_id: '', // No session ID for this simplified version
        message: { content: request.title, is_code: false },
        context_cards: []
      };
      const response = await ApiService.createIssueFromChat(chatRequest, sessionToken || undefined);
      
      if (response.success && onShowIssuePreview) {
        // Create a mock GitHub issue preview since the API structure changed
        const mockPreview = {
          title: response.issue.title,
          body: response.issue.description || response.issue.issue_text_raw,
          labels: [],
          assignees: [],
          repository_info: request.repository_info,
          metadata: {
            chat_messages_count: conversationMessages.length,
            file_context_count: fileContextItems.length,
            total_tokens: fileContextItems.reduce((sum, file) => sum + file.tokens, 0),
            generated_at: new Date().toISOString(),
            generation_method: 'chat_conversation'
          },
          userIssue: response.issue,
          conversationContext: conversationMessages,
          fileContext: fileContextItems,
          canCreateGitHubIssue: !!selectedRepository,
          repositoryInfo: request.repository_info
        };
        
        onShowIssuePreview(mockPreview);
        showToast('Issue created successfully!');
      }
      
    } catch (error) {
      console.error('Failed to create GitHub issue:', error);
      const errorText = `Failed to create GitHub issue: ${error instanceof Error ? error.message : 'Unknown error'}`;
      // Show error as toast
      showToast(errorText);
      // Optionally, you could also send this as a chat message if desired
      // const errorMessage: Message = {
      //   id: Date.now().toString(),
      //   content: errorText,
      //   isCode: false,
      //   timestamp: new Date(),
      // };
      // sendRealtimeMessage({ type: 'MESSAGE', data: errorMessage });
    } finally {
      setIsCreatingIssue(false);
    }
  };

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
            className={`flex ${message.isCode ? 'justify-start' : 'justify-end'}`}
            onMouseEnter={() => setHoveredMessage(message.id)}
            onMouseLeave={() => setHoveredMessage(null)}
          >
            <div
              className={`max-w-[70%] rounded-lg p-3 ${
                message.isCode
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
            <Send size={16} />
            Send
          </button>
          <button
            onClick={handleCreateGitHubIssue}
            disabled={isCreatingIssue || userMessageCount < 1 || !selectedRepository}
            className="bg-green-600 hover:bg-green-700 disabled:bg-zinc-600 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg flex items-center gap-2"
          >
            <Plus size={16} />
            Create Issue
          </button>
        </div>
      </div>
    </div>
  );
};
}