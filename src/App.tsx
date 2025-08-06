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
import { IdeaItem, Toast, ProgressStep, TabType, SelectedRepository } from './types';
import { FileItem } from './types/fileDependencies';
import { useAuth } from './hooks/useAuth';
import { useRepository } from './hooks/useRepository';
import { UserIssueResponse } from './types';
import { ChatContextMessage, FileContextItem } from './services/api';

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
  
  // Local UI state
  const [currentStep] = useState<ProgressStep>('DAifu');
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
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

  const addToContext = (content: string, source: 'chat' | 'file-deps' | 'upload' = 'chat') => {
    // Simplified context management - just log for now
    console.log('Adding to context:', { content, source });
  };

  const addFileToContext = (file: FileItem) => {
    // Simplified file context management
    console.log('Adding file to context:', file);
  };

  const removeContextCardHandler = (id: string) => {
    // Simplified context removal
    console.log('Removing context card:', id);
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
            onAddToContext={addToContext}
            onShowIssuePreview={handleShowIssuePreview}
          />
        );
      case 'file-deps':
        return (
          <FileDependencies
            onAddToContext={addFileToContext}
            onShowDetails={handleShowFileDetails}
          />
        );
      case 'context':
        return (
          <ContextCards
            cards={[]} // Empty array for now since we removed session management
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