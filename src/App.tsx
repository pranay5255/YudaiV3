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

  // Show repository selection after login if no repository is selected
  useEffect(() => {
    if (isAuthenticated && user && !hasSelectedRepository) {
      // Add a small delay to let the user see they've logged in
      const timer = setTimeout(() => {
        setShowRepositorySelection(true);
      }, 1000);
      
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, user, hasSelectedRepository]);

  // Repository selection handlers
  const handleRepositoryConfirm = (selection: SelectedRepository) => {
    setSelectedRepository(selection);
    setShowRepositorySelection(false);
    addToast('Repository selected successfully', 'success');
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
  const addToContext = (content: string, source: ContextCard['source'] = 'chat') => {
    const newCard: ContextCard = {
      id: Date.now().toString(),
      title: content.slice(0, 50) + (content.length > 50 ? '...' : ''),
      description: content.slice(0, 150) + (content.length > 150 ? '...' : ''),
      tokens: Math.floor(content.length * 0.75), // Rough token estimation
      source,
    };
    
    setContextCards(prev => [...prev, newCard]);
    addToast('Added to context successfully', 'success');
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

  const removeContextCard = (id: string) => {
    setContextCards(prev => prev.filter(card => card.id !== id));
    addToast('Removed from context', 'info');
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