import React, { useState, useEffect, ReactNode } from 'react';
import { RepositoryContext } from './RepositoryContext';
import { SelectedRepository } from '../types';
import { STORAGE_KEYS } from '../constants/storage';

interface RepositoryContextValue {
  selectedRepository: SelectedRepository | null;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  hasSelectedRepository: boolean;
  clearSelectedRepository: () => void;
}

interface RepositoryProviderProps {
  children: ReactNode;
}

export const RepositoryProvider: React.FC<RepositoryProviderProps> = ({ children }) => {
  const [selectedRepository, setSelectedRepositoryState] = useState<SelectedRepository | null>(null);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.SELECTED_REPOSITORY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setSelectedRepositoryState(parsed);
      }
    } catch (error) {
      console.error('Failed to load selected repository from localStorage:', error);
      localStorage.removeItem(STORAGE_KEYS.SELECTED_REPOSITORY);
    }
  }, []);

  // Save to localStorage whenever selection changes
  const setSelectedRepository = (repository: SelectedRepository | null) => {
    setSelectedRepositoryState(repository);
    
    if (repository) {
      try {
        localStorage.setItem(STORAGE_KEYS.SELECTED_REPOSITORY, JSON.stringify(repository));
      } catch (error) {
        console.error('Failed to save selected repository to localStorage:', error);
      }
    } else {
      localStorage.removeItem(STORAGE_KEYS.SELECTED_REPOSITORY);
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