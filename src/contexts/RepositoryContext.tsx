import { createContext } from 'react';
import { SelectedRepository } from '../types';

interface RepositoryContextValue {
  selectedRepository: SelectedRepository | null;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  hasSelectedRepository: boolean;
  clearSelectedRepository: () => void;
}

export const RepositoryContext = createContext<RepositoryContextValue | undefined>(undefined);

 