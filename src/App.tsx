import { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { TopBar } from './components/TopBar';
import { Sidebar } from './components/Sidebar';
import { Chat } from './components/Chat';
import { ContextCards } from './components/ContextCards';
import { IdeasToImplement } from './components/IdeasToImplement';
import { DiffModal } from './components/DiffModal';
import { ToastContainer } from './components/Toast';
import { RepositorySelectionToast } from './components/RepositorySelectionToast';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SessionErrorBoundary } from './components/SessionErrorBoundary';
import { AuthSuccess } from './components/AuthSuccess';
import { AuthCallback } from './components/AuthCallback';
import { LoginPage } from './components/LoginPage';
import { IdeaItem, Toast, ProgressStep, TabType, SelectedRepository } from './types';
import { useAuth } from './hooks/useAuth';
import { useRepository } from './hooks/useRepository';
import { useSessionManagement } from './hooks/useSessionManagement';
import { useSession, useContextCards, useRemoveContextCard } from './hooks/useSessionQueries';
import { UserIssueResponse } from './types';
import { ChatContextMessage, FileContextItem } from './types/api';

// Interface for issue preview data (matching DiffModal expectations)
interface IssuePreviewData {
  title: string;
  body: string;
  labels: string[];
  assignees: string[];
  repository_info?: {
    owner: string;
    name: string;
    branch?: string;
  };
  metadata: {
    chat_messages_count: number;
    file_context_count: number;
    total_tokens: number;
    generated_at: string;
    generation_method: string;
  };
  userIssue?: UserIssueResponse;
  conversationContext: ChatContextMessage[];
  fileContext: FileContextItem[];
  canCreateGitHubIssue: boolean;
  repositoryInfo?: {
    owner: string;
    name: string;
    branch?: string;
  };
}

/**
 * Main App Content Component
 * Simplified state management without session context
 * Handles UI state and coordinates between different sections
 */
function AppContent() {
  // Auth and repository contexts
  const { user, isAuthenticated } = useAuth();
  const { setSelectedRepository, hasSelectedRepository } = useRepository();
  
  // Session management hook for state management
  const {
    activeSessionId,
    activeTab,
    setActiveTab,
    sidebarCollapsed,
    setSidebarCollapsed
  } = useSessionManagement();
  
  // React Query hooks for data fetching
  const { data: sessionData, isLoading: isSessionLoading } = useSession(activeSessionId || '');
  const { data: contextCards = [] } = useContextCards(activeSessionId || '');
  const removeContextCardMutation = useRemoveContextCard();

  const isValidTab = (tab: unknown): tab is TabType =>
    tab === 'chat' || tab === 'context' || tab === 'ideas';

  useEffect(() => {
    if (!isValidTab(activeTab)) {
      setActiveTab('chat');
    }
  }, [activeTab, setActiveTab]);

  const currentTab: TabType = isValidTab(activeTab) ? activeTab : 'chat';
  
  // Local UI state
  const [currentStep] = useState<ProgressStep>('DAifu');
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isDiffModalOpen, setIsDiffModalOpen] = useState(false);
  const [issuePreviewData, setIssuePreviewData] = useState<IssuePreviewData | undefined>(undefined);
  
  // Repository selection state - always show after login if no repository selected
  const [showRepositorySelection, setShowRepositorySelection] = useState(false);

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
  }, [isAuthenticated, user, activeSessionId, hasSelectedRepository]);

  // Debug log session and data state
  useEffect(() => {
    if (activeSessionId) {
      console.log('Session state:', {
        sessionId: activeSessionId,
        sessionData: sessionData ? 'loaded' : 'loading',
        contextCardsCount: contextCards.length,
        isLoading: isSessionLoading
      });
    }
  }, [activeSessionId, sessionData, contextCards, isSessionLoading]);

  const handleRepositoryConfirm = async (selection: SelectedRepository) => {
    try {
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

  const addToast = (message: string, type: Toast['type'] = 'info') => {
    const newToast: Toast = {
      id: Date.now().toString(),
      message,
      type,
    };
    setToasts(prev => [...prev, newToast]);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  const handleShowIssuePreview = (previewData: IssuePreviewData) => {
    setIssuePreviewData(previewData);
    setIsDiffModalOpen(true);
  };

  const removeContextCardHandler = (id: string) => {
    if (!activeSessionId) {
      addToast('No active session to remove context from', 'error');
      return;
    }

    removeContextCardMutation.mutate({
      sessionId: activeSessionId,
      cardId: id,
    }, {
      onSuccess: () => addToast('Removed context card', 'info'),
      onError: () => addToast('Failed to remove context card', 'error'),
    });
  };

  const handleCreateIdeaIssue = (idea: IdeaItem) => {
    // Simplified idea issue creation
    console.log('Creating idea issue:', idea);
    addToast('Idea issue creation not implemented yet', 'info');
  };

  const handleTabChange = (newTab: TabType) => {
    setActiveTab(newTab);
  };

  const renderTabContent = () => {
    switch (currentTab) {
      case 'chat':
        return (
          <Chat
            onShowIssuePreview={handleShowIssuePreview}
            onShowError={addToast}
          />
        );
      case 'context':
        return (
          <ContextCards
            cards={contextCards}
            onRemoveCard={removeContextCardHandler}
          />
        );
      case 'ideas':
        return (
          <IdeasToImplement
            onCreateIssue={handleCreateIdeaIssue}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen bg-bg text-fg">
      {/* Sidebar */}
      <Sidebar
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        activeTab={currentTab}
        onTabChange={handleTabChange}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <TopBar
          currentStep={currentStep}
        />

        {/* Main Content Area */}
        <main className="flex-1 overflow-hidden">
          {renderTabContent()}
        </main>
      </div>

      {/* Modals */}
      <DiffModal
        isOpen={isDiffModalOpen}
        onClose={() => setIsDiffModalOpen(false)}
        issuePreview={issuePreviewData}
      />

      {/* Toast Container */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />

      {/* Repository Selection Toast */}
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
  const { initializeAuth } = useAuth();
  
  // Initialize authentication on app mount - this must happen before ProtectedRoute
  useEffect(() => {
    console.log('[App] Initializing authentication on app mount');
    initializeAuth();
  }, [initializeAuth]);

  // Handle session errors by clearing session and optionally logging out
  const handleSessionError = () => {
    console.log('[App] Handling session error - clearing session state');
    // Don't automatically logout as user might still be authenticated
    // Just clear the invalid session
  };

  // Handle retry by re-initializing auth
  const handleRetry = () => {
    console.log('[App] Retrying after error - re-initializing auth');
    initializeAuth();
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
