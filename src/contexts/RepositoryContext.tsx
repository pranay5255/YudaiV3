import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { SelectedRepository, GitHubRepository } from '../types';
import { useAuth } from './AuthContext';

interface RepositoryContextValue {
  selectedRepository: SelectedRepository | null;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  hasSelectedRepository: boolean;
  clearSelectedRepository: () => void;
  repositories: GitHubRepository[];
  loadUserRepositories: () => Promise<void>;
  isLoadingRepositories: boolean;
  syncRepositoryData: (repository: SelectedRepository) => Promise<void>;
}

const RepositoryContext = createContext<RepositoryContextValue | undefined>(undefined);

interface RepositoryProviderProps {
  children: ReactNode;
}

const STORAGE_KEY = 'yudai_selected_repository';
const API_BASE_URL = 'http://localhost:8000';

export const RepositoryProvider: React.FC<RepositoryProviderProps> = ({ children }) => {
  const { user, isAuthenticated, token } = useAuth();
  const [selectedRepository, setSelectedRepositoryState] = useState<SelectedRepository | null>(null);
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(false);

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

  // Load user repositories when authenticated
  useEffect(() => {
    if (isAuthenticated && user && token) {
      loadUserRepositories();
    }
  }, [isAuthenticated, user, token]);

  const getAuthHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  });

  const loadUserRepositories = async () => {
    if (!token) return;
    
    setIsLoadingRepositories(true);
    try {
      const response = await fetch(`${API_BASE_URL}/github/repositories`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch repositories: ${response.status}`);
      }

      const data = await response.json();
      setRepositories(data);
    } catch (error) {
      console.error('Failed to load repositories:', error);
    } finally {
      setIsLoadingRepositories(false);
    }
  };

  const syncRepositoryData = async (repository: SelectedRepository) => {
    if (!token) return;

    try {
      // Extract owner and repo name from full_name (format: "owner/repo")
      const [owner, repoName] = repository.repository.full_name.split('/');
      
      // 1. Fetch detailed repository information and update database
      const repoResponse = await fetch(
        `${API_BASE_URL}/github/repositories/${owner}/${repoName}`,
        { headers: getAuthHeaders() }
      );

      if (!repoResponse.ok) {
        throw new Error(`Failed to sync repository data: ${repoResponse.status}`);
      }

      // 2. Fetch repository issues and update database
      const issuesResponse = await fetch(
        `${API_BASE_URL}/github/repositories/${owner}/${repoName}/issues`,
        { headers: getAuthHeaders() }
      );

      // 3. Fetch repository pull requests and update database
      const pullsResponse = await fetch(
        `${API_BASE_URL}/github/repositories/${owner}/${repoName}/pulls`,
        { headers: getAuthHeaders() }
      );

      // 4. Update user's active repository in database
      await updateUserActiveRepository(repository);
      
      console.log('Repository data synchronized successfully');
    } catch (error) {
      console.error('Failed to sync repository data:', error);
      throw error;
    }
  };

  const updateUserActiveRepository = async (repository: SelectedRepository) => {
    if (!token || !user) return;

    try {
      // Update user's active repository in the backend
      const response = await fetch(`${API_BASE_URL}/auth/profile`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          active_repository: repository.repository.full_name
        }),
      });

      if (!response.ok) {
        console.warn('Failed to update user active repository in database');
      }
    } catch (error) {
      console.error('Failed to update user active repository:', error);
    }
  };

  // Enhanced setSelectedRepository with database sync
  const setSelectedRepository = async (repository: SelectedRepository | null) => {
    setSelectedRepositoryState(repository);
    
    if (repository) {
      try {
        // Save to localStorage
        localStorage.setItem(STORAGE_KEY, JSON.stringify(repository));
        
        // Sync repository data with database
        await syncRepositoryData(repository);
      } catch (error) {
        console.error('Failed to sync repository selection:', error);
        // Still keep the selection in state even if sync fails
      }
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  const clearSelectedRepository = () => {
    setSelectedRepositoryState(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  const hasSelectedRepository = selectedRepository !== null;

  const value: RepositoryContextValue = {
    selectedRepository,
    setSelectedRepository,
    hasSelectedRepository,
    clearSelectedRepository,
    repositories,
    loadUserRepositories,
    isLoadingRepositories,
    syncRepositoryData,
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