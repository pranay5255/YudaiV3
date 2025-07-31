import React, { createContext, useState, useEffect, ReactNode, useReducer } from 'react';
import { ApiService } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import {
  UnifiedSessionState,
  UnifiedWebSocketMessage,
  UnifiedMessage,
  TabState,
  AgentType,
  AgentStatus as UnifiedAgentStatusEnum,
  ContextCardUpdateData,
  WebSocketMessageType
} from '../types/unifiedState';

/**
 * Comprehensive Session Context Interface
 * Manages all application state through session-based architecture
 */
export interface SessionContextValue {
  // Core session state, directly from the backend
  sessionState: UnifiedSessionState;
  // UI-only state for tabs
  tabState: TabState;
  // Real-time connection status
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
  
  // A function to set the active session ID, which triggers connection
  setActiveSessionId: (sessionId: string | null) => void;
  
  // A dispatcher for UI-only state changes (like active tab)
  dispatch: React.Dispatch<SessionAction>;
}

// A simple reducer action type for UI state changes
export type SessionAction =
  | { type: 'SET_ACTIVE_TAB'; payload: import('../types/unifiedState').TabType }
  | { type: 'REFRESH_TAB'; payload: import('../types/unifiedState').TabType };

export const SessionContext = createContext<SessionContextValue | undefined>(undefined);

interface SessionProviderProps {
  children: ReactNode;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const { token } = useAuth();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const [sessionState, setSessionState] = useState<UnifiedSessionState>({
    session_id: null,
    user_id: null,
    repository: null,
    messages: [],
    context_cards: [],
    file_embeddings: [],
    agent_status: { type: AgentType.DAIFU, status: UnifiedAgentStatusEnum.IDLE },
    statistics: { total_messages: 0, total_tokens: 0, total_cost: 0, session_duration: 0, agent_actions: 0, files_processed: 0 },
    last_activity: new Date().toISOString(),
    is_active: false
  });

  const initialTabState: TabState = {
    activeTab: 'chat',
    refreshKeys: { chat: 0, 'file-deps': 0, context: 0, ideas: 0 },
    tabHistory: ['chat']
  };

  const tabReducer = (state: TabState, action: SessionAction): TabState => {
    switch (action.type) {
      case 'SET_ACTIVE_TAB':
        return {
          ...state,
          activeTab: action.payload,
          tabHistory: [action.payload, ...state.tabHistory.filter(t => t !== action.payload)].slice(0, 10)
        };
      case 'REFRESH_TAB':
        return {
          ...state,
          refreshKeys: {
            ...state.refreshKeys,
            [action.payload]: state.refreshKeys[action.payload] + 1
          }
        };
      default:
        return state;
    }
  };

  const [tabState, dispatch] = useReducer(tabReducer, initialTabState);
  
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected');

  // This effect manages the WebSocket connection lifecycle.
  useEffect(() => {
    if (!activeSessionId || !token) {
      return;
    }

    setConnectionStatus('reconnecting');
    const ws = ApiService.createSessionWebSocket(activeSessionId, token);

    ws.onopen = () => {
      console.log(`WebSocket connected for session: ${activeSessionId}`);
      setConnectionStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const message: UnifiedWebSocketMessage = JSON.parse(event.data);
        console.log('Real-time update received:', message);
        
        // Use a reducer-like pattern to update state based on message type
        setSessionState(prevState => {
            switch (message.type) {
                case WebSocketMessageType.SESSION_UPDATE:
                    return message.data as UnifiedSessionState;
                case WebSocketMessageType.MESSAGE:
                    return { ...prevState, messages: [...prevState.messages, message.data as UnifiedMessage] };
                case WebSocketMessageType.CONTEXT_CARD: {
                    const { action, card } = message.data as ContextCardUpdateData;
                    return { ...prevState, context_cards: action === 'add' ? [...prevState.context_cards, card] : prevState.context_cards.filter(c => c.id !== card.id) };
                }
                // ... other cases
                default:
                    return prevState;
            }
        });

      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('disconnected');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('disconnected');
      // Optionally add reconnect logic here
    };

    // Cleanup on component unmount or when activeSessionId changes
    return () => {
      ws.close();
    };
  }, [activeSessionId, token]);

  // The context value now only provides state and a way to change the active session.
  // All other logic will be moved to the `useSessionHelpers` hook.
  const value: SessionContextValue = {
    sessionState,
    tabState,
    connectionStatus,
    setActiveSessionId,
    dispatch: dispatch,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
};
