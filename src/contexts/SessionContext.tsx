import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ApiService } from '../services/api';
import { useRepository } from '../hooks/useRepository';
import { useAuth } from '../hooks/useAuth';

interface SessionContextValue {
  currentSessionId: string | null;
  setCurrentSessionId: (sessionId: string | null) => void;
  createSession: (repoOwner: string, repoName: string, repoBranch?: string, title?: string) => Promise<string>;
  getSessionContext: (sessionId: string) => Promise<{
    session: import('../types').ChatSession;
    messages: import('../types').ChatMessageAPI[];
    context_cards: string[];
    repository_info?: Record<string, unknown>;
  }>;
  isLoading: boolean;
  error: string | null;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

interface SessionProviderProps {
  children: ReactNode;
}

const STORAGE_KEY = 'yudai_current_session_id';

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const [currentSessionId, setCurrentSessionIdState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { selectedRepository } = useRepository();
  const { isAuthenticated } = useAuth();

  // Load session ID from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setCurrentSessionIdState(stored);
      }
    } catch (error) {
      console.error('Failed to load session ID from localStorage:', error);
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Save session ID to localStorage whenever it changes
  const setCurrentSessionId = (sessionId: string | null) => {
    setCurrentSessionIdState(sessionId);
    
    if (sessionId) {
      try {
        localStorage.setItem(STORAGE_KEY, sessionId);
      } catch (error) {
        console.error('Failed to save session ID to localStorage:', error);
      }
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  // Create a new session for the selected repository
  const createSession = async (
    repoOwner: string, 
    repoName: string, 
    repoBranch: string = 'main',
    title?: string
  ): Promise<string> => {
    if (!isAuthenticated) {
      throw new Error('User must be authenticated to create a session');
    }

    setIsLoading(true);
    setError(null);

    try {
      const session = await ApiService.createOrGetSession(
        repoOwner,
        repoName,
        repoBranch,
        title
      );

      const sessionId = session.id; // Use id field from ChatSession
      setCurrentSessionId(sessionId);
      return sessionId;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create session';
      setError(errorMessage);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // Get session context
  const getSessionContext = async (sessionId: string) => {
    if (!isAuthenticated) {
      throw new Error('User must be authenticated to get session context');
    }

    try {
      return await ApiService.getSessionContext(sessionId);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to get session context';
      setError(errorMessage);
      throw error;
    }
  };

  // Auto-create session when repository is selected
  useEffect(() => {
    if (isAuthenticated && selectedRepository && !currentSessionId) {
      createSession(
        selectedRepository.repository.full_name.split('/')[0],
        selectedRepository.repository.name,
        selectedRepository.branch,
        `Session for ${selectedRepository.repository.full_name}`
      ).catch(error => {
        console.error('Failed to auto-create session:', error);
      });
    }
  }, [isAuthenticated, selectedRepository, currentSessionId]);

  const value: SessionContextValue = {
    currentSessionId,
    setCurrentSessionId,
    createSession,
    getSessionContext,
    isLoading,
    error,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = (): SessionContextValue => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}; 