import { useEffect, useRef } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AgentWorkbench } from './components/AgentWorkbench';
import { AuthCallback } from './components/AuthCallback';
import { AuthSuccess } from './components/AuthSuccess';
import { DemoWorkbench } from './components/DemoWorkbench';
import { LoginPage } from './components/LoginPage';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SessionErrorBoundary } from './components/SessionErrorBoundary';
import { useAuth } from './hooks/useAuth';
import { useSessionStore } from './stores/sessionStore';

function App(): JSX.Element {
  const { initializeAuth, isAuthenticated, sessionToken } = useAuth();
  const clearSession = useSessionStore((state) => state.clearSession);
  const setActiveTab = useSessionStore((state) => state.setActiveTab);
  const setSelectedRepository = useSessionStore((state) => state.setSelectedRepository);
  const previousTokenRef = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    void initializeAuth();
  }, [initializeAuth]);

  useEffect(() => {
    if (previousTokenRef.current === undefined) {
      previousTokenRef.current = sessionToken;
      return;
    }

    if (previousTokenRef.current !== sessionToken) {
      clearSession();
      setSelectedRepository(null);
      setActiveTab('chat');
      previousTokenRef.current = sessionToken;
    }
  }, [clearSession, sessionToken, setActiveTab, setSelectedRepository]);

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      clearSession();
    }, 10 * 60 * 1000);

    return () => window.clearTimeout(timer);
  }, [clearSession, isAuthenticated]);

  function handleSessionError(): void {
    clearSession();
  }

  function handleRetry(): void {
    window.location.href = '/auth/login';
  }

  return (
    <SessionErrorBoundary
      onRetry={handleRetry}
      onSessionError={handleSessionError}
    >
      <Routes>
        <Route element={<LoginPage />} path="/auth/login" />
        <Route element={<DemoWorkbench />} path="/demo" />
        <Route element={<AuthSuccess />} path="/auth/success" />
        <Route element={<AuthCallback />} path="/auth/callback" />
        <Route
          element={(
            <ProtectedRoute>
              <AgentWorkbench />
            </ProtectedRoute>
          )}
          path="/"
        />
        <Route element={<Navigate replace to="/" />} path="*" />
      </Routes>
    </SessionErrorBoundary>
  );
}

export default App;
