import { useState, useEffect, useRef, useCallback } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { TopBar } from './components/TopBar';
import { Chat } from './components/Chat';
import { ContextCards } from './components/ContextCards';
import { TrajectoryViewer } from './components/TrajectoryViewer';
import { SolveIssues } from './components/SolveIssues';
import { ToastContainer } from './components/Toast';
import { RepositorySelectionToast } from './components/RepositorySelectionToast';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SessionErrorBoundary } from './components/SessionErrorBoundary';
import { SessionOrchestrator } from './components/SessionOrchestrator';
import { AuthSuccess } from './components/AuthSuccess';
import { AuthCallback } from './components/AuthCallback';
import { LoginPage } from './components/LoginPage';
import { Toast, TabType, SelectedRepository } from './types';
import { useAuth } from './hooks/useAuth';
import { useRepository } from './hooks/useRepository';
import { useSessionManagement } from './hooks/useSessionManagement';
import { useSessionStore } from './stores/sessionStore';

/**
 * Main App Content Component
 * Simplified state management without session context
 * Handles UI state and coordinates between different sections
 */
function AppContent() {
  // Auth and repository contexts
  const { user, isAuthenticated } = useAuth();
  const { setSelectedRepository, hasSelectedRepository, selectedRepository } = useRepository();
  
  // Session management hook for state management
  const {
    activeSessionId,
    activeTab,
    setActiveTab,
    clearSession
  } = useSessionManagement();

  const { currentSession } = useSessionStore();
  const contextCards = useSessionStore((state) => state.contextCards);
  const deleteContextCard = useSessionStore((state) => state.deleteContextCard);

  const isValidTab = (tab: unknown): tab is TabType =>
    tab === 'chat' || tab === 'context' || tab === 'ideas' || tab === 'solve';

  useEffect(() => {
    if (!isValidTab(activeTab)) {
      setActiveTab('chat');
    }
  }, [activeTab, setActiveTab]);

  const currentTab: TabType = isValidTab(activeTab) ? activeTab : 'chat';
  
  // Local UI state
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Repository selection state - always show after login if no repository selected
  const [showRepositorySelection, setShowRepositorySelection] = useState(false);

  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const newToast: Toast = {
      id: Date.now().toString(),
      message,
      type,
    };
    setToasts(prev => [...prev, newToast]);
  }, []);

  // Show repository selection after login if no repository is selected
  useEffect(() => {
    console.log('Repository selection check:', {
      isAuthenticated,
      user: !!user,
      hasSelectedRepository
    });

    // Always show repository selection after login if no repository is selected
    if (isAuthenticated && user && !hasSelectedRepository) {
      console.log('Showing repository selection toast');
      // Add a small delay to let the user see they've logged in
      const timer = setTimeout(() => {
        setShowRepositorySelection(true);
      }, 1000);

      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, user, hasSelectedRepository]);

  // Session initialization check
  useEffect(() => {
    if (isAuthenticated && user && !activeSessionId && hasSelectedRepository) {
      console.log('User is authenticated and has selected repository but no active session');
      // Optionally auto-create a session or prompt user
      addToast('Ready to start a chat session!', 'info');
    }
  }, [isAuthenticated, user, activeSessionId, hasSelectedRepository, addToast]);

  const handleRepositoryConfirm = async (selection: SelectedRepository) => {
    try {
      const normalizeSelection = (repoSelection: SelectedRepository) => ({
        owner: repoSelection.repository.owner?.login || repoSelection.repository.full_name.split('/')[0],
        name: repoSelection.repository.name,
        branch: repoSelection.branch || '',
      });

      const selectionRepo = normalizeSelection(selection);
      const selectedRepo = selectedRepository ? normalizeSelection(selectedRepository) : null;
      const sessionRepo = currentSession ? {
        owner: currentSession.repo_owner || '',
        name: currentSession.repo_name || '',
        branch: currentSession.repo_branch || '',
      } : null;

      const matchesRepo = (a: { owner: string; name: string; branch: string }, b: { owner: string; name: string; branch: string }) =>
        a.owner === b.owner && a.name === b.name && a.branch === b.branch;

      const selectionDiffersFromSelected = selectedRepo ? !matchesRepo(selectionRepo, selectedRepo) : false;
      const selectionDiffersFromSession = sessionRepo ? !matchesRepo(selectionRepo, sessionRepo) : false;
      const shouldResetSession = Boolean(activeSessionId && (selectionDiffersFromSelected || selectionDiffersFromSession));

      if (shouldResetSession) {
        addToast('Switching repositories will start a new session.', 'info');
        clearSession();
      }

      setSelectedRepository(selection);
      setShowRepositorySelection(false);
      addToast('Repository selected successfully!', 'success');
    } catch (error) {
      console.error('Failed to select repository:', error);
      addToast('Failed to select repository', 'error');
    }
  };

  const handleRepositoryCancel = () => {
    setShowRepositorySelection(false);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  const removeContextCardHandler = (id: string) => {
    if (!activeSessionId) {
      addToast('No active session to remove context from', 'error');
      return;
    }

    void deleteContextCard(id)
      .then(() => addToast('Removed context card', 'info'))
      .catch(() => addToast('Failed to remove context card', 'error'));
  };


  const handleTabChange = (newTab: TabType) => {
    setActiveTab(newTab);
  };

  let tabContent = null;
  switch (currentTab) {
    case 'chat':
      tabContent = <Chat onShowError={addToast} />;
      break;
    case 'context':
      tabContent = (
        <ContextCards
          cards={contextCards}
          onRemoveCard={removeContextCardHandler}
        />
      );
      break;
    case 'ideas':
      tabContent = (
        <TrajectoryViewer
          sessionId={activeSessionId || undefined}
        />
      );
      break;
    case 'solve':
      tabContent = <SolveIssues />;
      break;
    default:
      tabContent = null;
      break;
  }

  return (
    <div className="min-h-screen bg-bg text-fg">
      <SessionOrchestrator />
      <div className="min-h-screen flex flex-col">
        <TopBar activeTab={currentTab} onTabChange={handleTabChange} />
        <main className="flex-1 overflow-hidden">
          {tabContent}
        </main>
      </div>

      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />

      {showRepositorySelection && (
        <RepositorySelectionToast
          isOpen={showRepositorySelection}
          onConfirm={handleRepositoryConfirm}
          onCancel={handleRepositoryCancel}
        />
      )}
    </div>
  );
}

function App() {
  const { isAuthenticated, sessionToken, initializeAuth } = useAuth();
  const clearSession = useSessionStore((state) => state.clearSession);
  const setSelectedRepository = useSessionStore((state) => state.setSelectedRepository);
  const previousTokenRef = useRef<string | null>(null);

  // Initialize authentication on app mount.
  useEffect(() => {
    console.log('[App] Initializing authentication on app mount');
    initializeAuth();
  }, [initializeAuth]);

  // Reset session state when the auth token changes to avoid stale data across logins or tabs.
  useEffect(() => {
    if (previousTokenRef.current === null) {
      previousTokenRef.current = sessionToken;
      return;
    }

    if (previousTokenRef.current !== sessionToken) {
      clearSession();
      setSelectedRepository(null);
      previousTokenRef.current = sessionToken;
    }
  }, [clearSession, sessionToken, setSelectedRepository]);

  // Auto-clear session store after 10 minutes of auth.
  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    const timer = setTimeout(() => {
      clearSession();
    }, 10 * 60 * 1000);

    return () => clearTimeout(timer);
  }, [isAuthenticated, clearSession]);

  // Handle session errors by clearing session and optionally logging out
  const handleSessionError = () => {
    console.log('[App] Handling session error - clearing session state');
    clearSession();
  };

  // Handle retry by re-initializing auth
  const handleRetry = () => {
    console.log('[App] Retrying after error - redirecting to login');
    window.location.href = '/auth/login';
  };

  return (
    <SessionErrorBoundary
      onSessionError={handleSessionError}
      onRetry={handleRetry}
    >
      <Routes>
        {/* Public routes */}
        <Route path="/auth/login" element={<LoginPage />} />
        <Route path="/auth/success" element={<AuthSuccess />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        
        {/* Protected routes */}
        <Route path="/" element={
          <ProtectedRoute>
            <AppContent />
          </ProtectedRoute>
        } />
        
        {/* Catch all route - redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SessionErrorBoundary>
  );
}

export default App;
