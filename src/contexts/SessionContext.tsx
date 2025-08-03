import React, { createContext, useState, useEffect, ReactNode, useReducer, useCallback, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';
import { ApiService } from '../services/api';
import { debounce } from '../utils/debounce';
import {
  UnifiedSessionState,
  TabState,
  AgentType,
  AgentStatus as UnifiedAgentStatusEnum,
  MessageRole,
  UnifiedMessage
} from '../types/unifiedState';
import { SessionContextResponse, ChatMessageAPI } from '../types';

// Define proper types for the context
interface OptimisticUpdateData {
  content?: string;
  is_code?: boolean;
  [key: string]: unknown;
}

/**
 * Enhanced Session Context Interface
 * Manages all application state through session-based architecture with real-time updates
 */
export interface SessionContextValue {
  // Core session state, directly from the backend
  sessionState: UnifiedSessionState;
  // UI-only state for tabs
  tabState: TabState;
  // Connection status (simplified for HTTP API)
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
  
  // A function to set the active session ID, which triggers polling
  setActiveSessionId: (sessionId: string | null) => void;
  
  // A dispatcher for UI-only state changes (like active tab)
  dispatch: React.Dispatch<SessionAction>;
  
  // Send optimistic updates for immediate UI feedback
  sendOptimisticUpdate: (action: string, data: OptimisticUpdateData) => void;
  
  // Force refresh session data
  refreshSession: () => Promise<void>;
}

// A simple reducer action type for UI state changes
export type SessionAction =
  | { type: 'SET_ACTIVE_TAB'; payload: import('../types/unifiedState').TabType }
  | { type: 'REFRESH_TAB'; payload: import('../types/unifiedState').TabType };

// Export the context but suppress the fast refresh warning with eslint-disable
// eslint-disable-next-line react-refresh/only-export-components
export const SessionContext = createContext<SessionContextValue | undefined>(undefined);

interface SessionProviderProps {
  children: ReactNode;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const { token } = useAuth();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    return localStorage.getItem('activeSessionId');
  });

  const initialSessionState: UnifiedSessionState = {
    session_id: null,
    user_id: null,
    repository: null,
    messages: [],
    context_cards: [],
    agent_status: {
      type: AgentType.DAIFU,
      status: UnifiedAgentStatusEnum.IDLE
    },
    statistics: {
      total_messages: 0,
      total_tokens: 0,
      total_cost: 0,
      session_duration: 0,
      agent_actions: 0,
      files_processed: 0
    },
    last_activity: new Date().toISOString(),
    is_active: false
  };

  const [sessionState, setSessionState] = useState<UnifiedSessionState>(initialSessionState);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected');
  
  // Refs for managing polling and state updates
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastUpdateTimestampRef = useRef<string | null>(null);
  const isPollingRef = useRef<boolean>(false);
  
  // Save the active session ID in localStorage whenever it changes
  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem('activeSessionId', activeSessionId);
    } else {
      localStorage.removeItem('activeSessionId');
    }
  }, [activeSessionId]);
  
  const initialTabState: TabState = {
    activeTab: 'chat',
    refreshKeys: {
      'chat': 0,
      'file-deps': 0,
      'context': 0,
      'ideas': 0
    },
    tabHistory: ['chat']
  };

  const tabReducer = (state: TabState, action: SessionAction): TabState => {
    switch (action.type) {
      case 'SET_ACTIVE_TAB': {
        return {
          ...state,
          activeTab: action.payload,
          tabHistory: [action.payload, ...state.tabHistory.filter(t => t !== action.payload)].slice(0, 10)
        };
      }
      case 'REFRESH_TAB': {
        return {
          ...state,
          refreshKeys: {
            ...state.refreshKeys,
            [action.payload]: state.refreshKeys[action.payload] + 1
          }
        };
      }
      default:
        return state;
    }
  };

  const [tabState, dispatch] = useReducer(tabReducer, initialTabState);
  
  // Debounced state update to prevent excessive re-renders
  const debouncedSetSessionState = useCallback((updater: (prev: UnifiedSessionState) => UnifiedSessionState) => {
    const debouncedUpdate = debounce(() => {
      setSessionState(updater);
    }, 50);
    debouncedUpdate();
  }, []);

  // Convert API response to UnifiedSessionState
  const convertApiResponseToUnifiedState = useCallback((response: SessionContextResponse): UnifiedSessionState => {
    return {
      session_id: response.session.session_id,
      user_id: null, // Not provided in API response
      repository: response.repository_info ? {
        owner: response.repository_info.owner,
        name: response.repository_info.name,
        branch: response.repository_info.branch,
        full_name: response.repository_info.full_name,
        html_url: response.repository_info.html_url
      } : null,
      messages: response.messages.map((msg: ChatMessageAPI): UnifiedMessage => ({
        id: msg.message_id,
        session_id: response.session.session_id,
        content: msg.message_text,
        role: msg.role as MessageRole,
        is_code: msg.is_code,
        timestamp: msg.created_at,
        tokens: msg.tokens,
        metadata: msg.error_message ? { error: msg.error_message } : undefined
      })),
      context_cards: [], // Context cards not fully implemented in API yet
      agent_status: {
        type: AgentType.DAIFU,
        status: UnifiedAgentStatusEnum.IDLE
      },
      statistics: {
        total_messages: response.statistics?.total_messages || response.session.total_messages,
        total_tokens: response.statistics?.total_tokens || response.session.total_tokens,
        total_cost: response.statistics?.total_cost || 0,
        session_duration: response.statistics?.session_duration || 0,
        agent_actions: 0,
        files_processed: response.file_embeddings_count || 0
      },
      last_activity: response.session.last_activity || response.session.updated_at || response.session.created_at,
      is_active: response.session.is_active
    };
  }, []);

  // Handle session data updates from polling
  const handleSessionUpdate = useCallback((apiResponse: SessionContextResponse) => {
    const newSessionState = convertApiResponseToUnifiedState(apiResponse);
    
    // Check if this is a newer update
    if (lastUpdateTimestampRef.current && newSessionState.last_activity <= lastUpdateTimestampRef.current) {
      return; // Skip outdated updates
    }
    
    lastUpdateTimestampRef.current = newSessionState.last_activity;
    
    debouncedSetSessionState(prevState => {
      // Only update if there are actual changes
      if (JSON.stringify(prevState) === JSON.stringify(newSessionState)) {
        return prevState;
      }
      
      return newSessionState;
    });
  }, [convertApiResponseToUnifiedState, debouncedSetSessionState]);

  // Initialize polling when session changes
  useEffect(() => {
    if (!activeSessionId || !token) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      setConnectionStatus('disconnected');
      isPollingRef.current = false;
      return;
    }

    setConnectionStatus('connected');
    isPollingRef.current = true;
    
    // Initial load
    const loadSession = async () => {
      try {
        const sessionData = await ApiService.getSession(activeSessionId);
        handleSessionUpdate(sessionData);
      } catch (error) {
        console.error('Failed to load session:', error);
        setConnectionStatus('disconnected');
      }
    };
    
    loadSession();
    
    // Set up polling every 3 seconds
    pollingIntervalRef.current = setInterval(async () => {
      if (!isPollingRef.current) return;
      
      try {
        const sessionData = await ApiService.getSession(activeSessionId);
        handleSessionUpdate(sessionData);
        setConnectionStatus('connected');
      } catch (error) {
        console.error('Polling error:', error);
        setConnectionStatus('disconnected');
      }
    }, 3000);

    return () => {
      isPollingRef.current = false;
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [activeSessionId, token, handleSessionUpdate]);

  // Optimistic updates for user actions
  const sendOptimisticUpdate = useCallback((action: string, data: OptimisticUpdateData) => {
    // Apply optimistic update immediately
    debouncedSetSessionState(prevState => {
      switch (action) {
        case 'SEND_MESSAGE': {
          const optimisticMessage = {
            id: `temp-${Date.now()}`,
            session_id: activeSessionId || '',
            content: data.content || '',
            role: MessageRole.USER,
            is_code: data.is_code || false,
            timestamp: new Date().toISOString(),
            tokens: 0,
            metadata: { status: 'sending' }
          };
          return {
            ...prevState,
            messages: [...prevState.messages, optimisticMessage]
          };
        }
        
        default:
          return prevState;
      }
    });
  }, [debouncedSetSessionState, activeSessionId]);

  // Force refresh session data
  const refreshSession = useCallback(async () => {
    if (!activeSessionId) return;
    
    try {
      setConnectionStatus('reconnecting');
      const sessionData = await ApiService.getSession(activeSessionId);
      handleSessionUpdate(sessionData);
      setConnectionStatus('connected');
    } catch (error) {
      console.error('Failed to refresh session:', error);
      setConnectionStatus('disconnected');
      throw error;
    }
  }, [activeSessionId, handleSessionUpdate]);


  // The context value now provides HTTP API-based capabilities
  const value: SessionContextValue = {
    sessionState,
    tabState,
    connectionStatus,
    setActiveSessionId,
    dispatch: dispatch,
    sendOptimisticUpdate,
    refreshSession,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
};