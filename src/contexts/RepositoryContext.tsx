import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { SelectedRepository } from '../types';

interface RepositoryContextValue {
  selectedRepository: SelectedRepository | null;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  hasSelectedRepository: boolean;
  clearSelectedRepository: () => void;
}

const RepositoryContext = createContext<RepositoryContextValue | undefined>(undefined);

interface RepositoryProviderProps {
  children: ReactNode;
}

const STORAGE_KEY = 'yudai_selected_repository';

export const RepositoryProvider: React.FC<RepositoryProviderProps> = ({ children }) => {
  const [selectedRepository, setSelectedRepositoryState] = useState<SelectedRepository | null>(null);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setSelectedRepositoryState(parsed);
      }
    } catch (error) {
      console.error('Failed to load selected repository from localStorage:', error);
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Save to localStorage whenever selection changes
  const setSelectedRepository = (repository: SelectedRepository | null) => {
    setSelectedRepositoryState(repository);
    
    if (repository) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(repository));
      } catch (error) {
        console.error('Failed to save selected repository to localStorage:', error);
      }
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  const clearSelectedRepository = () => {
    setSelectedRepository(null);
  };

  const hasSelectedRepository = selectedRepository !== null;

  const value: RepositoryContextValue = {
    selectedRepository,
    setSelectedRepository,
    hasSelectedRepository,
    clearSelectedRepository,
  };

  return (
    <RepositoryContext.Provider value={value}>
      {children}
    </RepositoryContext.Provider>
  );
};

export const useRepository = (): RepositoryContextValue => {
  const context = useContext(RepositoryContext);
  if (context === undefined) {
    throw new Error('useRepository must be used within a RepositoryProvider');
  }
  return context;
}; 