import React, { useState, ReactNode } from 'react';
import { RepositoryContext } from './RepositoryContext';
import { SelectedRepository } from '../types';

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

  // No longer loading from localStorage - managed in state only
  const setSelectedRepository = (repository: SelectedRepository | null) => {
    setSelectedRepositoryState(repository);
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