import { useSessionStore } from '../stores/sessionStore';

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
  } = useSessionStore();

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

