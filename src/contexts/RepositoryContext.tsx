import { createContext } from 'react';
import { SelectedRepository } from '../types';

interface RepositoryContextValue {
  selectedRepository: SelectedRepository | null;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  hasSelectedRepository: boolean;
  clearSelectedRepository: () => void;
}

export const RepositoryContext = createContext<RepositoryContextValue | undefined>(undefined);

// TODO: CREATE - Unified repository state management
export interface RepositoryState {
  selectedRepository: SelectedRepository | null;
  hasSelectedRepository: boolean;
  showRepositorySelection: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface RepositoryActions {
  setSelectedRepository: (repo: SelectedRepository | null) => void;
  setShowRepositorySelection: (show: boolean) => void;
  clearRepository: () => void;
  handleRepositoryConfirm: (selection: SelectedRepository) => Promise<void>;
  handleRepositoryCancel: () => void;
}

 