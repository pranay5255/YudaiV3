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
import { SessionProvider } from './contexts/SessionContext';
import { useSession } from './hooks/useSession';
import { IdeaItem, Toast, ProgressStep, TabType, SelectedRepository } from './types';
import { UnifiedContextCard, UnifiedFileEmbedding, ContextCardSource, UnifiedMessage } from './types/unifiedState';
import { useAuth } from './hooks/useAuth';
import { useRepository } from './hooks/useRepository';
import { useSessionHelpers } from './hooks/useSessionHelpers';
import { ApiService, ChatContextMessage, FileContextItem, UserIssueResponse } from './services/api';

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
  const { sessionState, tabState, connectionStatus, dispatch } = useSession();
  const {
      createSession,
      addContextCard,
      removeContextCard,
      addFileContext,
      removeFileContext,
      // createIssue // This will be redefined locally for now
    } = useSessionHelpers();

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
  const [selectedFile, setSelectedFile] = useState<UnifiedFileEmbedding | null>(null);
  const [issuePreviewData, setIssuePreviewData] = useState<IssuePreviewData | undefined>(undefined);
  
  // Repository selection state
  const [showRepositorySelection, setShowRepositorySelection] = useState(false);

  // Show repository selection after login if no repository is selected
  useEffect(() => {
    if (isAuthenticated && user && !hasSelectedRepository && !sessionState.session_id) {
      // Add a small delay to let the user see they've logged in
      const timer = setTimeout(() => {
        setShowRepositorySelection(true);
      }, 1000);
      
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, user, hasSelectedRepository, sessionState.session_id]);
  
  // Real-time repository info updates
  useEffect(() => {
    if (sessionState.repository) {
      // Update repository context when session repository changes
      // This logic will now be handled inside the helper hook or context if needed
      // updateRepositoryInfo(sessionState.repository);
    }
  }, [sessionState.repository]);

  /**
   * Handles repository selection and creates a new session
   * Integrates with SessionContext for unified state management
   */
  const handleRepositoryConfirm = async (selection: SelectedRepository) => {
    setSelectedRepository(selection);
    setShowRepositorySelection(false);
    try {
        await createSession(
            selection.repository.full_name.split('/')[0],
            selection.repository.name,
            selection.branch
        );
        addToast('Session created successfully!', 'success');
    } catch (error) {
        addToast('Failed to create session.', 'error');
        console.error(error);
    }
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
  const addToContext = (content: string, source: ContextCardSource = ContextCardSource.CHAT) => {
    const newCard: UnifiedContextCard = {
      id: Date.now().toString(),
      session_id: sessionState.session_id || '',
      title: content.slice(0, 50) + (content.length > 50 ? '...' : ''),
      description: content.slice(0, 150) + (content.length > 150 ? '...' : ''),
      content: content,
      tokens: Math.floor(content.length * 0.75), // Rough token estimation
      source,
      created_at: new Date().toISOString()
    };
    
    addContextCard(newCard);
    addToast('Added to context successfully', 'success');
  };

  /**
   * Adds a file to context cards
   * @param file - The file item to add to context
   */
  const addFileToContext = (file: UnifiedFileEmbedding) => {
    const newCard: UnifiedContextCard = {
      id: Date.now().toString(),
      session_id: sessionState.session_id || '',
      title: file.file_name,
      description: `${file.file_type} file with ${file.tokens} tokens`,
      content: '', // File content is not stored in the card
      tokens: file.tokens,
      source: ContextCardSource.FILE,
      created_at: new Date().toISOString()
    };
    
    addContextCard(newCard);
    addFileContext(file);
    addToast(`Added ${file.file_name} to context`, 'success');
  };

  /**
   * Removes a context card by ID
   * @param id - The ID of the context card to remove
   */
  const removeContextCardHandler = (id: string) => {
    removeContextCard(id);
    // Also remove from file context if it's a file-deps item
    const card = sessionState.context_cards.find((c: UnifiedContextCard) => c.id === id);
    if (card && card.source === ContextCardSource.FILE) {
      const fileEmbedding = sessionState.file_embeddings.find((f: UnifiedFileEmbedding) => f.file_name === card.title);
      if (fileEmbedding) {
        removeFileContext(fileEmbedding.id);
      }
    }
    addToast('Removed from context', 'info');
  };

  /**
   * Modal handlers for file details and issue creation
   */
  const handleShowFileDetails = (file: UnifiedFileEmbedding) => {
    setSelectedFile(file);
    setIsDetailModalOpen(true);
  };

  /**
   * Enhanced issue creation using SessionContext
   * Creates issue with current session context including messages and files
   */
  // This function is defined locally as it interacts heavily with UI state (toasts, modals)
  const handleCreateIssue = async () => {
    if (!sessionState.session_id) {
        addToast('Cannot create an issue without an active session.', 'error');
        return;
    }
    try {
      addToast('Creating issue with session context...', 'info');
      setCurrentStep('Architect');
      
      // This is a placeholder for the actual request model for creating an issue
      const issueRequest = {
          title: `Issue from Session ${sessionState.session_id}`,
          description: 'This issue was generated from the current session context.',
          session_id: sessionState.session_id
          // In a real scenario, you'd pass the full context here
      };

      // Assume ApiService has a method to create a user issue
      // Since it's not defined in the provided file, we'll mock it for now
      const issue: UserIssueResponse = await ApiService.createUserIssue(issueRequest);
      
      addToast('Issue created successfully!', 'success');
      
      // Show issue preview
      handleShowIssuePreview({
        title: issue.title,
        body: issue.issue_text_raw,
        labels: [],
        assignees: [],
        metadata: {
          chat_messages_count: sessionState.messages.length,
          file_context_count: sessionState.file_embeddings.length,
          total_tokens: sessionState.statistics.total_tokens,
          generated_at: new Date().toISOString(),
          generation_method: 'session-based',
        },
        userIssue: issue,
        conversationContext: sessionState.messages.map((msg: UnifiedMessage) => ({
          id: msg.id,
          content: msg.content,
          isCode: msg.is_code,
          timestamp: msg.timestamp,
        })),
        fileContext: sessionState.file_embeddings.map((file: UnifiedFileEmbedding) => ({
          id: file.id.toString(),
          name: file.file_name,
          type: 'INTERNAL',
          tokens: file.tokens,
          category: 'INTERNAL',
          path: file.file_path,
        })),
        canCreateGitHubIssue: !!sessionState.repository,
        repositoryInfo: sessionState.repository ? {
          owner: sessionState.repository.owner,
          name: sessionState.repository.name,
          branch: sessionState.repository.branch
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
    dispatch({ type: 'SET_ACTIVE_TAB', payload: newTab });
  };
  
  /**
   * Refreshes specific tab content without affecting session state
   * @param tab - The tab to refresh
   */
  // Tab refresh handler - available for future use
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleTabRefresh = (tab: TabType) => {
    dispatch({ type: 'REFRESH_TAB', payload: tab });
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
            key={`chat-${refreshKey}-${sessionState.messages.length}`}
            onAddToContext={addToContext}
            onCreateIssue={handleCreateIssue}
            contextCards={sessionState.context_cards}
            fileContext={sessionState.file_embeddings.map((f: UnifiedFileEmbedding) => ({...f, id: f.id.toString(), name: f.file_name, type: 'INTERNAL', Category: 'INTERNAL', path: f.file_path, isDirectory: false}))}
            onShowIssuePreview={handleShowIssuePreview}
          />
        );
      case 'file-deps':
          return (
            <FileDependencies 
              key={`file-deps-${refreshKey}`}
              onAddToContext={addFileToContext}
              onShowDetails={(file) => handleShowFileDetails(file as unknown as UnifiedFileEmbedding)}
            />
          );
      case 'context':
        return (
          <ContextCards 
            key={`context-${refreshKey}`}
            cards={sessionState.context_cards.map((c: UnifiedContextCard) => ({...c, source: c.source || ContextCardSource.CHAT}))}
            onRemoveCard={removeContextCardHandler}
            onCreateIssue={handleCreateIssue}
            onShowIssuePreview={handleShowIssuePreview}
            repositoryInfo={sessionState.repository ? {
              owner: sessionState.repository.owner,
              name: sessionState.repository.name,
              branch: sessionState.repository.branch
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
        {connectionStatus !== 'connected' && sessionState.session_id && (
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
        <div className={`flex ${connectionStatus !== 'connected' && sessionState.session_id ? 'h-[calc(100vh-96px)] mt-8' : 'h-[calc(100vh-56px)]'}`}>
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
            <div>ID: {sessionState.session_id?.slice(-8) || 'None'}</div>
            <div>Messages: {sessionState.messages.length}</div>
            <div>Context: {sessionState.context_cards.length}</div>
            <div>Files: {sessionState.file_embeddings.length}</div>
            <div>Tokens: {sessionState.statistics.total_tokens.toLocaleString()}</div>
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