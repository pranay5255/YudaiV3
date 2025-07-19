import React, { useState, useEffect } from 'react';
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
import { ContextCard, FileItem, IdeaItem, Toast, ProgressStep, TabType, SelectedRepository } from './types';
import { useAuth } from './contexts/AuthContext';
import { useRepository } from './contexts/RepositoryContext';
import { ApiService } from './services/api';

function App() {
  // Auth and repository contexts
  const { user, isAuthenticated } = useAuth();
  const { setSelectedRepository, hasSelectedRepository } = useRepository();
  
  // State management
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  const [currentStep, setCurrentStep] = useState<ProgressStep>('DAifu');
  const [errorStep] = useState<ProgressStep | undefined>();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  const [contextCards, setContextCards] = useState<ContextCard[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  
  const [isDiffModalOpen, setIsDiffModalOpen] = useState(false);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  
  // Repository selection state
  const [showRepositorySelection, setShowRepositorySelection] = useState(false);

  // Load context cards when user is authenticated
  useEffect(() => {
    if (isAuthenticated && user) {
      loadContextCards();
    }
  }, [isAuthenticated, user]);

  // Show repository selection after login if no repository is selected
  useEffect(() => {
    if (isAuthenticated && user && !hasSelectedRepository) {
      // Welcome the user
      addToast(`Welcome back, ${user.github_username}! 🐱`, 'success');
      
      // Add a small delay to let the user see they've logged in
      const timer = setTimeout(() => {
        setShowRepositorySelection(true);
      }, 1000);
      
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, user, hasSelectedRepository]);

  // Load context cards from API
  const loadContextCards = async () => {
    try {
      const cards = await ApiService.getContextCards();
      const transformedCards: ContextCard[] = cards.map(card => ({
        id: card.id,
        title: card.title,
        description: card.description,
        tokens: card.tokens,
        source: card.source,
      }));
      setContextCards(transformedCards);
    } catch (error) {
      console.error('Failed to load context cards:', error);
    }
  };

  // Repository selection handlers
  const handleRepositoryConfirm = async (selection: SelectedRepository) => {
    try {
      await setSelectedRepository(selection);
      setShowRepositorySelection(false);
      addToast('Repository selected and synchronized successfully', 'success');
    } catch (error) {
      console.error('Failed to sync repository:', error);
      addToast('Repository selected but sync failed', 'error');
      setShowRepositorySelection(false);
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

  // Context management
  const addToContext = async (content: string, source: ContextCard['source'] = 'chat') => {
    try {
      // Create context card via API
      const contextCard = await ApiService.createContextCard({
        title: content.slice(0, 50) + (content.length > 50 ? '...' : ''),
        description: content.slice(0, 150) + (content.length > 150 ? '...' : ''),
        content,
        source,
      });

      // Add to local state
      const newCard: ContextCard = {
        id: contextCard.id,
        title: contextCard.title,
        description: contextCard.description,
        tokens: contextCard.tokens,
        source: contextCard.source,
      };
      
      setContextCards(prev => [...prev, newCard]);
      addToast('Added to context successfully', 'success');
    } catch (error) {
      console.error('Failed to add context card:', error);
      addToast('Failed to add to context', 'error');
    }
  };

  const addFileToContext = (file: FileItem) => {
    const newCard: ContextCard = {
      id: Date.now().toString(),
      title: file.name,
      description: `${file.type} file with ${file.tokens} tokens`,
      tokens: file.tokens,
      source: 'file-deps',
    };
    
    setContextCards(prev => [...prev, newCard]);
    addToast(`Added ${file.name} to context`, 'success');
  };

  const removeContextCard = async (id: string) => {
    try {
      await ApiService.deleteContextCard(id);
      setContextCards(prev => prev.filter(card => card.id !== id));
      addToast('Removed from context', 'info');
    } catch (error) {
      console.error('Failed to remove context card:', error);
      addToast('Failed to remove from context', 'error');
    }
  };

  // Modal handlers
  const handleShowFileDetails = (file: FileItem) => {
    setSelectedFile(file);
    setIsDetailModalOpen(true);
  };

  const handleCreateIssue = () => {
    addToast('Creating GitHub issue...', 'info');
    setCurrentStep('Architect');
    
    setTimeout(() => {
      setCurrentStep('Test-Writer');
      setTimeout(() => {
        setCurrentStep('Coder');
        setIsDiffModalOpen(true);
        addToast('Pull request ready for review!', 'success');
      }, 2000);
    }, 1500);
  };

  const handleCreateIdeaIssue = (idea: IdeaItem) => {
    addToast(`Creating issue for: ${idea.title}`, 'info');
    handleCreateIssue();
  };

  // Render tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case 'chat':
        return <Chat onAddToContext={addToContext} />;
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
            cards={contextCards}
            onRemoveCard={removeContextCard}
            onCreateIssue={handleCreateIssue}
          />
        );
      case 'ideas':
        return <IdeasToImplement onCreateIssue={handleCreateIdeaIssue} />;
      default:
        return null;
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-bg text-fg font-sans">
        {/* Top Bar */}
        <TopBar currentStep={currentStep} errorStep={errorStep} />
        
        {/* Main Layout */}
        <div className="flex h-[calc(100vh-56px)]">
          {/* Sidebar */}
          <Sidebar 
            activeTab={activeTab}
            onTabChange={setActiveTab}
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
          onClose={() => setIsDiffModalOpen(false)}
        />
        
        <DetailModal 
          isOpen={isDetailModalOpen}
          onClose={() => setIsDetailModalOpen(false)}
          file={selectedFile}
          onAddToContext={addFileToContext}
        />

        {/* Repository Selection Toast */}
        <RepositorySelectionToast
          isOpen={showRepositorySelection}
          onConfirm={handleRepositoryConfirm}
          onCancel={handleRepositoryCancel}
        />

        {/* Toast Container */}
        <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
      </div>
    </ProtectedRoute>
  );
}

export default App;