import { useContext } from 'react';
import { RepositoryContext } from '../contexts/RepositoryContext';
import { SelectedRepository } from '../types';

interface RepositoryContextValue {
  selectedRepository: SelectedRepository | null;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  hasSelectedRepository: boolean;
  clearSelectedRepository: () => void;
}

export const useRepository = (): RepositoryContextValue => {
  const context = useContext(RepositoryContext);
  if (context === undefined) {
    throw new Error('useRepository must be used within a RepositoryProvider');
  }
  return context;
}; 