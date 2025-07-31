import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { ApiService } from '../services/api';
import { useRepository } from '../hooks/useRepository';
import { useAuth } from '../hooks/useAuth';
import { 
  SessionState, 
  SessionUpdateEvent, 
  ContextCard, 
  FileItem, 
  ChatMessageAPI,
  AgentStatus,
  TabState
} from '../types';
import { UserIssueResponse } from '../services/api';

/**
 * Comprehensive Session Context Interface
 * Manages all application state through session-based architecture
 */
interface SessionContextValue {
  // Core session state
  sessionState: SessionState;
  tabState: TabState;
  
  // Session management functions
  createSession: (repoOwner: string, repoName: string, repoBranch?: string, title?: string, description?: string) => Promise<string>;
  loadSession: (sessionId: string) => Promise<void>;
  switchSession: (sessionId: string) => Promise<void>;
  clearSession: () => void;
  refreshSession: () => Promise<void>;
  
  // Real-time connection management
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
  reconnect: () => void;
  
  // Chat management with separate refresh
  sendMessage: (content: string, isCode?: boolean) => Promise<void>;
  refreshMessages: () => Promise<void>;
  clearMessages: () => void;
  
  // Context management
  addContextCard: (card: ContextCard) => void;
  removeContextCard: (cardId: string) => void;
  updateContextCards: (cards: ContextCard[]) => void;
  
  // File context management
  addFileContext: (file: FileItem) => void;
  removeFileContext: (fileId: string) => void;
  updateFileContext: (files: FileItem[]) => void;
  
  // Issue management
  createIssue: (title: string, description?: string) => Promise<UserIssueResponse>;
  loadUserIssues: () => Promise<void>;
  updateIssue: (issueId: string, updates: Partial<UserIssueResponse>) => void;
  
  // Agent management
  startAgent: (agentType: 'daifu' | 'architect' | 'coder' | 'tester') => Promise<void>;
  updateAgentStatus: (status: AgentStatus) => void;
  
  // Tab management
  setActiveTab: (tab: string) => void;
  refreshTab: (tab: string) => void;
  
  // Repository management
  updateRepositoryInfo: (repoInfo: any) => void;
  
  // Utility functions
  exportSessionData: () => SessionState;
  importSessionData: (data: Partial<SessionState>) => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

interface SessionProviderProps {
  children: ReactNode;
}

// Storage keys for persistent state
const STORAGE_KEYS = {
  SESSION_STATE: 'yudai_session_state',
  TAB_STATE: 'yudai_tab_state',
  CONNECTION_STATE: 'yudai_connection_state'
} as const;

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  // Initialize session state with comprehensive structure
  const [sessionState, setSessionState] = useState<SessionState>({
    sessionId: null,
    session: null,
    repository: null,
    branch: 'main',
    repositoryInfo: null,
    messages: [],
    isLoadingMessages: false,
    messageRefreshKey: 0,
    contextCards: [],
    fileContext: [],
    totalTokens: 0,
    userIssues: [],
    currentIssue: null,
    agentStatus: {
      type: 'daifu',
      status: 'idle'
    },
    agentHistory: [],
    statistics: {
      total_messages: 0,
      total_tokens: 0,
      total_cost: 0,
      session_duration: 0
    },
    isLoading: false,
    error: null,
    lastUpdated: new Date(),
    connectionStatus: 'disconnected'
  });
  
  // Tab state management with separate refresh keys
  const [tabState, setTabState] = useState<TabState>({
    activeTab: 'chat',
    refreshKeys: {
      chat: 0,
      'file-deps': 0,
      context: 0,
      ideas: 0
    },
    tabHistory: ['chat']
  });
  
  // Real-time connection state
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected');
  
  const { selectedRepository } = useRepository();
  const { isAuthenticated } = useAuth();

  // Load persistent state from localStorage on mount
  useEffect(() => {
    try {
      const storedSessionState = localStorage.getItem(STORAGE_KEYS.SESSION_STATE);
      const storedTabState = localStorage.getItem(STORAGE_KEYS.TAB_STATE);
      
      if (storedSessionState) {
        const parsedSessionState = JSON.parse(storedSessionState);
        setSessionState(prev => ({
          ...prev,
          ...parsedSessionState,
          lastUpdated: new Date(parsedSessionState.lastUpdated),
          connectionStatus: 'disconnected' // Always start disconnected
        }));
      }
      
      if (storedTabState) {
        const parsedTabState = JSON.parse(storedTabState);
        setTabState(parsedTabState);
      }
    } catch (error) {
      console.error('Failed to load session state from localStorage:', error);
      // Clear corrupted data
      Object.values(STORAGE_KEYS).forEach(key => {
        localStorage.removeItem(key);
      });
    }
  }, []);

  // Save session state to localStorage whenever it changes
  useEffect(() => {
    if (sessionState.sessionId) {
      try {
        localStorage.setItem(STORAGE_KEYS.SESSION_STATE, JSON.stringify(sessionState));
      } catch (error) {
        console.error('Failed to save session state to localStorage:', error);
      }
    }
  }, [sessionState]);
  
  // Save tab state to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.TAB_STATE, JSON.stringify(tabState));
    } catch (error) {
      console.error('Failed to save tab state to localStorage:', error);
    }
  }, [tabState]);

  /**
   * Creates a new session using the enhanced session creation endpoint
   * Automatically establishes real-time connection and loads initial context
   */
  const createSession = async (
    repoOwner: string, 
    repoName: string, 
    repoBranch: string = 'main',
    title?: string,
    description?: string
  ): Promise<string> => {
    if (!isAuthenticated) {
      throw new Error('User must be authenticated to create a session');
    }

    setSessionState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      // Create session using new endpoint
      const session = await ApiService.createSession(
        repoOwner,
        repoName,
        repoBranch,
        title,
        description
      );

      // Update session state with new session
      setSessionState(prev => ({
        ...prev,
        sessionId: session.id,
        session,
        repository: {
          id: 0, // Will be populated when repository is selected
          name: repoName,
          full_name: `${repoOwner}/${repoName}`,
          private: false,
          html_url: `https://github.com/${repoOwner}/${repoName}`,
        },
        branch: repoBranch,
        repositoryInfo: {
          owner: repoOwner,
          name: repoName,
          branch: repoBranch,
          full_name: `${repoOwner}/${repoName}`,
          html_url: `https://github.com/${repoOwner}/${repoName}`
        },
        isLoading: false,
        lastUpdated: new Date()
      }));

      // Establish real-time connection
      await establishRealtimeConnection(session.id);
      
      // Load initial session context
      await loadSessionContext(session.id);

      return session.id;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create session';
      setSessionState(prev => ({ 
        ...prev, 
        error: errorMessage, 
        isLoading: false 
      }));
      throw error;
    }
  };

  /**
   * Establishes Server-Sent Events connection for real-time updates
   * Handles automatic reconnection and error recovery
   */
  const establishRealtimeConnection = useCallback(async (sessionId: string) => {
    if (eventSource) {
      eventSource.close();
    }

    try {
      setConnectionStatus('reconnecting');
      
      const newEventSource = ApiService.createSessionEventSource(sessionId);
      
      newEventSource.onopen = () => {
        console.log('Real-time connection established for session:', sessionId);
        setConnectionStatus('connected');
        setSessionState(prev => ({ ...prev, connectionStatus: 'connected' }));
      };
      
      newEventSource.onmessage = (event) => {
        try {
          const updateEvent: SessionUpdateEvent = JSON.parse(event.data);
          handleRealtimeUpdate(updateEvent);
        } catch (error) {
          console.error('Failed to parse real-time update:', error);
        }
      };
      
      newEventSource.onerror = (error) => {
        console.error('Real-time connection error:', error);
        setConnectionStatus('disconnected');
        setSessionState(prev => ({ ...prev, connectionStatus: 'disconnected' }));
        
        // Attempt to reconnect after 5 seconds
        setTimeout(() => {
          if (sessionState.sessionId) {
            establishRealtimeConnection(sessionState.sessionId);
          }
        }, 5000);
      };
      
      setEventSource(newEventSource);
    } catch (error) {
      console.error('Failed to establish real-time connection:', error);
      setConnectionStatus('disconnected');
    }
  }, [eventSource, sessionState.sessionId]);
  
  /**
   * Handles real-time updates from Server-Sent Events
   * Updates appropriate parts of session state based on event type
   */
  const handleRealtimeUpdate = useCallback((event: SessionUpdateEvent) => {
    console.log('Real-time update received:', event);
    
    switch (event.type) {
      case 'message':
        setSessionState(prev => ({
          ...prev,
          messages: [...prev.messages, event.data as ChatMessageAPI],
          messageRefreshKey: prev.messageRefreshKey + 1,
          lastUpdated: new Date()
        }));
        break;
        
      case 'context_card':
        setSessionState(prev => ({
          ...prev,
          contextCards: event.data.action === 'add' 
            ? [...prev.contextCards, event.data.card]
            : prev.contextCards.filter(card => card.id !== event.data.card_id),
          lastUpdated: new Date()
        }));
        break;
        
      case 'agent_status':
        setSessionState(prev => ({
          ...prev,
          agentStatus: event.data as AgentStatus,
          agentHistory: [...prev.agentHistory, event.data as AgentStatus],
          lastUpdated: new Date()
        }));
        break;
        
      case 'session_update':
        setSessionState(prev => ({
          ...prev,
          session: { ...prev.session, ...event.data },
          lastUpdated: new Date()
        }));
        break;
        
      case 'repository_update':
        setSessionState(prev => ({
          ...prev,
          repositoryInfo: { ...prev.repositoryInfo, ...event.data },
          lastUpdated: new Date()
        }));
        break;
        
      default:
        console.warn('Unknown real-time event type:', event.type);
    }
  }, []);
  
  /**
   * Loads comprehensive session context from the enhanced endpoint
   */
  const loadSessionContext = async (sessionId: string) => {
    try {
      const context = await ApiService.getSessionContextById(sessionId);
      
      setSessionState(prev => ({
        ...prev,
        session: context.session,
        messages: context.messages,
        contextCards: context.context_cards.map(id => ({ id, title: '', description: '', tokens: 0, source: 'chat' as any })),
        fileContext: context.file_embeddings?.map(emb => ({
          id: emb.id.toString(),
          name: emb.file_name,
          type: emb.file_type as 'INTERNAL' | 'EXTERNAL',
          tokens: emb.tokens,
          Category: 'INTERNAL',
          path: emb.file_path,
          isDirectory: false
        })) || [],
        repositoryInfo: context.repository_info,
        statistics: context.statistics,
        totalTokens: context.statistics?.total_tokens || 0,
        lastUpdated: new Date()
      }));
    } catch (error) {
      console.error('Failed to load session context:', error);
      throw error;
    }
  };

  // Auto-create session when repository is selected
  useEffect(() => {
    if (isAuthenticated && selectedRepository && !sessionState.sessionId) {
      createSession(
        selectedRepository.repository.full_name.split('/')[0],
        selectedRepository.repository.name,
        selectedRepository.branch,
        `Session for ${selectedRepository.repository.full_name}`,
        `Working session for ${selectedRepository.repository.full_name} on ${selectedRepository.branch} branch`
      ).catch(error => {
        console.error('Failed to auto-create session:', error);
      });
    }
  }, [isAuthenticated, selectedRepository, sessionState.sessionId]);
  
  // Clean up real-time connection on unmount
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);
  
  // Touch session periodically to keep it active
  useEffect(() => {
    if (sessionState.sessionId && connectionStatus === 'connected') {
      const touchInterval = setInterval(async () => {
        try {
          await ApiService.touchSession(sessionState.sessionId!);
        } catch (error) {
          console.error('Failed to touch session:', error);
        }
      }, 30000); // Touch every 30 seconds
      
      return () => clearInterval(touchInterval);
    }
  }, [sessionState.sessionId, connectionStatus]);

  // Additional session management functions
  const loadSession = async (sessionId: string): Promise<void> => {
    setSessionState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      await loadSessionContext(sessionId);
      await establishRealtimeConnection(sessionId);
      setSessionState(prev => ({ ...prev, isLoading: false }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load session';
      setSessionState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
      throw error;
    }
  };
  
  const switchSession = async (sessionId: string): Promise<void> => {
    if (eventSource) {
      eventSource.close();
    }
    await loadSession(sessionId);
  };
  
  const clearSession = (): void => {
    if (eventSource) {
      eventSource.close();
    }
    
    setSessionState({
      sessionId: null,
      session: null,
      repository: null,
      branch: 'main',
      repositoryInfo: null,
      messages: [],
      isLoadingMessages: false,
      messageRefreshKey: 0,
      contextCards: [],
      fileContext: [],
      totalTokens: 0,
      userIssues: [],
      currentIssue: null,
      agentStatus: { type: 'daifu', status: 'idle' },
      agentHistory: [],
      statistics: {
        total_messages: 0,
        total_tokens: 0,
        total_cost: 0,
        session_duration: 0
      },
      isLoading: false,
      error: null,
      lastUpdated: new Date(),
      connectionStatus: 'disconnected'
    });
    
    setTabState({
      activeTab: 'chat',
      refreshKeys: { chat: 0, 'file-deps': 0, context: 0, ideas: 0 },
      tabHistory: ['chat']
    });
    
    Object.values(STORAGE_KEYS).forEach(key => {
      localStorage.removeItem(key);
    });
  };
  
  const refreshSession = async (): Promise<void> => {
    if (sessionState.sessionId) {
      await loadSessionContext(sessionState.sessionId);
    }
  };
  
  // Chat management functions
  const sendMessage = async (content: string, isCode: boolean = false): Promise<void> => {
    if (!sessionState.sessionId) {
      throw new Error('No active session');
    }
    
    setSessionState(prev => ({ ...prev, isLoadingMessages: true }));
    
    try {
      const response = await ApiService.sendEnhancedChatMessage({
        session_id: sessionState.sessionId,
        message: { content, is_code: isCode },
        context_cards: sessionState.contextCards.map(card => card.id),
        file_context: sessionState.fileContext.map(file => file.id)
      });
      
      // Update messages with user message and AI response
      const userMessage: ChatMessageAPI = {
        id: `user_${Date.now()}`,
        content,
        role: 'user',
        timestamp: new Date().toISOString(),
        is_code: isCode
      };
      
      const aiMessage: ChatMessageAPI = {
        id: response.message_id,
        content: response.reply,
        role: 'assistant',
        timestamp: new Date().toISOString(),
        is_code: false
      };
      
      setSessionState(prev => ({
        ...prev,
        messages: [...prev.messages, userMessage, aiMessage],
        messageRefreshKey: prev.messageRefreshKey + 1,
        isLoadingMessages: false,
        lastUpdated: new Date()
      }));
    } catch (error) {
      setSessionState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to send message',
        isLoadingMessages: false
      }));
      throw error;
    }
  };
  
  const refreshMessages = async (): Promise<void> => {
    if (!sessionState.sessionId) return;
    
    setSessionState(prev => ({ ...prev, isLoadingMessages: true }));
    
    try {
      const messages = await ApiService.getSessionMessages(sessionState.sessionId);
      setSessionState(prev => ({
        ...prev,
        messages,
        messageRefreshKey: prev.messageRefreshKey + 1,
        isLoadingMessages: false,
        lastUpdated: new Date()
      }));
    } catch (error) {
      setSessionState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to refresh messages',
        isLoadingMessages: false
      }));
    }
  };
  
  const clearMessages = (): void => {
    setSessionState(prev => ({
      ...prev,
      messages: [],
      messageRefreshKey: prev.messageRefreshKey + 1,
      lastUpdated: new Date()
    }));
  };
  
  // Context management functions
  const addContextCard = (card: ContextCard): void => {
    setSessionState(prev => ({
      ...prev,
      contextCards: [...prev.contextCards, card],
      totalTokens: prev.totalTokens + card.tokens,
      lastUpdated: new Date()
    }));
  };
  
  const removeContextCard = (cardId: string): void => {
    setSessionState(prev => {
      const removedCard = prev.contextCards.find(card => card.id === cardId);
      return {
        ...prev,
        contextCards: prev.contextCards.filter(card => card.id !== cardId),
        totalTokens: prev.totalTokens - (removedCard?.tokens || 0),
        lastUpdated: new Date()
      };
    });
  };
  
  const updateContextCards = (cards: ContextCard[]): void => {
    setSessionState(prev => ({
      ...prev,
      contextCards: cards,
      totalTokens: cards.reduce((sum, card) => sum + card.tokens, 0),
      lastUpdated: new Date()
    }));
  };
  
  // File context management
  const addFileContext = (file: FileItem): void => {
    setSessionState(prev => ({
      ...prev,
      fileContext: [...prev.fileContext, file],
      lastUpdated: new Date()
    }));
  };
  
  const removeFileContext = (fileId: string): void => {
    setSessionState(prev => ({
      ...prev,
      fileContext: prev.fileContext.filter(file => file.id !== fileId),
      lastUpdated: new Date()
    }));
  };
  
  const updateFileContext = (files: FileItem[]): void => {
    setSessionState(prev => ({
      ...prev,
      fileContext: files,
      lastUpdated: new Date()
    }));
  };
  
  // Issue management
  const createIssue = async (title: string, description?: string): Promise<UserIssueResponse> => {
    if (!sessionState.sessionId) {
      throw new Error('No active session');
    }
    
    setSessionState(prev => ({ ...prev, isLoading: true }));
    
    try {
      const request = {
        title,
        description,
        chat_messages: sessionState.messages.map(msg => ({
          id: msg.id,
          content: msg.content,
          isCode: msg.is_code,
          timestamp: msg.timestamp
        })),
        file_context: sessionState.fileContext.map(file => ({
          id: file.id,
          name: file.name,
          type: file.type,
          tokens: file.tokens,
          category: file.Category,
          path: file.path
        })),
        repository_info: sessionState.repositoryInfo ? {
          owner: sessionState.repositoryInfo.owner,
          name: sessionState.repositoryInfo.name,
          branch: sessionState.repositoryInfo.branch
        } : undefined,
        priority: 'medium'
      };
      
      const response = await ApiService.createIssueWithContext(request, false, false);
      
      if (response.success && response.user_issue) {
        setSessionState(prev => ({
          ...prev,
          userIssues: [...prev.userIssues, response.user_issue!],
          currentIssue: response.user_issue!,
          isLoading: false,
          lastUpdated: new Date()
        }));
        return response.user_issue;
      } else {
        throw new Error('Failed to create issue');
      }
    } catch (error) {
      setSessionState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to create issue',
        isLoading: false
      }));
      throw error;
    }
  };
  
  const loadUserIssues = async (): Promise<void> => {
    if (!sessionState.repositoryInfo) return;
    
    try {
      const issues = await ApiService.getUserIssues({
        repo_owner: sessionState.repositoryInfo.owner,
        repo_name: sessionState.repositoryInfo.name
      });
      
      setSessionState(prev => ({
        ...prev,
        userIssues: issues,
        lastUpdated: new Date()
      }));
    } catch (error) {
      console.error('Failed to load user issues:', error);
    }
  };
  
  const updateIssue = (issueId: string, updates: Partial<UserIssueResponse>): void => {
    setSessionState(prev => ({
      ...prev,
      userIssues: prev.userIssues.map(issue => 
        issue.issue_id === issueId ? { ...issue, ...updates } : issue
      ),
      lastUpdated: new Date()
    }));
  };
  
  // Agent management
  const startAgent = async (agentType: 'daifu' | 'architect' | 'coder' | 'tester'): Promise<void> => {
    if (!sessionState.sessionId) {
      throw new Error('No active session');
    }
    
    const agentStatus: AgentStatus = {
      type: agentType,
      status: 'processing',
      started_at: new Date().toISOString()
    };
    
    setSessionState(prev => ({
      ...prev,
      agentStatus,
      agentHistory: [...prev.agentHistory, agentStatus],
      lastUpdated: new Date()
    }));
    
    // Here you would call the appropriate agent API
    // For now, simulate agent processing
    setTimeout(() => {
      const completedStatus: AgentStatus = {
        ...agentStatus,
        status: 'completed',
        completed_at: new Date().toISOString()
      };
      
      setSessionState(prev => ({
        ...prev,
        agentStatus: completedStatus,
        lastUpdated: new Date()
      }));
    }, 5000);
  };
  
  const updateAgentStatus = (status: AgentStatus): void => {
    setSessionState(prev => ({
      ...prev,
      agentStatus: status,
      lastUpdated: new Date()
    }));
  };
  
  // Tab management
  const setActiveTab = (tab: string): void => {
    setTabState(prev => ({
      ...prev,
      activeTab: tab as any,
      tabHistory: [tab as any, ...prev.tabHistory.filter(t => t !== tab)].slice(0, 10)
    }));
  };
  
  const refreshTab = (tab: string): void => {
    setTabState(prev => ({
      ...prev,
      refreshKeys: {
        ...prev.refreshKeys,
        [tab]: (prev.refreshKeys as any)[tab] + 1
      }
    }));
  };
  
  // Repository management
  const updateRepositoryInfo = (repoInfo: any): void => {
    setSessionState(prev => ({
      ...prev,
      repositoryInfo: { ...prev.repositoryInfo, ...repoInfo },
      lastUpdated: new Date()
    }));
  };
  
  // Utility functions
  const exportSessionData = (): SessionState => {
    return sessionState;
  };
  
  const importSessionData = (data: Partial<SessionState>): void => {
    setSessionState(prev => ({ ...prev, ...data, lastUpdated: new Date() }));
  };
  
  const reconnect = (): void => {
    if (sessionState.sessionId) {
      establishRealtimeConnection(sessionState.sessionId);
    }
  };
  
  const value: SessionContextValue = {
    sessionState,
    tabState,
    createSession,
    loadSession,
    switchSession,
    clearSession,
    refreshSession,
    connectionStatus,
    reconnect,
    sendMessage,
    refreshMessages,
    clearMessages,
    addContextCard,
    removeContextCard,
    updateContextCards,
    addFileContext,
    removeFileContext,
    updateFileContext,
    createIssue,
    loadUserIssues,
    updateIssue,
    startAgent,
    updateAgentStatus,
    setActiveTab,
    refreshTab,
    updateRepositoryInfo,
    exportSessionData,
    importSessionData
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
};

/**
 * Custom hook to access session context
 * Provides comprehensive session state management and real-time updates
 * 
 * @throws Error if used outside of SessionProvider
 * @returns SessionContextValue - Complete session management interface
 */
export const useSession = (): SessionContextValue => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};

/**
 * Helper hook to get current session state without management functions
 * Useful for components that only need to read session data
 */
export const useSessionState = (): SessionState => {
  const { sessionState } = useSession();
  return sessionState;
};

/**
 * Helper hook to get current tab state without management functions
 * Useful for components that only need to read tab data
 */
export const useTabState = (): TabState => {
  const { tabState } = useSession();
  return tabState;
};

/**
 * Helper hook to get real-time connection status
 * Useful for displaying connection indicators
 */
export const useConnectionStatus = (): 'connected' | 'disconnected' | 'reconnecting' => {
  const { connectionStatus } = useSession();
  return connectionStatus;
}; 