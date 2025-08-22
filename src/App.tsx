import { useState, useEffect } from 'react';
import { TopBar } from './components/TopBar';
import { Sidebar } from './components/Sidebar';
import { Chat } from './components/Chat';
import { FileDependencies } from './components/FileDependencies';
import { ContextCards } from './components/ContextCards';
import { IdeasToImplement } from './components/IdeasToImplement';
import { DiffModal } from './components/DiffModal';
import { DetailModal } from './components/DetailModal';
import { ToastContainer } from './components/Toast';
import { RepositorySelectionToast } from './components/RepositorySelectionToast';
import { ProtectedRoute } from './components/ProtectedRoute';
import { IdeaItem, Toast, ProgressStep, TabType, SelectedRepository, FileItem } from './types';
import { useAuth } from './hooks/useAuth';
import { useRepository } from './hooks/useRepository';
import { useSessionStore } from './stores/sessionStore';
import { useSession, useContextCards, useFileDependencies, useAddContextCard, useRemoveContextCard } from './hooks/useSessionQueries';
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
  
  // Zustand store for state management
  const { 
    activeSessionId, 
    activeTab, 
    setActiveTab,
    sidebarCollapsed, 
    setSidebarCollapsed
  } = useSessionStore();
  
  // React Query hooks for data fetching
  const { data: sessionData, isLoading: isSessionLoading } = useSession(activeSessionId || '');
  const { data: contextCards = [] } = useContextCards(activeSessionId || '');
  const { data: fileContext = [] } = useFileDependencies(activeSessionId || '');
  const addContextCardMutation = useAddContextCard();
  const removeContextCardMutation = useRemoveContextCard();
  
  // Local UI state
  const [currentStep] = useState<ProgressStep>('DAifu');
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isDiffModalOpen, setIsDiffModalOpen] = useState(false);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
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
        fileContextCount: fileContext.length,
        isLoading: isSessionLoading
      });
    }
  }, [activeSessionId, sessionData, contextCards, fileContext, isSessionLoading]);

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

  const addFileToContext = (file: FileItem) => {
    if (!activeSessionId) {
      addToast('Please select a repository to start a session first', 'error');
      return;
    }

    addContextCardMutation.mutate({
      sessionId: activeSessionId,
      card: {
        title: file.name || file.file_name || 'File',
        description: file.path || '',
        source: 'file-deps',
        tokens: file.tokens,
      }
    }, {
      onSuccess: () => addToast(`Added ${file.name || file.file_name} to context`, 'success'),
      onError: () => addToast('Failed to add file to context', 'error'),
    });
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

  const handleShowFileDetails = (file: FileItem) => {
    setSelectedFile(file);
    setIsDetailModalOpen(true);
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
    switch (activeTab) {
      case 'chat':
        return (
          <Chat
            onShowIssuePreview={handleShowIssuePreview}
            onShowError={addToast}
          />
        );
      case 'file-deps':
        return (
          <FileDependencies
            onShowDetails={handleShowFileDetails}
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
        activeTab={activeTab}
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

      <DetailModal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        file={selectedFile}
        onAddToContext={addFileToContext}
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
  return (
    <ProtectedRoute>
      <AppContent />
    </ProtectedRoute>
  );
}

export default App;