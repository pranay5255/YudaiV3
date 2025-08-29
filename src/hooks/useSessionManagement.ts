import { useCallback, useEffect } from 'react';
import { useSessionStore } from '../stores/sessionStore';
import { useCreateSessionFromRepository, useEnsureSessionExists } from './useSessionQueries';
import { SelectedRepository } from '../types';

/**
 * Custom hook for session management that integrates with the session store
 * Provides session creation, validation, and management functionality
 * Handles OAuth callback parsing and session initialization on app launch
 */
export const useSessionManagement = () => {
  const {
    activeSessionId,
    selectedRepository,
    sessionInitialized,
    isLoading,
    error,
    isAuthenticated,
    authLoading,
    user,
    activeTab,
    sidebarCollapsed,
    createSessionForRepository,
    ensureSessionExists,
    setActiveSession,
    clearSession,
    setSelectedRepository,
    setError,
    setActiveTab,
    setSidebarCollapsed,
  } = useSessionStore();

  const createSessionMutation = useCreateSessionFromRepository();
  const ensureSessionMutation = useEnsureSessionExists();

  // Auto-create session when repository is selected and user is authenticated
  useEffect(() => {
    if (isAuthenticated && user && selectedRepository && !activeSessionId && !sessionInitialized && !isLoading && !authLoading && !createSessionMutation.isPending) {
      console.log('[SessionManagement] Auto-creating session for repository:', selectedRepository.repository.name);
      createSessionMutation.mutate(selectedRepository, {
        onSuccess: (sessionId) => {
          if (!sessionId) {
            console.error('[SessionManagement] Failed to create session');
            setError('Failed to create session');
          } else {
            console.log('[SessionManagement] Session created successfully:', sessionId);
          }
        },
        onError: (error) => {
          console.error('[SessionManagement] Session creation error:', error);
          setError(error instanceof Error ? error.message : 'Failed to create session');
          // Add retry logic
          setTimeout(() => createSessionMutation.mutate(selectedRepository), 2000);  // Retry after 2s
        },
      });
    }
  }, [isAuthenticated, user, selectedRepository, activeSessionId, sessionInitialized, isLoading, authLoading, createSessionMutation, setError]);

  // Validate session exists when activeSessionId changes (but not during creation)
  useEffect(() => {
    if (isAuthenticated && user && activeSessionId && !sessionInitialized && !createSessionMutation.isPending && !ensureSessionMutation.isPending) {
      console.log('[SessionManagement] Validating existing session:', activeSessionId);
      ensureSessionMutation.mutate(activeSessionId, {
        onSuccess: (exists) => {
          if (!exists) {
            console.warn('[SessionManagement] Session does not exist:', activeSessionId);
            clearSession();
            setError('Session not found');
          } else {
            console.log('[SessionManagement] Session validation successful:', activeSessionId);
          }
        },
        onError: (error) => {
          console.error('[SessionManagement] Session validation error:', error);
          clearSession();
          setError('Session validation failed');
        },
      });
    }
  }, [isAuthenticated, user, activeSessionId, sessionInitialized, ensureSessionMutation, clearSession, setError, createSessionMutation.isPending]);

  // Manual session creation
  const createSession = useCallback(async (repository: SelectedRepository) => {
    try {
      setError(null);
      const sessionId = await createSessionForRepository(repository);
      return sessionId;
    } catch (error) {
      console.error('[SessionManagement] Manual session creation failed:', error);
      setError(error instanceof Error ? error.message : 'Failed to create session');
      return null;
    }
  }, [createSessionForRepository, setError]);

  // Manual session validation
  const validateSession = useCallback(async (sessionId: string) => {
    try {
      setError(null);
      const exists = await ensureSessionExists(sessionId);
      return exists;
    } catch (error) {
      console.error('[SessionManagement] Session validation failed:', error);
      setError(error instanceof Error ? error.message : 'Session validation failed');
      return false;
    }
  }, [ensureSessionExists, setError]);

  // Set active session
  const setSession = useCallback((sessionId: string) => {
    setActiveSession(sessionId);
    setError(null);
  }, [setActiveSession, setError]);

  // Clear current session
  const clearCurrentSession = useCallback(() => {
    clearSession();
    setError(null);
  }, [clearSession, setError]);

  return {
    // Auth state
    isAuthenticated,
    authLoading,
    user,
    
    // Session state
    activeSessionId,
    selectedRepository,
    sessionInitialized,
    isLoading,
    error,
    
    // UI state
    activeTab,
    sidebarCollapsed,
    
    // Actions
    createSession,
    validateSession,
    setSession,
    clearSession: clearCurrentSession,
    setSelectedRepository,
    setActiveTab,
    setSidebarCollapsed,
    
    // Mutation states
    isCreatingSession: createSessionMutation.isPending,
    isValidatingSession: ensureSessionMutation.isPending,
    createSessionError: createSessionMutation.error,
    validateSessionError: ensureSessionMutation.error,
  };
};
