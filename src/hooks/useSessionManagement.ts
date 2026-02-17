import { useCallback } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useSessionStore } from '../stores/sessionStore';
import { useAuthStore } from '../stores/authStore';
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

  const { isAuthenticated, isLoading: authLoading, user } = useAuthStore(
    useShallow((state) => ({
      isAuthenticated: state.isAuthenticated,
      isLoading: state.isLoading,
      user: state.user,
    }))
  );

  // Manual session creation
  const createSession = useCallback(async (repository: SelectedRepository) => {
    try {
      setError(null);
      const sessionId = await createSessionForRepository(repository);
      return sessionId;
    } catch (error) {
      console.error('[SessionManagement] Manual session creation failed:', error);
      setError(error instanceof Error ? error.message : 'Failed to create session');
      throw error;
    }
  }, [createSessionForRepository, setError]);

  // Manual session validation
  const validateSession = useCallback(async (sessionId: string) => {
    try {
      setError(null);
      await ensureSessionExists(sessionId);
      return true;
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
    
    // Derived statuses
    isCreatingSession: false,
    isValidatingSession: false,
    createSessionError: null,
    validateSessionError: null,
  };
};
