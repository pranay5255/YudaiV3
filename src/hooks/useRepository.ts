import { useCallback } from 'react';
import { useSessionStore } from '../stores/sessionStore';
import { GitHubRepository, SelectedRepository } from '../types';

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
    loadRepositories: () => {}, // TODO: Implement repository loading
    repositoryError,
  };
};

/**
 * Helper hook for repository selection operations
 */
export const useRepositorySelection = () => {
  const {
    selectedRepository,
    setSelectedRepository,
    availableRepositories,
    isLoadingRepositories,
    repositoryError
  } = useSessionStore();

  const hasSelectedRepository = !!selectedRepository;
  const clearSelectedRepository = useCallback(() => {
    setSelectedRepository(null);
  }, [setSelectedRepository]);

  const selectRepositoryWithBranch = useCallback((
    repository: GitHubRepository,
    branch: string
  ) => {
    const selection: SelectedRepository = {
      repository,
      branch
    };
    setSelectedRepository(selection);
  }, [setSelectedRepository]);

  const getRepositoryByName = useCallback((fullName: string): GitHubRepository | undefined => {
    return availableRepositories.find((repo: GitHubRepository) => repo.full_name === fullName);
  }, [availableRepositories]);

  const getCurrentRepositoryUrl = useCallback((): string | null => {
    if (!selectedRepository) return null;
    return selectedRepository.repository.html_url;
  }, [selectedRepository]);

  const getCurrentRepositoryInfo = useCallback(() => {
    if (!selectedRepository) return null;
    
    const [owner, name] = selectedRepository.repository.full_name.split('/');
    return {
      owner,
      name,
      branch: selectedRepository.branch,
      full_name: selectedRepository.repository.full_name,
      html_url: selectedRepository.repository.html_url
    };
  }, [selectedRepository]);

  return {
    selectedRepository,
    hasSelectedRepository,
    clearSelectedRepository,
    availableRepositories,
    isLoadingRepositories,
    repositoryError,
    selectRepositoryWithBranch,
    getRepositoryByName,
    getCurrentRepositoryUrl,
    getCurrentRepositoryInfo
  };
};