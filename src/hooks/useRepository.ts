import { useSessionStore } from '../stores/sessionStore';
import { useShallow } from 'zustand/react/shallow';

/**
 * Custom hook to access repository state and management functions
 */
export const useRepository = () => {
  const {
    selectedRepository,
    setSelectedRepository,
    availableRepositories,
    isLoadingRepositories,
    repositoryError
  } = useSessionStore(
    useShallow((state) => ({
      selectedRepository: state.selectedRepository,
      setSelectedRepository: state.setSelectedRepository,
      availableRepositories: state.availableRepositories,
      isLoadingRepositories: state.isLoadingRepositories,
      repositoryError: state.repositoryError,
    }))
  );

  return {
    selectedRepository,
    setSelectedRepository,
    hasSelectedRepository: !!selectedRepository,
    clearSelectedRepository: () => setSelectedRepository(null),
    availableRepositories,
    isLoadingRepositories,
    repositoryError,
  };
};
