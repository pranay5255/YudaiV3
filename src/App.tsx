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
import { SessionProvider, useSession, useConnectionStatus } from './contexts/SessionContext';
import { ContextCard, FileItem, IdeaItem, Toast, ProgressStep, TabType, SelectedRepository } from './types';
import { useAuth } from './hooks/useAuth';
import { useRepository } from './hooks/useRepository';
import { ChatContextMessage, FileContextItem, UserIssueResponse } from './services/api';

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
 * Uses SessionContext for comprehensive state management
 * Handles UI state and coordinates between different sections
 */
function AppContent() {
  // Session context provides all application state
  const {
    sessionState,
    tabState,
    addContextCard,
    removeContextCard,
    addFileContext,
    removeFileContext,
    createIssue,
    setActiveTab,
    refreshTab,
    updateRepositoryInfo
  } = useSession();
  
  const connectionStatus = useConnectionStatus();
  
  // Auth and repository contexts
  const { user, isAuthenticated } = useAuth();
  const { setSelectedRepository, hasSelectedRepository } = useRepository();
  
  // Local UI state (not session-related)
  const [currentStep, setCurrentStep] = useState<ProgressStep>('DAifu');
  const [errorStep] = useState<ProgressStep | undefined>();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isDiffModalOpen, setIsDiffModalOpen] = useState(false);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [issuePreviewData, setIssuePreviewData] = useState<IssuePreviewData | undefined>(undefined);
  
  // Repository selection state
  const [showRepositorySelection, setShowRepositorySelection] = useState(false);

  // Show repository selection after login if no repository is selected
  useEffect(() => {
    if (isAuthenticated && user && !hasSelectedRepository && !sessionState.sessionId) {
      // Add a small delay to let the user see they've logged in
      const timer = setTimeout(() => {
        setShowRepositorySelection(true);
      }, 1000);
      
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, user, hasSelectedRepository, sessionState.sessionId]);
  
  // Real-time repository info updates
  useEffect(() => {
    if (sessionState.repositoryInfo) {
      // Update repository context when session repository changes
      updateRepositoryInfo(sessionState.repositoryInfo);
    }
  }, [sessionState.repositoryInfo, updateRepositoryInfo]);

  /**
   * Handles repository selection and creates a new session
   * Integrates with SessionContext for unified state management
   */
  const handleRepositoryConfirm = (selection: SelectedRepository) => {
    setSelectedRepository(selection);
    setShowRepositorySelection(false);
    addToast('Repository selected successfully', 'success');
    
    // The SessionContext will automatically create a session via useEffect
    // when selectedRepository changes
  };

  const handleRepositoryCancel = () => {
    setShowRepositorySelection(false);
  };

  // Toast management
  const addToast = (message: string, type: Toast['type'] = 'info') => {
    const toast: Toast = {
      id: Date.now().toString(),
      message,
      type,
    };
    setToasts(prev => [...prev, toast]);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  // Handle issue preview from Chat component
  const handleShowIssuePreview = (previewData: IssuePreviewData) => {
    setIssuePreviewData(previewData);
    setIsDiffModalOpen(true);
    addToast('Issue preview generated successfully!', 'success');
  };


  /**
   * Context management functions - now integrated with SessionContext
   * These functions maintain backward compatibility while using session state
   */
  
  /**
   * Adds chat content to context cards
   * @param content - The content to add to context
   * @param source - The source of the content (chat, file-deps, upload)
   */
  const addToContext = (content: string, source: ContextCard['source'] = 'chat') => {
    const newCard: ContextCard = {
      id: Date.now().toString(),
      title: content.slice(0, 50) + (content.length > 50 ? '...' : ''),
      description: content.slice(0, 150) + (content.length > 150 ? '...' : ''),
      tokens: Math.floor(content.length * 0.75), // Rough token estimation
      source,
    };
    
    addContextCard(newCard);
    addToast('Added to context successfully', 'success');
  };

  /**
   * Adds a file to context cards
   * @param file - The file item to add to context
   */
  const addFileToContext = (file: FileItem) => {
    const newCard: ContextCard = {
      id: Date.now().toString(),
      title: file.name,
      description: `${file.type} file with ${file.tokens} tokens`,
      tokens: file.tokens,
      source: 'file-deps',
    };
    
    addContextCard(newCard);
    addFileContext(file);
    addToast(`Added ${file.name} to context`, 'success');
  };

  /**
   * Removes a context card by ID
   * @param id - The ID of the context card to remove
   */
  const removeContextCardHandler = (id: string) => {
    removeContextCard(id);
    // Also remove from file context if it's a file-deps item
    const card = sessionState.contextCards.find(c => c.id === id);
    if (card && card.source === 'file-deps') {
      removeFileContext(id);
    }
    addToast('Removed from context', 'info');
  };

  /**
   * Modal handlers for file details and issue creation
   */
  const handleShowFileDetails = (file: FileItem) => {
    setSelectedFile(file);
    setIsDetailModalOpen(true);
  };

  /**
   * Enhanced issue creation using SessionContext
   * Creates issue with current session context including messages and files
   */
  const handleCreateIssue = async () => {
    try {
      addToast('Creating issue with session context...', 'info');
      setCurrentStep('Architect');
      
      const issue = await createIssue(
        `Issue from Session ${sessionState.sessionId}`,
        'This issue was generated from the current session context.'
      );
      
      addToast('Issue created successfully!', 'success');
      
      // Show issue preview
      handleShowIssuePreview({
        title: issue.title,
        body: issue.issue_text_raw,
        labels: [],
        assignees: [],
        metadata: {
          chat_messages_count: sessionState.messages.length,
          file_context_count: sessionState.fileContext.length,
          total_tokens: sessionState.totalTokens,
          generated_at: new Date().toISOString(),
          generation_method: 'session-based',
        },
        userIssue: issue,
        conversationContext: sessionState.messages.map(msg => ({
          id: msg.id,
          content: msg.content,
          isCode: msg.is_code,
          timestamp: msg.timestamp,
        })),
        fileContext: sessionState.fileContext.map(file => ({
          id: file.id,
          name: file.name,
          type: file.type,
          tokens: file.tokens,
          category: file.Category,
          path: file.path,
        })),
        canCreateGitHubIssue: !!sessionState.repositoryInfo,
        repositoryInfo: sessionState.repositoryInfo ? {
          owner: sessionState.repositoryInfo.owner,
          name: sessionState.repositoryInfo.name,
          branch: sessionState.repositoryInfo.branch
        } : undefined,
      });
    } catch (error) {
      addToast('Failed to create issue', 'error');
      console.error('Failed to create issue:', error);
    }
  };

  /**
   * Creates issue from idea items
   * @param idea - The idea item to create an issue from
   */
  const handleCreateIdeaIssue = (idea: IdeaItem) => {
    addToast(`Creating issue for: ${idea.title}`, 'info');
    handleCreateIssue();
  };

  /**
   * Tab management with session-aware refresh
   * Maintains tab state while preserving session context
   */
  const handleTabChange = (newTab: TabType) => {
    setActiveTab(newTab);
    // Don't reset tab content - maintain state across tab switches
  };
  
  /**
   * Refreshes specific tab content without affecting session state
   * @param tab - The tab to refresh
   */
  const handleTabRefresh = (tab: TabType) => {
    refreshTab(tab);
    addToast(`Refreshed ${tab} tab`, 'info');
  };
  
  // Use handleTabRefresh on double-click for tabs (future enhancement)
  // This function is available for future tab refresh functionality

  /**
   * Renders tab content with session-aware props
   * All components receive session state and refresh keys for proper updates
   */
  const renderTabContent = () => {
    const currentTab = tabState.activeTab;
    const refreshKey = tabState.refreshKeys[currentTab];
    
    switch (currentTab) {
      case 'chat':
        return (
          <Chat 
            key={`chat-${refreshKey}-${sessionState.messageRefreshKey}`}
            onAddToContext={addToContext}
            onCreateIssue={handleCreateIssue}
            contextCards={sessionState.contextCards}
            fileContext={sessionState.fileContext}
            onShowIssuePreview={handleShowIssuePreview}
          />
        );
      case 'file-deps':
          return (
            <FileDependencies 
              key={`file-deps-${refreshKey}`}
              onAddToContext={addFileToContext}
              onShowDetails={handleShowFileDetails}
            />
          );
      case 'context':
        return (
          <ContextCards 
            key={`context-${refreshKey}`}
            cards={sessionState.contextCards}
            onRemoveCard={removeContextCardHandler}
            onCreateIssue={handleCreateIssue}
            onShowIssuePreview={handleShowIssuePreview}
            repositoryInfo={sessionState.repositoryInfo ? {
              owner: sessionState.repositoryInfo.owner,
              name: sessionState.repositoryInfo.name,
              branch: sessionState.repositoryInfo.branch
            } : undefined}
          />
        );
      case 'ideas':
        return (
          <IdeasToImplement 
            key={`ideas-${refreshKey}`}
            onCreateIssue={handleCreateIdeaIssue}
          />
        );
      default:
        return null;
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-bg text-fg font-sans">
        {/* Connection Status Indicator */}
        {connectionStatus !== 'connected' && sessionState.sessionId && (
          <div className={`fixed top-0 left-0 right-0 z-50 p-2 text-center text-sm ${
            connectionStatus === 'reconnecting' ? 'bg-yellow-600' : 'bg-red-600'
          } text-white`}>
            {connectionStatus === 'reconnecting' ? 'Reconnecting...' : 'Connection lost - Some features may be limited'}
          </div>
        )}
        
        {/* Top Bar with Session Info */}
        <TopBar 
          currentStep={currentStep} 
          errorStep={errorStep}
        />
        
        {/* Main Layout */}
        <div className={`flex ${connectionStatus !== 'connected' && sessionState.sessionId ? 'h-[calc(100vh-96px)] mt-8' : 'h-[calc(100vh-56px)]'}`}>
          {/* Sidebar with Session State */}
          <Sidebar 
            activeTab={tabState.activeTab}
            onTabChange={handleTabChange}
            isCollapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          />
          
          {/* Main Content */}
          <main className="flex-1 p-6">
            <div className="h-full bg-bg/80 backdrop-blur rounded-2xl shadow-md border border-zinc-800/50 overflow-hidden">
              {renderTabContent()}
            </div>
          </main>
        </div>

        {/* Modals */}
        <DiffModal 
          isOpen={isDiffModalOpen}
          onClose={() => {
            setIsDiffModalOpen(false);
            setIssuePreviewData(undefined);
          }}
          issuePreview={issuePreviewData}
        />
        
        <DetailModal 
          isOpen={isDetailModalOpen}
          onClose={() => setIsDetailModalOpen(false)}
          file={selectedFile}
          onAddToContext={addFileToContext}
        />

        {/* Repository Selection Toast with Session Integration */}
        <RepositorySelectionToast
          isOpen={showRepositorySelection}
          onConfirm={handleRepositoryConfirm}
          onCancel={handleRepositoryCancel}
        />

        {/* Toast Container */}
        <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
        
        {/* Session Debug Info (Development Only) */}
        {process.env.NODE_ENV === 'development' && (
          <div className="fixed bottom-4 right-4 bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-xs font-mono max-w-sm">
            <div className="text-zinc-400 mb-2">Session Debug</div>
            <div>ID: {sessionState.sessionId?.slice(-8) || 'None'}</div>
            <div>Messages: {sessionState.messages.length}</div>
            <div>Context: {sessionState.contextCards.length}</div>
            <div>Files: {sessionState.fileContext.length}</div>
            <div>Tokens: {sessionState.totalTokens.toLocaleString()}</div>
            <div className={`${
              connectionStatus === 'connected' ? 'text-green-400' : 
              connectionStatus === 'reconnecting' ? 'text-yellow-400' : 'text-red-400'
            }`}>
              Status: {connectionStatus}
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}

/**
 * Main App Component with SessionProvider
 * Wraps the entire application with session context
 */
function App() {
  return (
    <SessionProvider>
      <AppContent />
    </SessionProvider>
  );
}

export default App;