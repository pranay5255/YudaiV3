import React, { createContext, useState, useEffect, ReactNode, useReducer, useCallback, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';
import { RealTimeManager } from '../services/RealTimeManager';
import { debounce } from '../utils/debounce';
import {
  UnifiedSessionState,
  TabState,
  AgentType,
  AgentStatus as UnifiedAgentStatusEnum,
  WebSocketMessageType,
  MessageRole
} from '../types/unifiedState';

/**
 * Enhanced Session Context Interface
 * Manages all application state through session-based architecture with real-time updates
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
  
  // Send optimistic updates for immediate UI feedback
  sendOptimisticUpdate: (action: string, data: any) => void;
  
  // Send real-time message through WebSocket
  sendRealtimeMessage: (message: any) => void;
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
  
  // Refs for managing real-time updates
  const realTimeManagerRef = useRef<RealTimeManager | null>(null);
  const stateUpdateQueueRef = useRef<Set<string>>(new Set());
  const lastUpdateRef = useRef<Record<string, number>>({});
  
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
  
  // Debounced state update to prevent excessive re-renders
  const debouncedSetSessionState = useCallback(
    debounce((updater: (prev: UnifiedSessionState) => UnifiedSessionState) => {
      setSessionState(updater);
    }, 50), // 50ms debounce for real-time feel
    []
  );

  // Handle real-time updates with conflict resolution
  const handleRealTimeUpdate = useCallback((update: any) => {
    const updateId = `${update.type}-${update.timestamp || Date.now()}`;
    
    // Prevent duplicate updates within 50ms
    if (stateUpdateQueueRef.current.has(updateId)) {
      return;
    }
    
    // Check if this update is newer than the last one
    const lastUpdate = lastUpdateRef.current[update.type] || 0;
    if (update.timestamp && update.timestamp < lastUpdate) {
      console.log('⏭️ Skipping outdated update:', update.type);
      return;
    }
    
    stateUpdateQueueRef.current.add(updateId);
    lastUpdateRef.current[update.type] = update.timestamp || Date.now();

    debouncedSetSessionState(prevState => {
      switch (update.type) {
        case WebSocketMessageType.SESSION_UPDATE:
          return { ...prevState, ...update.data };
        
        case WebSocketMessageType.MESSAGE:
          // Prevent duplicate messages
          const messageExists = prevState.messages.some(m => m.id === update.data.id);
          if (messageExists) return prevState;
          
          return {
            ...prevState,
            messages: [...prevState.messages, update.data]
          };
        
        case WebSocketMessageType.CONTEXT_CARD:
          if (update.data.action === 'batch') {
            // Handle batch context card updates
            const newCards = update.data.cards.filter((card: any) => 
              !prevState.context_cards.some(existing => existing.id === card.id)
            );
            return {
              ...prevState,
              context_cards: [...prevState.context_cards, ...newCards]
            };
          } else {
            // Handle single context card update
            const { action, card } = update.data;
            if (action === 'add') {
              return {
                ...prevState,
                context_cards: [...prevState.context_cards, card]
              };
            } else if (action === 'remove') {
              return {
                ...prevState,
                context_cards: prevState.context_cards.filter(c => c.id !== card.id)
              };
            }
          }
          return prevState;
        
        case WebSocketMessageType.AGENT_STATUS:
          return {
            ...prevState,
            agent_status: { ...prevState.agent_status, ...update.data }
          };
        
        case WebSocketMessageType.STATISTICS:
          return {
            ...prevState,
            statistics: { ...prevState.statistics, ...update.data }
          };
        

        
        case WebSocketMessageType.ERROR:
          console.error('Real-time error:', update.data);
          return prevState;
        
        default:
          return prevState;
      }
    });

    // Clean up update ID after processing
    setTimeout(() => {
      stateUpdateQueueRef.current.delete(updateId);
    }, 1000);
  }, [debouncedSetSessionState]);

  // Initialize real-time connection when session changes
  useEffect(() => {
    if (!activeSessionId || !token) {
      if (realTimeManagerRef.current) {
        realTimeManagerRef.current.disconnect();
        realTimeManagerRef.current = null;
      }
      setConnectionStatus('disconnected');
      return;
    }

    setConnectionStatus('reconnecting');
    
    // Create new real-time manager
    realTimeManagerRef.current = new RealTimeManager({
      sessionId: activeSessionId,
      token,
      onMessage: handleRealTimeUpdate,
      onError: (error) => {
        console.error('Real-time error:', error);
        setConnectionStatus('disconnected');
      },
      onConnectionStatusChange: setConnectionStatus
    });

    realTimeManagerRef.current.connect();

    return () => {
      if (realTimeManagerRef.current) {
        realTimeManagerRef.current.disconnect();
        realTimeManagerRef.current = null;
      }
    };
  }, [activeSessionId, token, handleRealTimeUpdate]);

  // Optimistic updates for user actions
  const sendOptimisticUpdate = useCallback((action: string, data: any) => {
    // Apply optimistic update immediately
    debouncedSetSessionState(prevState => {
      switch (action) {
        case 'SEND_MESSAGE':
          const optimisticMessage = {
            id: `temp-${Date.now()}`,
            session_id: activeSessionId || '',
            content: data.content,
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
        
        default:
          return prevState;
      }
    });

    // Send to backend via WebSocket
    if (realTimeManagerRef.current) {
      realTimeManagerRef.current.send({ type: action, data });
    }
  }, [debouncedSetSessionState, activeSessionId]);

  // Send real-time message
  const sendRealtimeMessage = useCallback((message: any) => {
    if (realTimeManagerRef.current) {
      realTimeManagerRef.current.send(message);
    } else {
      console.warn('RealTimeManager not available');
    }
  }, []);


  // The context value now provides enhanced real-time capabilities
  const value: SessionContextValue = {
    sessionState,
    tabState,
    connectionStatus,
    setActiveSessionId,
    dispatch: dispatch,
    sendOptimisticUpdate,
    sendRealtimeMessage,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
};