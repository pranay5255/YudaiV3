import React, { createContext, useState, useCallback, useEffect } from 'react';
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
  SessionResponse as ApiSessionResponse,
  SessionContextResponse as ApiSessionContextResponse,
  FileEmbeddingResponse as ApiFileEmbeddingResponse,
  ContextCardResponse as ApiContextCardResponse
} from '../types/api';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export { SessionContext };

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
  
  // Core session state
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



  // Chat message management functions
  const addChatMessage = useCallback((message: ChatMessageAPI) => {
    setSessionState(prev => {
      const newMessages = [...prev.messages, message];
      
      // Persist messages to localStorage
      if (prev.sessionId) {
        localStorage.setItem(`chat_messages_${prev.sessionId}`, JSON.stringify(newMessages));
      }
      
      return {
        ...prev,
        messages: newMessages,
        lastUpdated: new Date(),
      };
    });
  }, []);

  const updateChatMessage = useCallback((messageId: string, updates: Partial<ChatMessageAPI>) => {
    setSessionState(prev => {
      const newMessages = prev.messages.map(msg => 
        msg.message_id === messageId ? { ...msg, ...updates } : msg
      );
      
      // Persist updated messages to localStorage
      if (prev.sessionId) {
        localStorage.setItem(`chat_messages_${prev.sessionId}`, JSON.stringify(newMessages));
      }
      
      return {
        ...prev,
        messages: newMessages,
        lastUpdated: new Date(),
      };
    });
  }, []);

  const clearChatMessages = useCallback(() => {
    setSessionState(prev => {
      // Clear messages from localStorage
      if (prev.sessionId) {
        localStorage.removeItem(`chat_messages_${prev.sessionId}`);
      }
      
      return {
        ...prev,
        messages: [],
        lastUpdated: new Date(),
      };
    });
  }, []);

  const loadChatMessages = useCallback((sessionId: string) => {
    try {
      const storedMessages = localStorage.getItem(`chat_messages_${sessionId}`);
      if (storedMessages) {
        const messages: ChatMessageAPI[] = JSON.parse(storedMessages);
        console.log('[SessionProvider] Loaded chat messages from storage:', messages.length);
        return messages;
      }
    } catch (error) {
      console.error('[SessionProvider] Failed to load chat messages:', error);
    }
    return [];
  }, []);

  // Session management functions
  const createSession = useCallback(async (repoOwner: string, repoName: string, repoBranch: string = 'main') => {
    try {
      console.log('[SessionProvider] Creating session for:', { repoOwner, repoName, repoBranch });
      
      setSessionState(prev => ({ ...prev, isLoading: true, error: null }));
      
      // Create session via API
      const session: ApiSessionResponse = await api.createSession({
        repo_owner: repoOwner,
        repo_name: repoName,
        repo_branch: repoBranch,
        title: `Chat - ${repoOwner}/${repoName}`,
      });
      
      // Update session state with new session
      setSessionState(prev => ({
        ...prev,
        sessionId: session.session_id,
        session: {
          id: session.id,
          session_id: session.session_id,
          title: session.title,
          description: session.description,
          repo_owner: session.repo_owner,
          repo_name: session.repo_name,
          repo_branch: session.repo_branch,
          repo_context: session.repo_context,
          is_active: session.is_active,
          total_messages: session.total_messages,
          total_tokens: session.total_tokens,
          created_at: session.created_at,
          updated_at: session.updated_at,
          last_activity: session.last_activity,
        },
        repositoryInfo: {
          owner: repoOwner,
          name: repoName,
          branch: repoBranch,
          full_name: `${repoOwner}/${repoName}`,
          html_url: `https://github.com/${repoOwner}/${repoName}`,
        },
        isLoading: false,
        lastUpdated: new Date(),
        connectionStatus: 'connected',
      }));
      
      console.log('[SessionProvider] Session created successfully:', session.session_id);
      
      // Persist session ID in localStorage
      localStorage.setItem('current_session_id', session.session_id);
      
    } catch (error) {
      console.error('[SessionProvider] Failed to create session:', error);
      setSessionState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to create session',
        isLoading: false,
        connectionStatus: 'disconnected',
      }));
      throw error;
    }
  }, [api]);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      console.log('[SessionProvider] Loading session:', sessionId);
      
      setSessionState(prev => ({ ...prev, isLoading: true, error: null }));
      
      const context: ApiSessionContextResponse = await api.getSessionContext(sessionId);
      
      // Load context cards for this session
      const contextCardsResponse: ApiContextCardResponse[] = await api.getContextCards(sessionId);
      
      // Transform context cards from API response to frontend format
      const transformedContextCards: ContextCard[] = contextCardsResponse.map((card: ApiContextCardResponse) => ({
        id: card.id.toString(),
        title: card.title,
        description: card.description,
        tokens: card.tokens,
        source: card.source as 'chat' | 'file-deps' | 'upload',
      }));
      
      // Transform file context from API response to frontend format
      const transformedFileContext: FileItem[] = [];
      if (context.file_embeddings && context.file_embeddings.length > 0) {
        transformedFileContext.push(...context.file_embeddings.map((embedding: ApiFileEmbeddingResponse) => ({
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

        tokens: msg.tokens,
        model_used: msg.model_used,
        processing_time: msg.processing_time,
        context_cards: msg.context_cards,
        referenced_files: msg.referenced_files,
        error_message: msg.error_message,
        created_at: msg.created_at,
        updated_at: msg.updated_at,
      }));
      
      // Load any additional chat messages from localStorage
      const localMessages = loadChatMessages(sessionId);
      
      // Combine messages, avoiding duplicates by message_id
      const messageMap = new Map<string, ChatMessageAPI>();
      
      // Add API messages first (they take precedence)
      transformedMessages.forEach(msg => {
        messageMap.set(msg.message_id, msg);
      });
      
      // Add local messages only if they don't exist in API messages
      localMessages.forEach(msg => {
        if (!messageMap.has(msg.message_id)) {
          messageMap.set(msg.message_id, msg);
        }
      });
      
      const allMessages = Array.from(messageMap.values());
      
      setSessionState(prev => ({
        ...prev,
        sessionId: context.session.session_id,
        session: {
          id: context.session.id,
          session_id: context.session.session_id,
          title: context.session.title,
          description: context.session.description,
          repo_owner: context.session.repo_owner,
          repo_name: context.session.repo_name,
          repo_branch: context.session.repo_branch,
          repo_context: context.session.repo_context,
          is_active: context.session.is_active,
          total_messages: context.session.total_messages,
          total_tokens: context.session.total_tokens,
          created_at: context.session.created_at,
          updated_at: context.session.updated_at,
          last_activity: context.session.last_activity,
        },
        messages: allMessages,
        contextCards: transformedContextCards,
        userIssues: context.user_issues || [],
        statistics: context.statistics || prev.statistics,
        repositoryInfo: context.repository_info || null,
        fileContext: transformedFileContext,
        totalTokens: context.statistics?.total_tokens || 0,
        isLoading: false,
        lastUpdated: new Date(),
        connectionStatus: 'connected',
      }));
      
      console.log('[SessionProvider] Session loaded successfully with', allMessages.length, 'messages');
      
    } catch (error) {
      console.error('[SessionProvider] Failed to load session:', error);
      setSessionState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to load session',
        isLoading: false,
        connectionStatus: 'disconnected',
      }));
      throw error;
    }
  }, [api, loadChatMessages]);

  const clearSession = useCallback(() => {
    console.log('[SessionProvider] Clearing session');
    
    setSessionState(prev => {
      // Clear chat messages from localStorage if session exists
      if (prev.sessionId) {
        localStorage.removeItem(`chat_messages_${prev.sessionId}`);
      }
      
      return {
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
        connectionStatus: 'disconnected',
      };
    });
    
    // Clear session ID from localStorage
    localStorage.removeItem('current_session_id');
  }, []);

  // Repository management functions
  const setSelectedRepository = useCallback((repository: SelectedRepository | null) => {
    console.log('[SessionProvider] Setting selected repository:', repository);
    
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
    
    console.log('[SessionProvider] Loading repositories');
    
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
      console.log('[SessionProvider] Repositories loaded:', transformedRepos.length);
      
    } catch (error) {
      console.error('[SessionProvider] Failed to load repositories:', error);
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
        console.log('[SessionProvider] Restored repository from storage:', parsed);
      } catch (error) {
        console.warn('[SessionProvider] Failed to parse stored repository:', error);
        sessionStorage.removeItem('selected_repository');
      }
    }
  }, [isAuthenticated]);

  // Restore session from localStorage on mount
  useEffect(() => {
    const storedSessionId = localStorage.getItem('current_session_id');
    if (storedSessionId && isAuthenticated) {
      console.log('[SessionProvider] Restoring session from storage:', storedSessionId);
      loadSession(storedSessionId).catch(error => {
        console.warn('[SessionProvider] Failed to restore session:', error);
        localStorage.removeItem('current_session_id');
      });
    }
  }, [isAuthenticated, loadSession]);

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
    // Add these new functions
    addChatMessage,
    updateChatMessage,
    clearChatMessages,
    loadChatMessages,
  };

  return (
    <SessionContext.Provider value={contextValue}>
      {children}
    </SessionContext.Provider>
  );
};