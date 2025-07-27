import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ApiService } from '../services/api';
import { ChatSession, ChatSessionStats, ChatMessageAPI } from '../types';

interface SessionContextType {
  // Current session
  currentSession: ChatSession | null;
  setCurrentSession: (session: ChatSession | null) => void;
  
  // Session management
  sessions: ChatSession[];
  loadSessions: () => Promise<void>;
  createNewSession: () => string;
  switchToSession: (sessionId: string) => Promise<void>;
  
  // Session data
  sessionMessages: ChatMessageAPI[];
  sessionStats: ChatSessionStats | null;
  loadSessionMessages: (sessionId: string) => Promise<void>;
  loadSessionStats: (sessionId: string) => Promise<void>;
  
  // Session operations
  updateSessionTitle: (sessionId: string, title: string) => Promise<void>;
  deactivateSession: (sessionId: string) => Promise<void>;
  
  // State
  isLoading: boolean;
  error: string | null;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const useSession = () => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};

interface SessionProviderProps {
  children: ReactNode;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionMessages, setSessionMessages] = useState<ChatMessageAPI[]>([]);
  const [sessionStats, setSessionStats] = useState<ChatSessionStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Generate a new session ID
  const createNewSession = (): string => {
    return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  };

  // Load all user sessions
  const loadSessions = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const userSessions = await ApiService.getChatSessions();
      setSessions(userSessions);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load sessions';
      setError(errorMessage);
      console.error('Failed to load sessions:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Switch to a specific session
  const switchToSession = async (sessionId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Find the session in our local list
      const session = sessions.find(s => s.session_id === sessionId);
      if (session) {
        setCurrentSession(session);
        
        // Load messages and stats for this session
        await Promise.all([
          loadSessionMessages(sessionId),
          loadSessionStats(sessionId)
        ]);
      } else {
        throw new Error('Session not found');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to switch session';
      setError(errorMessage);
      console.error('Failed to switch session:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Load messages for a session
  const loadSessionMessages = async (sessionId: string) => {
    try {
      const messages = await ApiService.getSessionMessages(sessionId);
      setSessionMessages(messages);
    } catch (err) {
      console.error('Failed to load session messages:', err);
      // Don't throw here to avoid breaking the session switch
    }
  };

  // Load statistics for a session
  const loadSessionStats = async (sessionId: string) => {
    try {
      const stats = await ApiService.getSessionStatistics(sessionId);
      setSessionStats(stats);
    } catch (err) {
      console.error('Failed to load session stats:', err);
      // Don't throw here to avoid breaking the session switch
    }
  };

  // Update session title
  const updateSessionTitle = async (sessionId: string, title: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      const updatedSession = await ApiService.updateSessionTitle(sessionId, title);
      
      // Update local state
      setSessions(prev => prev.map(session => 
        session.session_id === sessionId 
          ? { ...session, title: updatedSession.title }
          : session
      ));
      
      // Update current session if it's the one being updated
      if (currentSession?.session_id === sessionId) {
        setCurrentSession(prev => prev ? { ...prev, title: updatedSession.title } : null);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update session title';
      setError(errorMessage);
      console.error('Failed to update session title:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  // Deactivate a session
  const deactivateSession = async (sessionId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      await ApiService.deactivateSession(sessionId);
      
      // Remove from local state
      setSessions(prev => prev.filter(session => session.session_id !== sessionId));
      
      // Clear current session if it's the one being deactivated
      if (currentSession?.session_id === sessionId) {
        setCurrentSession(null);
        setSessionMessages([]);
        setSessionStats(null);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to deactivate session';
      setError(errorMessage);
      console.error('Failed to deactivate session:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  const value: SessionContextType = {
    currentSession,
    setCurrentSession,
    sessions,
    loadSessions,
    createNewSession,
    switchToSession,
    sessionMessages,
    sessionStats,
    loadSessionMessages,
    loadSessionStats,
    updateSessionTitle,
    deactivateSession,
    isLoading,
    error
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}; 