import { useCallback } from 'react';
import { useSession } from '../contexts/SessionProvider';
import { GitHubRepository, SelectedRepository } from '../types';

/**
 * Custom hook to access repository state and management functions
 * Must be used within a SessionProvider
 */
export const useRepository = () => {
  const session = useSession();
  return {
    selectedRepository: session.selectedRepository,
    setSelectedRepository: session.setSelectedRepository,
    hasSelectedRepository: session.hasSelectedRepository,
    clearSelectedRepository: session.clearSelectedRepository,
    availableRepositories: session.availableRepositories,
    isLoadingRepositories: session.isLoadingRepositories,
    loadRepositories: session.loadRepositories,
    repositoryError: session.repositoryError,
  };
};

/**
 * Helper hook for repository selection operations
 */
export const useRepositorySelection = () => {
  const {
    selectedRepository,
    setSelectedRepository,
    hasSelectedRepository,
    clearSelectedRepository,
    availableRepositories,
    isLoadingRepositories,
    repositoryError
  } = useRepository();

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
    return availableRepositories.find(repo => repo.full_name === fullName);
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