/**
 * Zustand-first session hooks.
 * This module keeps a compatibility API but does not use React Query.
 */
import { useCallback, useEffect, useState } from 'react';
import { API, buildApiUrl } from '../config/api';
import { realtimeFeatureFlags } from '../config/realtimeFlags';
import { useAuthStore } from '../stores/authStore';
import { useSessionStore } from '../stores/sessionStore';
import type {
  AddContextCardMutationData,
  CancelSolveResponse,
  ChatMessage,
  ContextCard,
  CreateIssueWithContextRequest,
  CreateSessionMutationData,
  CreateGitHubIssueResponse,
  FileItem,
  GitHubBranch,
  GitHubRepository,
  IssueCreationResponse,
  RemoveContextCardMutationData,
  SelectedRepository,
  SessionContext,
  SolveStatusResponse,
  StartSolveRequest,
  StartSolveResponse,
} from '../types/sessionTypes';

type MutationOptions<TResult> = {
  onSuccess?: (data: TResult) => void;
  onError?: (error: Error) => void;
};

type SimpleMutation<TVariables, TResult> = {
  mutate: (variables: TVariables, options?: MutationOptions<TResult>) => void;
  mutateAsync: (variables: TVariables) => Promise<TResult>;
  isPending: boolean;
  error: Error | null;
  reset: () => void;
};

const getAuthHeaders = (sessionToken?: string): HeadersInit => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (sessionToken) {
    headers['Authorization'] = `Bearer ${sessionToken}`;
  }
  return headers;
};

const buildSessionTargetUrl = (
  endpoint: string,
  params: Record<string, string>
): string => {
  const resolved = buildApiUrl(endpoint, params);

  if (realtimeFeatureFlags.controllerProxyEnabled) {
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
    const parsed = new URL(resolved, origin);
    const match = parsed.pathname.match(/\/daifu\/sessions\/([^/]+)(\/.*)?$/);
    if (match) {
      const [, sessionId, rest] = match;
      return `/api/controller/proxy/sessions/${sessionId}/sessions/${sessionId}${rest || ''}${parsed.search}`;
    }
  }

  if (!realtimeFeatureFlags.tunnelModeEnabled) {
    return resolved;
  }

  const tunnelUrl =
    useSessionStore.getState().runtime?.tunnel_url ||
    useSessionStore.getState().currentSession?.tunnel_url;
  if (!tunnelUrl) {
    throw new Error('Sandbox tunnel is unavailable. Please create a new session.');
  }

  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
  const parsed = new URL(resolved, origin);
  const tunnelPath = parsed.pathname.replace(/^\/api\/daifu/, '');
  return `${tunnelUrl.replace(/\/$/, '')}${tunnelPath}${parsed.search}`;
};

const toError = (error: unknown, fallback: string): Error =>
  error instanceof Error ? error : new Error(fallback);

const useSimpleMutation = <TVariables, TResult>(
  action: (variables: TVariables) => Promise<TResult>
): SimpleMutation<TVariables, TResult> => {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const mutateAsync = useCallback(
    async (variables: TVariables) => {
      setIsPending(true);
      setError(null);
      try {
        return await action(variables);
      } catch (mutationError) {
        const normalized = toError(mutationError, 'Mutation failed');
        setError(normalized);
        throw normalized;
      } finally {
        setIsPending(false);
      }
    },
    [action]
  );

  const mutate = useCallback(
    (variables: TVariables, options?: MutationOptions<TResult>) => {
      void mutateAsync(variables)
        .then((result) => {
          options?.onSuccess?.(result);
        })
        .catch((mutationError) => {
          options?.onError?.(toError(mutationError, 'Mutation failed'));
        });
    },
    [mutateAsync]
  );

  const reset = useCallback(() => {
    setError(null);
    setIsPending(false);
  }, []);

  return { mutate, mutateAsync, isPending, error, reset };
};

const useAsyncLoader = <T>(
  enabled: boolean,
  loader: () => Promise<T>
): { isLoading: boolean; error: Error | null; refetch: () => Promise<T> } => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      return await loader();
    } catch (loadError) {
      const normalized = toError(loadError, 'Failed to load data');
      setError(normalized);
      throw normalized;
    } finally {
      setIsLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void refetch().catch(() => {
      // Errors are surfaced through `error` state.
    });
  }, [enabled, refetch]);

  return { isLoading, error, refetch };
};

// Kept for compatibility with old call-sites.
export const QueryKeys = {
  sessions: ['sessions'] as const,
  session: (sessionId: string) => ['session', sessionId] as const,
  messages: (sessionId: string) => ['messages', sessionId] as const,
  contextCards: (sessionId: string) => ['context-cards', sessionId] as const,
  fileDependencies: (sessionId: string) => ['file-deps', sessionId] as const,
  repositories: ['repositories'] as const,
};

export const useSession = (sessionId: string) => {
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const loadSession = useSessionStore((state) => state.loadSession);
  const sessionContext = useSessionStore((state) => state.sessionContext);

  const { isLoading, error, refetch } = useAsyncLoader(
    Boolean(sessionId && sessionToken),
    async () => {
      await loadSession(sessionId);
      const context = useSessionStore.getState().sessionContext;
      if (!context) {
        throw new Error('Session context not available');
      }
      return context;
    }
  );

  return {
    data: sessionContext as SessionContext | null,
    isLoading,
    error,
    refetch,
  };
};

export const useChatMessages = (sessionId: string) => {
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const loadMessages = useSessionStore((state) => state.loadMessages);
  const messages = useSessionStore((state) => state.messages);

  const { isLoading, error, refetch } = useAsyncLoader(
    Boolean(sessionId && sessionToken),
    async () => loadMessages(sessionId)
  );

  return {
    data: messages as ChatMessage[],
    isLoading,
    error,
    refetch,
  };
};

export const useContextCards = (sessionId: string) => {
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const loadContextCards = useSessionStore((state) => state.loadContextCards);
  const contextCards = useSessionStore((state) => state.contextCards);

  const { isLoading, error, refetch } = useAsyncLoader(
    Boolean(sessionId && sessionToken),
    async () => loadContextCards(sessionId)
  );

  return {
    data: contextCards as ContextCard[],
    isLoading,
    error,
    refetch,
  };
};

export const useFileDependencies = (sessionId: string) => {
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const loadFileDependencies = useSessionStore((state) => state.loadFileDependencies);
  const fileContext = useSessionStore((state) => state.fileContext);

  const { isLoading, error, refetch } = useAsyncLoader(
    Boolean(sessionId && sessionToken),
    async () => loadFileDependencies(sessionId)
  );

  return {
    data: fileContext as FileItem[],
    isLoading,
    error,
    refetch,
  };
};

export const useAddContextCard = () => {
  const createContextCard = useSessionStore((state) => state.createContextCard);
  return useSimpleMutation(async ({ card }: AddContextCardMutationData) => {
    await createContextCard(card);
    return true;
  });
};

export const useRemoveContextCard = () => {
  const deleteContextCard = useSessionStore((state) => state.deleteContextCard);
  return useSimpleMutation(async ({ cardId }: RemoveContextCardMutationData) => {
    await deleteContextCard(cardId);
    return true;
  });
};

export const useCreateSession = () => {
  const createSessionForRepository = useSessionStore((state) => state.createSessionForRepository);

  return useSimpleMutation(async ({ repoOwner, repoName, repoBranch = 'main' }: CreateSessionMutationData) => {
    const mockRepository: SelectedRepository = {
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

    return createSessionForRepository(mockRepository);
  });
};

export const useCreateSessionFromRepository = () => {
  const createSessionForRepository = useSessionStore((state) => state.createSessionForRepository);
  return useSimpleMutation((repository: SelectedRepository) => createSessionForRepository(repository));
};

export const useEnsureSessionExists = () => {
  const ensureSessionExists = useSessionStore((state) => state.ensureSessionExists);
  return useSimpleMutation(async (sessionId: string) => {
    await ensureSessionExists(sessionId);
    return true;
  });
};

export const useRepositories = () => {
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const availableRepositories = useSessionStore((state) => state.availableRepositories);
  const loadRepositories = useSessionStore((state) => state.loadRepositories);

  const { isLoading, error, refetch } = useAsyncLoader(
    Boolean(sessionToken),
    async () => loadRepositories()
  );

  return {
    data: availableRepositories as GitHubRepository[],
    isLoading,
    error,
    refetch,
  };
};

export const useRepositoryBranches = (owner: string, repo: string) => {
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const loadRepositoryBranches = useSessionStore((state) => state.loadRepositoryBranches);
  const [branches, setBranches] = useState<GitHubBranch[]>([]);

  const { isLoading, error, refetch } = useAsyncLoader(
    Boolean(sessionToken && owner && repo),
    async () => {
      const loaded = await loadRepositoryBranches(owner, repo);
      setBranches(loaded);
      return loaded;
    }
  );

  return {
    data: branches,
    isLoading,
    error,
    refetch,
  };
};

export const useCreateIssueWithContext = () => {
  const createIssueWithContext = useSessionStore((state) => state.createIssueWithContext);
  return useSimpleMutation((request: CreateIssueWithContextRequest) =>
    createIssueWithContext(request)
  );
};

export const useCreateGitHubIssueFromUserIssue = () => {
  const createGitHubIssueFromUserIssue = useSessionStore((state) => state.createGitHubIssueFromUserIssue);
  return useSimpleMutation((issueId: string) =>
    createGitHubIssueFromUserIssue(issueId)
  );
};

export const useStartSolveSession = () => {
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useSimpleMutation(async (request: StartSolveRequest) => {
    if (!activeSessionId || !sessionToken) {
      throw new Error('No active session or session token available');
    }

    const startUrl = buildSessionTargetUrl(API.SESSIONS.SOLVER.START, { sessionId: activeSessionId });
    const response = await fetch(startUrl, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json() as Promise<StartSolveResponse>;
  });
};

export const useGetSolveSession = (solveSessionId: string) => {
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const [data, setData] = useState<SolveStatusResponse | null>(null);

  const { isLoading, error, refetch } = useAsyncLoader(
    Boolean(activeSessionId && sessionToken && solveSessionId),
    async () => {
      if (!activeSessionId || !sessionToken) {
        throw new Error('No active session or session token available');
      }

      const statusUrl = buildSessionTargetUrl(API.SESSIONS.SOLVER.STATUS, {
        sessionId: activeSessionId,
        solveSessionId,
      });
      const response = await fetch(statusUrl, {
        method: 'GET',
        headers: getAuthHeaders(sessionToken),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const payload = await response.json() as SolveStatusResponse;
      setData(payload);
      return payload;
    }
  );

  return { data, isLoading, error, refetch };
};

export const useCancelSolveSession = () => {
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const sessionToken = useAuthStore((state) => state.sessionToken);

  return useSimpleMutation(async (solveSessionId: string) => {
    if (!activeSessionId || !sessionToken) {
      throw new Error('No active session or session token available');
    }

    const cancelUrl = buildSessionTargetUrl(API.SESSIONS.SOLVER.CANCEL, {
      sessionId: activeSessionId,
      solveSessionId,
    });
    const response = await fetch(cancelUrl, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json() as Promise<CancelSolveResponse>;
  });
};

// Backward-compatible aliases.
export type {
  ContextCard,
  FileItem,
  GitHubBranch,
  GitHubRepository,
  SessionContext,
  ChatMessage,
  CreateIssueWithContextRequest,
  IssueCreationResponse,
  CreateGitHubIssueResponse,
};
