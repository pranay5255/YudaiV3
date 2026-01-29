/**
 * React Query hooks for session management
 * Handles server state and caching for sessions, messages, context cards, and file dependencies
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSessionStore } from '../stores/sessionStore';
import { useAuthStore } from '../stores/authStore';
import { API, buildApiUrl } from '../config/api';
import { logger } from '../utils/logger';
import {
  ChatMessage,
  ContextCard,
  FileItem,
  CreateSessionMutationData,
  AddContextCardMutationData,
  RemoveContextCardMutationData,
  ContextCardMutationContext,
  SelectedRepository,
  SessionContext,
  StartSolveRequest,
  CreateIssueWithContextRequest,
  GitHubBranch,
  GitHubRepository,
} from '../types/sessionTypes';

// Helper function to get auth headers
const getAuthHeaders = (sessionToken?: string): HeadersInit => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = sessionToken || useAuthStore.getState().sessionToken;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

// Helper function to check if error is a session not found error
const isSessionNotFoundError = (error: unknown): boolean => {
  if (error instanceof Error) {
    return error.message.includes('Session not found') ||
           error.message.includes('404') ||
           error.message.includes('Not Found');
  }
  return false;
};

// Helper function to handle session errors by clearing invalid session
const handleSessionError = (error: unknown, sessionId: string, clearSession: () => void) => {
  if (isSessionNotFoundError(error)) {
    logger.warn(`[Session] Session ${sessionId} not found, clearing invalid session`);
    clearSession();
    return true; // Indicates session was cleared
  }
  return false; // Other type of error
};

// Rate limiting for session requests
const SESSION_REQUEST_COOLDOWN = 2000; // 2 seconds
const lastSessionRequestTimes = new Map<string, number>();

const shouldAllowSessionRequest = (sessionId: string): boolean => {
  const lastRequestTime = lastSessionRequestTimes.get(sessionId) || 0;
  const now = Date.now();
  const timeSinceLastRequest = now - lastRequestTime;
  
  if (timeSinceLastRequest < SESSION_REQUEST_COOLDOWN) {
    logger.info(`[Session] Rate limiting session request for ${sessionId}, last request was ${timeSinceLastRequest}ms ago`);
    return false;
  }
  
  lastSessionRequestTimes.set(sessionId, now);
  return true;
};

// Exponential backoff retry configuration
const getRetryDelay = (attemptIndex: number): number => {
  // Base delay of 1 second, exponentially increasing: 1s, 2s, 4s
  return Math.min(1000 * Math.pow(2, attemptIndex), 8000);
};

// Custom retry function with exponential backoff
const retryWithBackoff = (failureCount: number, error: unknown) => {
  // Don't retry session not found errors
  if (isSessionNotFoundError(error)) {
    return false;
  }
  
  // Don't retry authentication errors
  if (error instanceof Error && error.message.includes('401')) {
    return false;
  }
  
  // Don't retry too many times for 500 errors to prevent spam
  if (error instanceof Error && error.message.includes('500')) {
    return failureCount < 2; // Only retry once for server errors
  }
  
  // Retry up to 3 times for other errors (network issues, etc.)
  return failureCount < 3;
};

// Query keys for consistent cache management
export const QueryKeys = {
  sessions: ['sessions'] as const,
  session: (sessionId: string) => ['session', sessionId] as const,
  messages: (sessionId: string) => ['messages', sessionId] as const,
  contextCards: (sessionId: string) => ['context-cards', sessionId] as const,
  fileDependencies: (sessionId: string) => ['file-deps', sessionId] as const,
  repositories: ['repositories'] as const,
};



// ============================================================================
// SESSION QUERIES - Unified with Zustand Store
// ============================================================================

export const useSession = (sessionId: string) => {
  const { clearSession, loadSession } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useQuery({
    queryKey: QueryKeys.session(sessionId),
    queryFn: async (): Promise<SessionContext> => {
      if (!shouldAllowSessionRequest(sessionId)) {
        throw new Error('Rate limited: too many session requests');
      }

      try {
        // Use the unified sessionStore method instead of direct API call
        const success = await loadSession(sessionId);
        if (!success) {
          throw new Error('Failed to load session');
        }

        // Get the updated session context from store
        const { sessionContext } = useSessionStore.getState();
        if (!sessionContext) {
          throw new Error('Session context not available');
        }

        return sessionContext;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty state to prevent further queries
          return {
            session: null,
            messages: [],
            context_cards: [],
            file_embeddings_count: 0,
            user_issues: []
          };
        }
        throw error;
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
};

// ============================================================================
// CHAT MESSAGE QUERIES - Unified with Zustand Store
// ============================================================================

export const useChatMessages = (sessionId: string) => {
  const { clearSession, loadMessages } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useQuery({
    queryKey: QueryKeys.messages(sessionId),
    queryFn: async (): Promise<ChatMessage[]> => {
      if (!shouldAllowSessionRequest(`messages-${sessionId}`)) {
        throw new Error('Rate limited: too many message requests');
      }

      try {
        // Use the unified sessionStore method
        await loadMessages(sessionId);

        // Get messages from store
        const { messages } = useSessionStore.getState();
        return messages;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty messages
          return [];
        }
        throw error;
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false,
  });
};




// ============================================================================
// CONTEXT CARD QUERIES - Unified with Zustand Store
// ============================================================================

export const useContextCards = (sessionId: string) => {
  const { clearSession, loadContextCards } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useQuery({
    queryKey: QueryKeys.contextCards(sessionId),
    queryFn: async (): Promise<ContextCard[]> => {
      try {
        // Use the unified sessionStore method
        await loadContextCards(sessionId);

        // Get context cards from store
        const { contextCards } = useSessionStore.getState();
        return contextCards;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty context cards
          return [];
        }
        throw error;
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

// ============================================================================
// CONTEXT CARD MUTATIONS - Unified with Zustand Store
// ============================================================================

export const useAddContextCard = () => {
  const queryClient = useQueryClient();
  const { createContextCard } = useSessionStore();

  return useMutation({
    mutationFn: async ({ sessionId: _sessionId, card }: AddContextCardMutationData) => { // eslint-disable-line @typescript-eslint/no-unused-vars
      return await createContextCard(card);
    },
    onMutate: async ({ sessionId, card }): Promise<ContextCardMutationContext> => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: QueryKeys.contextCards(sessionId) });

      // Snapshot the previous value
      const previousCards = queryClient.getQueryData<ContextCard[]>(QueryKeys.contextCards(sessionId)) || [];

      // Optimistic update will be handled by Zustand store
      const optimisticCard: ContextCard = {
        id: Date.now().toString(),
        title: card.title,
        description: card.description,
        tokens: card.tokens,
        source: card.source,
      };

      return { previousCards, optimisticCard };
    },
    onError: (_err: Error, { sessionId }: AddContextCardMutationData, context?: ContextCardMutationContext) => {
      // Rollback handled by Zustand store
      if (context?.previousCards) {
        queryClient.setQueryData(QueryKeys.contextCards(sessionId), context.previousCards);
      }
    },
    onSettled: (_data: boolean | undefined, _error: Error | null, { sessionId }: AddContextCardMutationData) => {
      // Invalidate to sync with server state
      queryClient.invalidateQueries({ queryKey: QueryKeys.contextCards(sessionId) });
    },
  });
};

export const useRemoveContextCard = () => {
  const queryClient = useQueryClient();
  const { deleteContextCard } = useSessionStore();

  return useMutation({
    mutationFn: async ({ sessionId: _sessionId, cardId }: RemoveContextCardMutationData) => { // eslint-disable-line @typescript-eslint/no-unused-vars
      return await deleteContextCard(cardId);
    },
    onMutate: async ({ sessionId, cardId: _cardId }): Promise<ContextCardMutationContext> => { // eslint-disable-line @typescript-eslint/no-unused-vars
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: QueryKeys.contextCards(sessionId) });

      // Snapshot the previous value
      const previousCards = queryClient.getQueryData<ContextCard[]>(QueryKeys.contextCards(sessionId)) || [];

      return { previousCards };
    },
    onError: (_err: Error, { sessionId }: RemoveContextCardMutationData, context?: ContextCardMutationContext) => {
      // Rollback handled by Zustand store
      if (context?.previousCards) {
        queryClient.setQueryData(QueryKeys.contextCards(sessionId), context.previousCards);
      }
    },
    onSettled: (_data: boolean | undefined, _error: Error | null, { sessionId }: RemoveContextCardMutationData) => {
      // Invalidate to sync with server state
      queryClient.invalidateQueries({ queryKey: QueryKeys.contextCards(sessionId) });
    },
  });
};

// ============================================================================
// FILE DEPENDENCY QUERIES - Unified with Zustand Store
// ============================================================================

export const useFileDependencies = (sessionId: string) => {
  const { clearSession, loadFileDependencies } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useQuery({
    queryKey: QueryKeys.fileDependencies(sessionId),
    queryFn: async (): Promise<FileItem[]> => {
      try {
        // Use the unified sessionStore method
        await loadFileDependencies(sessionId);

        // Get file dependencies from store
        const { fileContext } = useSessionStore.getState();
        return fileContext;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty file dependencies
          return [];
        }
        throw error;
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};



// ============================================================================
// SESSION MANAGEMENT MUTATIONS - Unified with Zustand Store
// ============================================================================

export const useCreateSession = () => {
  const queryClient = useQueryClient();
  const { createSessionForRepository } = useSessionStore();

  return useMutation({
    mutationFn: async ({ repoOwner, repoName, repoBranch = 'main' }: CreateSessionMutationData) => {
      // Create a mock SelectedRepository for the sessionStore method
      const mockRepository = {
        repository: {
          id: 0,
          name: repoName,
          full_name: `${repoOwner}/${repoName}`,
          private: false,
          html_url: `https://github.com/${repoOwner}/${repoName}`,
          owner: { login: repoOwner, id: 0, avatar_url: '', html_url: `https://github.com/${repoOwner}` },
        },
        branch: repoBranch || 'main',
      };

      return await createSessionForRepository(mockRepository);
    },
    onSuccess: (sessionId: string | null) => {
      if (sessionId) {
        // Invalidate sessions list
        queryClient.invalidateQueries({ queryKey: QueryKeys.sessions });
      }
    },
  });
};

// ============================================================================
// REPOSITORY-BASED SESSION CREATION - Unified with Zustand Store
// ============================================================================

export const useCreateSessionFromRepository = () => {
  const { createSessionForRepository } = useSessionStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (repository: SelectedRepository) => {
      return await createSessionForRepository(repository);
    },
    onSuccess: (sessionId: string | null) => {
      if (sessionId) {
        // Invalidate sessions list
        queryClient.invalidateQueries({ queryKey: QueryKeys.sessions });
      }
    },
  });
};

// ============================================================================
// SESSION VALIDATION - Unified with Zustand Store
// ============================================================================

export const useEnsureSessionExists = () => {
  const { ensureSessionExists } = useSessionStore();

  return useMutation({
    mutationFn: async (sessionId: string) => {
      return await ensureSessionExists(sessionId);
    },
  });
};

// ============================================================================
// REPOSITORY QUERIES - Unified with Zustand Store
// ============================================================================

export const useRepositories = () => {
  const { availableRepositories, loadRepositories } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useQuery({
    queryKey: QueryKeys.repositories,
    queryFn: async (): Promise<GitHubRepository[]> => {
      await loadRepositories();
      return availableRepositories;
    },
    enabled: !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });
};

// ============================================================================
// REPOSITORY BRANCHES QUERY - Unified with Zustand Store
// ============================================================================

export const useRepositoryBranches = (owner: string, repo: string) => {
  const { loadRepositoryBranches } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useQuery({
    queryKey: ['repository-branches', owner, repo],
    queryFn: async (): Promise<GitHubBranch[]> => {
      if (!owner || !repo) {
        throw new Error('Owner and repo are required');
      }
      return await loadRepositoryBranches(owner, repo);
    },
    enabled: !!sessionToken && !!owner && !!repo,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 10 * 60 * 1000, // 10 minutes (branches don't change often)
    refetchOnWindowFocus: false,
  });
};

// ============================================================================
// ISSUE CREATION MUTATION - Consolidated under sessions context
// ============================================================================

export const useCreateIssueWithContext = () => {
  const { createIssueWithContext } = useSessionStore();

  return useMutation({
    mutationFn: async (request: CreateIssueWithContextRequest) => {
      return await createIssueWithContext(request);
    },
  });
};

// ============================================================================
// GITHUB ISSUE CREATION MUTATION - Consolidated under sessions context
// ============================================================================

export const useCreateGitHubIssueFromUserIssue = () => {
  const { createGitHubIssueFromUserIssue } = useSessionStore();

  return useMutation({
    mutationFn: async (issueId: string) => {
      return await createGitHubIssueFromUserIssue(issueId);
    },
  });
};

// ============================================================================
// SOLVER MUTATIONS - Consolidated under sessions context
// ============================================================================

export const useStartSolveSession = () => {
  const queryClient = useQueryClient();
  const { activeSessionId } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useMutation({
    mutationFn: async (request: StartSolveRequest) => {
      if (!activeSessionId || !sessionToken) {
        throw new Error('No active session or session token available');
      }

      const response = await fetch(buildApiUrl(API.SESSIONS.SOLVER.START, { sessionId: activeSessionId }), {
        method: 'POST',
        headers: getAuthHeaders(sessionToken),
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      return response.json();
    },
    onSuccess: () => {
      // Invalidate solver sessions list
      queryClient.invalidateQueries({ queryKey: ['solve-sessions', activeSessionId] });
    },
  });
};

export const useGetSolveSession = (solveSessionId: string) => {
  const { activeSessionId } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useQuery({
    queryKey: ['solve-session', activeSessionId, solveSessionId],
    queryFn: async () => {
      if (!activeSessionId || !sessionToken) {
        throw new Error('No active session or session token available');
      }

      const response = await fetch(buildApiUrl(API.SESSIONS.SOLVER.STATUS, {
        sessionId: activeSessionId,
        solveSessionId
      }), {
        method: 'GET',
        headers: getAuthHeaders(sessionToken),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      return response.json();
    },
    enabled: !!activeSessionId && !!sessionToken && !!solveSessionId,
  });
};


export const useCancelSolveSession = () => {
  const queryClient = useQueryClient();
  const { activeSessionId } = useSessionStore();
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useMutation({
    mutationFn: async (solveSessionId: string) => {
      if (!activeSessionId || !sessionToken) {
        throw new Error('No active session or session token available');
      }

      const response = await fetch(buildApiUrl(API.SESSIONS.SOLVER.CANCEL, {
        sessionId: activeSessionId,
        solveSessionId
      }), {
        method: 'POST',
        headers: getAuthHeaders(sessionToken),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      return response.json();
    },
    onSuccess: () => {
      // Invalidate solver sessions list
      queryClient.invalidateQueries({ queryKey: ['solve-sessions', activeSessionId] });
    },
  });
};
