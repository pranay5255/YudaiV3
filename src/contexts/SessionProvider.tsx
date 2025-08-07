import React, { createContext, useState, useCallback, useEffect, useContext } from 'react';
import { 
  SessionState, 
  GitHubRepository, 
  SelectedRepository, 
  SessionContextValue,
  UnifiedSessionState,
  TabState,
  ContextCard,
  FileItem,
  ChatMessageAPI
} from '../types';
import type { 
  GitHubRepositoryAPI, 
  SessionResponse, 
  SessionContextResponse,
  FileEmbeddingResponse
} from '../types/api';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export { SessionContext };

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};


interface SessionProviderProps {
  children: React.ReactNode;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const api = useApi();
  const { isAuthenticated } = useAuth();
  
  // Repository state
  const [selectedRepository, setSelectedRepositoryState] = useState<SelectedRepository | null>(null);
  const [availableRepositories, setAvailableRepositories] = useState<GitHubRepository[]>([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(false);
  const [repositoryError, setRepositoryError] = useState<string | null>(null);
  
  // Tab state
  const [tabState] = useState<TabState>({
    activeTab: 'chat',
    refreshKeys: {
      chat: 0,
      'file-deps': 0,
      context: 0,
      ideas: 0,
    },
    tabHistory: ['chat'],
  });
  
  const [sessionState, setSessionState] = useState<SessionState>({
    sessionId: null,
    session: null,
    repository: null,
    branch: 'main',
    repositoryInfo: null,
    messages: [],
    isLoadingMessages: false,
    messageRefreshKey: 0,
    contextCards: [],
    fileContext: [],
    totalTokens: 0,
    userIssues: [],
    currentIssue: null,
    agentStatus: { type: 'daifu', status: 'idle' },
    agentHistory: [],
    statistics: {
      total_messages: 0,
      total_tokens: 0,
      total_cost: 0,
      session_duration: 0,
    },
    isLoading: false,
    error: null,
    lastUpdated: new Date(),
    connectionStatus: 'disconnected',
  });

  const createSession = useCallback(async (repoOwner: string, repoName: string, repoBranch: string = 'main') => {
    try {
      setSessionState(prev => ({ ...prev, isLoading: true, error: null }));
      
      const session: SessionResponse = await api.createSession({
        repo_owner: repoOwner,
        repo_name: repoName,
        repo_branch: repoBranch,
        title: `Chat - ${repoOwner}/${repoName}`,
      });
      
      setSessionState(prev => ({
        ...prev,
        sessionId: session.session_id,
        session: session,
        repositoryInfo: {
          owner: repoOwner,
          name: repoName,
          branch: repoBranch,
          full_name: `${repoOwner}/${repoName}`,
          html_url: `https://github.com/${repoOwner}/${repoName}`,
        },
        isLoading: false,
        lastUpdated: new Date(),
      }));
    } catch (error) {
      setSessionState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to create session',
        isLoading: false,
      }));
      throw error;
    }
  }, [api]);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      setSessionState(prev => ({ ...prev, isLoading: true, error: null }));
      
      const context: SessionContextResponse = await api.getSessionContext(sessionId);
      
      // Transform context cards from API response to frontend format
      const transformedContextCards: ContextCard[] = [];
      if (context.context_cards && context.context_cards.length > 0) {
        // TODO: Load actual context cards when API is ready
        // For now, create placeholder context cards
        transformedContextCards.push({
          id: 'placeholder-1',
          title: 'Session Context',
          description: 'Context from session loading',
          tokens: 100,
          source: 'chat',
        });
      }
      
      // Transform file context from API response to frontend format
      const transformedFileContext: FileItem[] = [];
      if (context.file_embeddings && context.file_embeddings.length > 0) {
        transformedFileContext.push(...context.file_embeddings.map((embedding: FileEmbeddingResponse) => ({
          id: embedding.id.toString(),
          name: embedding.file_name,
          path: embedding.file_path,
          type: 'INTERNAL' as const,
          tokens: embedding.tokens,
          category: embedding.file_type,
          created_at: embedding.created_at,
        })));
      }
      
      // Transform messages to match ChatMessageAPI type
      const transformedMessages: ChatMessageAPI[] = (context.messages || []).map(msg => ({
        id: msg.id,
        message_id: msg.message_id,
        message_text: msg.message_text,
        sender_type: msg.sender_type as 'user' | 'assistant' | 'system',
        role: msg.role as 'user' | 'assistant' | 'system',
        is_code: msg.is_code,
        tokens: msg.tokens,
        model_used: msg.model_used,
        processing_time: msg.processing_time,
        context_cards: msg.context_cards,
        referenced_files: msg.referenced_files,
        error_message: msg.error_message,
        created_at: msg.created_at,
        updated_at: msg.updated_at,
      }));
      
      setSessionState(prev => ({
        ...prev,
        sessionId: context.session.session_id,
        session: context.session,
        messages: transformedMessages,
        contextCards: transformedContextCards,
        userIssues: context.user_issues || [],
        statistics: context.statistics || prev.statistics,
        repositoryInfo: context.repository_info || null,
        fileContext: transformedFileContext,
        totalTokens: context.statistics?.total_tokens || 0,
        isLoading: false,
        lastUpdated: new Date(),
      }));
    } catch (error) {
      setSessionState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to load session',
        isLoading: false,
      }));
      throw error;
    }
  }, [api]);

  const clearSession = useCallback(() => {
    setSessionState(prev => ({
      ...prev,
      sessionId: null,
      session: null,
      repository: null,
      repositoryInfo: null,
      messages: [],
      contextCards: [],
      fileContext: [],
      totalTokens: 0,
      userIssues: [],
      currentIssue: null,
      agentStatus: { type: 'daifu', status: 'idle' },
      agentHistory: [],
      statistics: {
        total_messages: 0,
        total_tokens: 0,
        total_cost: 0,
        session_duration: 0,
      },
      error: null,
      lastUpdated: new Date(),
    }));
  }, []);

  // Repository management functions
  const setSelectedRepository = useCallback((repository: SelectedRepository | null) => {
    setSelectedRepositoryState(repository);
    // Persist selected repository in sessionStorage for the current session
    if (repository) {
      sessionStorage.setItem('selected_repository', JSON.stringify(repository));
    } else {
      sessionStorage.removeItem('selected_repository');
    }
  }, []);

  const clearSelectedRepository = useCallback(() => {
    setSelectedRepository(null);
  }, [setSelectedRepository]);

  const loadRepositories = useCallback(async () => {
    if (!isAuthenticated) return;
    
    setIsLoadingRepositories(true);
    setRepositoryError(null);
    
    try {
      const repositories: GitHubRepositoryAPI[] = await api.getUserRepositories();
      // Transform API response to match frontend GitHubRepository type
      const transformedRepos: GitHubRepository[] = repositories.map(repo => ({
        id: repo.id,
        name: repo.name,
        full_name: repo.full_name,
        description: repo.description || '',
        private: repo.private,
        html_url: repo.html_url,
        default_branch: repo.default_branch,
        owner: {
          login: repo.full_name.split('/')[0],
          id: repo.id, // Using repo id as fallback
        },
      }));
      setAvailableRepositories(transformedRepos);
    } catch (error) {
      console.error('Failed to load repositories:', error);
      setRepositoryError(error instanceof Error ? error.message : 'Failed to load repositories');
      setAvailableRepositories([]);
    } finally {
      setIsLoadingRepositories(false);
    }
  }, [api, isAuthenticated]);

  // Load repositories when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      loadRepositories();
    } else {
      setAvailableRepositories([]);
      setSelectedRepository(null);
    }
  }, [isAuthenticated, loadRepositories, setSelectedRepository]);

  // Restore selected repository from sessionStorage on mount
  useEffect(() => {
    const storedRepository = sessionStorage.getItem('selected_repository');
    if (storedRepository && isAuthenticated) {
      try {
        const parsed = JSON.parse(storedRepository);
        setSelectedRepositoryState(parsed);
      } catch (error) {
        console.warn('Failed to parse stored repository:', error);
        sessionStorage.removeItem('selected_repository');
      }
    }
  }, [isAuthenticated]);

  const hasSelectedRepository = selectedRepository !== null;

  // Create unified session state
  const unifiedSessionState: UnifiedSessionState = {
    ...sessionState,
    tabState,
    selectedRepository,
    availableRepositories,
    isLoadingRepositories,
    repositoryError,
  };

  const contextValue: SessionContextValue = {
    ...unifiedSessionState,
    createSession,
    loadSession,
    clearSession,
    setSelectedRepository,
    hasSelectedRepository,
    clearSelectedRepository,
    loadRepositories,
  };

  return (
    <SessionContext.Provider value={contextValue}>
      {children}
    </SessionContext.Provider>
  );
};