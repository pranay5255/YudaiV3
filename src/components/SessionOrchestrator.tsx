import { useEffect, useRef } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useAuthStore } from '../stores/authStore';
import { useSessionStore } from '../stores/sessionStore';

/**
 * Central session lifecycle orchestrator.
 * This component owns session side effects so they run exactly once in the app tree.
 */
export const SessionOrchestrator = () => {
  const { isAuthenticated, isLoading: authLoading, user } = useAuthStore(
    useShallow((state) => ({
      isAuthenticated: state.isAuthenticated,
      isLoading: state.isLoading,
      user: state.user,
    }))
  );

  const {
    activeSessionId,
    selectedRepository,
    sessionInitialized,
    sessionStatus,
    isLoading,
    createSessionForRepository,
    ensureSessionExists,
    loadMessages,
    loadContextCards,
    clearSession,
    setError,
  } = useSessionStore(
    useShallow((state) => ({
      activeSessionId: state.activeSessionId,
      selectedRepository: state.selectedRepository,
      sessionInitialized: state.sessionInitialized,
      sessionStatus: state.sessionStatus,
      isLoading: state.isLoading,
      createSessionForRepository: state.createSessionForRepository,
      ensureSessionExists: state.ensureSessionExists,
      loadMessages: state.loadMessages,
      loadContextCards: state.loadContextCards,
      clearSession: state.clearSession,
      setError: state.setError,
    }))
  );

  const creatingSessionRef = useRef(false);
  const validatingSessionRef = useRef(false);
  const hydratedSessionRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated || authLoading || !user) {
      return;
    }
    if (!selectedRepository) {
      return;
    }
    if (activeSessionId || creatingSessionRef.current || isLoading) {
      return;
    }
    if (sessionStatus !== 'awaiting_session') {
      return;
    }

    creatingSessionRef.current = true;
    void createSessionForRepository(selectedRepository)
      .then((sessionId) => {
        console.log('[SessionOrchestrator] Session created:', sessionId);
      })
      .catch((error) => {
        console.error('[SessionOrchestrator] Failed to create session:', error);
        setError(error instanceof Error ? error.message : 'Failed to create session');
      })
      .finally(() => {
        creatingSessionRef.current = false;
      });
  }, [
    isAuthenticated,
    authLoading,
    user,
    selectedRepository,
    activeSessionId,
    isLoading,
    sessionStatus,
    createSessionForRepository,
    setError,
  ]);

  useEffect(() => {
    if (!isAuthenticated || authLoading || !user) {
      return;
    }
    if (!activeSessionId || sessionInitialized || validatingSessionRef.current) {
      return;
    }

    validatingSessionRef.current = true;
    void ensureSessionExists(activeSessionId)
      .catch((error) => {
        console.error('[SessionOrchestrator] Session validation failed:', error);
        clearSession();
        setError(error instanceof Error ? error.message : 'Session validation failed');
      })
      .finally(() => {
        validatingSessionRef.current = false;
      });
  }, [
    isAuthenticated,
    authLoading,
    user,
    activeSessionId,
    sessionInitialized,
    ensureSessionExists,
    clearSession,
    setError,
  ]);

  useEffect(() => {
    if (!activeSessionId || !isAuthenticated || !user) {
      hydratedSessionRef.current = null;
      return;
    }

    if (hydratedSessionRef.current === activeSessionId) {
      return;
    }

    hydratedSessionRef.current = activeSessionId;

    void Promise.allSettled([
      loadMessages(activeSessionId),
      loadContextCards(activeSessionId),
    ]).then((results) => {
      const rejected = results.find((result) => result.status === 'rejected');
      if (rejected && rejected.status === 'rejected') {
        const reason = rejected.reason;
        setError(reason instanceof Error ? reason.message : 'Failed to load session data');
      }
    });
  }, [
    activeSessionId,
    isAuthenticated,
    user,
    loadMessages,
    loadContextCards,
    setError,
  ]);

  return null;
};
