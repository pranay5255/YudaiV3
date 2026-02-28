import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import {
  SelectedRepository,
  TabType,
  ContextCard,
  FileItem,
  ChatMessage,
  GitHubRepository,
  UserIssue,
  Session,
  SessionContext,
  UpdateSessionRequest,
  CreateContextCardRequest,
  CreateFileEmbeddingRequest,
  ChatRequest,
  CreateIssueWithContextRequest,
  IssueCreationResponse,
  AgentStatus,
  GitHubBranch,
  ChatResponse,
  CreateGitHubIssueResponse,
  SessionRuntimeInfo,
} from '../types/sessionTypes';
import { API, buildApiUrl } from '../config/api';
import { realtimeFeatureFlags } from '../config/realtimeFlags';
import { buildControllerSessionTargetUrl } from '../utils/realtimeRouting';
import { useAuthStore } from './authStore';

export type SessionStatus =
  | 'no_repo'
  | 'awaiting_session'
  | 'creating_session'
  | 'ready'
  | 'sending'
  | 'error';

export class AppError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'AppError';
    this.code = code;
  }
}

const toAppError = (
  error: unknown,
  code: string,
  fallbackMessage: string
): AppError => {
  if (error instanceof AppError) {
    return error;
  }
  if (error instanceof Error) {
    return new AppError(code, error.message || fallbackMessage);
  }
  return new AppError(code, fallbackMessage);
};

const SESSION_AUTH_EXPIRED_MESSAGE =
  'Session expired. Sign in again to reconnect to sandbox.';
const SESSION_TERMINATED_MESSAGE =
  'This session sandbox has already been terminated.';

// Helper function to get auth headers
const getAuthHeaders = (sessionToken?: string): HeadersInit => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = sessionToken || useAuthStore.getState().sessionToken;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

// Helper function to handle API responses
const handleApiResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    let errorCode = `HTTP_${response.status}`;
    let errorMessage = `HTTP error! status: ${response.status}`;
    try {
      const errorData = await response.json();
      if (typeof errorData?.detail === 'object' && errorData.detail !== null) {
        errorCode = errorData.detail.code || errorCode;
        errorMessage = errorData.detail.message || errorData.detail.detail || errorMessage;
      } else {
        errorCode = errorData?.code || errorCode;
        errorMessage = errorData?.detail || errorData?.message || errorMessage;
      }
    } catch {
      // ignore parse errors
    }
    if (errorCode === `HTTP_${response.status}`) {
      if (response.status === 401) {
        errorCode = 'SESSION_AUTH_EXPIRED';
        errorMessage = SESSION_AUTH_EXPIRED_MESSAGE;
      } else if (response.status === 410) {
        errorCode = 'SESSION_TERMINATED';
        errorMessage = SESSION_TERMINATED_MESSAGE;
      }
    }
    throw new AppError(errorCode, errorMessage);
  }
  return response.json() as Promise<T>;
};

const buildSessionTargetUrl = (
  endpoint: string,
  params: Record<string, string>
): string => {
  return buildControllerSessionTargetUrl(endpoint, params);
};

// Unified Session State Interface - matches backend models perfectly
interface SessionState {
  // ============================================================================
  // SESSION STATE (core session management)
  // ============================================================================
  activeSessionId: string | null;
  currentSession: Session | null;
  sessionContext: SessionContext | null;
  isLoading: boolean;
  error: string | null;
  sessionInitialized: boolean;
  sessionStatus: SessionStatus;
  runtime: SessionRuntimeInfo | null;

  // ============================================================================
  // REPOSITORY STATE (GitHub integration)
  // ============================================================================
  selectedRepository: SelectedRepository | null;
  availableRepositories: GitHubRepository[];
  isLoadingRepositories: boolean;
  repositoryError: string | null;

  // ============================================================================
  // CHAT & MESSAGES STATE (matches ChatMessage model)
  // ============================================================================
  messages: ChatMessage[];
  isLoadingMessages: boolean;
  messageError: string | null;

  // ============================================================================
  // CONTEXT MANAGEMENT STATE (matches ContextCard model)
  // ============================================================================
  contextCards: ContextCard[];
  isLoadingContextCards: boolean;
  contextCardError: string | null;

  // ============================================================================
  // FILE DEPENDENCIES STATE (matches FileEmbedding model)
  // ============================================================================
  fileContext: FileItem[];
  isLoadingFileContext: boolean;
  fileContextError: string | null;

  // ============================================================================
  // USER ISSUES STATE (matches UserIssue model)
  // ============================================================================
  userIssues: UserIssue[];
  currentIssue: UserIssue | null;
  isLoadingIssues: boolean;
  issueError: string | null;

  // ============================================================================
  // AGENT ORCHESTRATION STATE (for AI solver integration)
  // ============================================================================
  agentStatus: AgentStatus | null;
  agentHistory: AgentStatus[];

  // ============================================================================
  // UI STATE
  // ============================================================================
  activeTab: TabType;
  sidebarCollapsed: boolean;
  sessionLoadingEnabled: boolean;
  indexCodebaseEnabled: boolean;

  // ============================================================================
  // SESSION STATISTICS & METADATA
  // ============================================================================
  totalTokens: number;
  lastActivity: Date | null;
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';

  // ============================================================================
  // SESSION MANAGEMENT ACTIONS (matches backend session APIs)
  // ============================================================================
  createSessionForRepository: (repository: SelectedRepository) => Promise<string>;
  loadSession: (sessionId: string) => Promise<void>;
  updateSession: (sessionId: string, updates: UpdateSessionRequest) => Promise<boolean>;
  deleteSession: (sessionId: string) => Promise<boolean>;
  ensureSessionExists: (sessionId: string) => Promise<void>;
  setIndexCodebaseEnabled: (enabled: boolean) => void;

  // ============================================================================
  // REPOSITORY ACTIONS
  // ============================================================================
  loadRepositories: () => Promise<GitHubRepository[]>;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  setAvailableRepositories: (repositories: GitHubRepository[]) => void;
  setRepositoryLoading: (loading: boolean) => void;
  setRepositoryError: (error: string | null) => void;

  // ============================================================================
  // MESSAGE ACTIONS (matches ChatMessage APIs)
  // ============================================================================
  addMessage: (message: ChatMessage) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessage>) => Promise<boolean>;
  removeMessage: (messageId: string) => Promise<boolean>;
  loadMessages: (sessionId: string) => Promise<ChatMessage[]>;
  setMessages: (messages: ChatMessage[]) => void;
  setMessageLoading: (loading: boolean) => void;
  setMessageError: (error: string | null) => void;

  // ============================================================================
  // CONTEXT CARD ACTIONS (matches ContextCard APIs)
  // ============================================================================
  createContextCard: (card: CreateContextCardRequest) => Promise<ContextCard>;
  updateContextCard: (cardId: string, updates: Partial<CreateContextCardRequest>) => Promise<boolean>;
  deleteContextCard: (cardId: string) => Promise<void>;
  loadContextCards: (sessionId: string) => Promise<ContextCard[]>;
  setContextCards: (cards: ContextCard[]) => void;
  setContextCardLoading: (loading: boolean) => void;
  setContextCardError: (error: string | null) => void;

  // ============================================================================
  // FILE DEPENDENCY ACTIONS (matches FileEmbedding APIs)
  // ============================================================================
  createFileEmbedding: (embedding: CreateFileEmbeddingRequest) => Promise<boolean>;
  updateFileEmbedding: (fileId: string, updates: Partial<CreateFileEmbeddingRequest>) => Promise<boolean>;
  deleteFileEmbedding: (fileId: string) => Promise<boolean>;
  loadFileDependencies: (sessionId: string) => Promise<FileItem[]>;
  setFileContext: (files: FileItem[]) => void;
  setFileContextLoading: (loading: boolean) => void;
  setFileContextError: (error: string | null) => void;

  // ============================================================================
  // USER ISSUE ACTIONS (matches UserIssue APIs)
  // ============================================================================
  createUserIssue: (issue: UserIssue) => Promise<boolean>;
  updateUserIssue: (issueId: string, updates: Partial<UserIssue>) => Promise<boolean>;
  deleteUserIssue: (issueId: string) => Promise<boolean>;
  loadUserIssues: (sessionId: string) => Promise<void>;
  setUserIssues: (issues: UserIssue[]) => void;
  setCurrentIssue: (issue: UserIssue | null) => void;
  setIssueLoading: (loading: boolean) => void;
  setIssueError: (error: string | null) => void;

  // ============================================================================
  // AGENT ACTIONS (for AI solver integration)
  // ============================================================================
  updateAgentStatus: (status: AgentStatus) => void;
  addAgentHistoryEntry: (entry: AgentStatus) => void;
  clearAgentHistory: () => void;

  // ============================================================================
  // CORE ACTIONS
  // ============================================================================
  setActiveSession: (sessionId: string) => void;
  clearSession: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSessionInitialized: (initialized: boolean) => void;
  setActiveTab: (tab: TabType) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSessionLoadingEnabled: (enabled: boolean) => void;
  updateSessionStats: (tokens: number) => void;
  setConnectionStatus: (status: 'connected' | 'disconnected' | 'reconnecting') => void;
  setSessionStatus: (status: SessionStatus) => void;
  setRuntime: (runtime: SessionRuntimeInfo | null) => void;

  // ============================================================================
  // CHAT MESSAGE SENDING (for sending messages through backend chat endpoint)
  // ============================================================================

  sendChatMessage: (message: string, contextCards?: string[], repository?: SelectedRepository) => Promise<ChatResponse>;

  // ============================================================================
  // USER ISSUE CREATION (for creating issues with context)
  // ============================================================================

  createIssueWithContext: (request: CreateIssueWithContextRequest) => Promise<IssueCreationResponse>;

  // ============================================================================
  // FILE DEPENDENCY EXTRACTION (for extracting file dependencies for session)
  // ============================================================================

  extractFileDependenciesForSession: (sessionId: string, repoUrl: string) => Promise<boolean>;

  // ============================================================================
  // REPOSITORY BRANCH LOADING (for loading repository branches)
  // ============================================================================

  loadRepositoryBranches: (owner: string, repo: string) => Promise<GitHubBranch[]>;

  // ============================================================================
  // GITHUB ISSUE CREATION (for creating GitHub issues from user issues)
  // ============================================================================

  createGitHubIssueFromUserIssue: (issueId: string) => Promise<CreateGitHubIssueResponse>;
}

// Create the unified session store with persistence
export const useSessionStore = create<SessionState>()(
  devtools(
    persist(
      (set, get) => ({
        // ============================================================================
        // INITIAL STATE - matches backend models perfectly
        // ============================================================================

        // Session state
        activeSessionId: null,
        currentSession: null,
        sessionContext: null,
        isLoading: false,
        error: null,
        sessionInitialized: false,
        sessionStatus: 'no_repo',
        runtime: null,

        // Repository state
        selectedRepository: null,
        availableRepositories: [],
        isLoadingRepositories: false,
        repositoryError: null,

        // Chat & messages state
        messages: [],
        isLoadingMessages: false,
        messageError: null,

        // Context management state
        contextCards: [],
        isLoadingContextCards: false,
        contextCardError: null,

        // File dependencies state
        fileContext: [],
        isLoadingFileContext: false,
        fileContextError: null,

        // User issues state
        userIssues: [],
        currentIssue: null,
        isLoadingIssues: false,
        issueError: null,

        // Agent orchestration state
        agentStatus: null,
        agentHistory: [],

        // UI state
        activeTab: 'chat',
        sidebarCollapsed: false,
        sessionLoadingEnabled: false,
        indexCodebaseEnabled: true,

        // Session statistics
        totalTokens: 0,
        lastActivity: null,
        connectionStatus: 'disconnected',
        
        // ============================================================================
        // SESSION MANAGEMENT ACTIONS (matches backend session APIs)
        // ============================================================================

        createSessionForRepository: async (repository: SelectedRepository) => {
          const { indexCodebaseEnabled } = get();
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!sessionToken) {
            throw new AppError('AUTH_MISSING_TOKEN', 'No session token available');
          }

          try {
            set({ isLoading: true, error: null, sessionStatus: 'creating_session' });

            const repoOwner = repository.repository.owner?.login || repository.repository.full_name.split('/')[0];
            const repoName = repository.repository.name;

            const sessionData = await handleApiResponse<Session>(
              await fetch(buildApiUrl(API.SESSIONS.BASE), {
                method: 'POST',
                headers: getAuthHeaders(sessionToken),
                body: JSON.stringify({
                  repo_owner: repoOwner,
                  repo_name: repoName,
                  repo_branch: repository.branch,
                  title: `Chat - ${repoOwner}/${repoName}`,
                  // Trigger background indexing on session creation
                  index_codebase: indexCodebaseEnabled,
                }),
              })
            );

            const shouldProvisionRuntime =
              realtimeFeatureFlags.controllerSplitEnabled ||
              realtimeFeatureFlags.controllerBrokerEnabled;

            let runtime: SessionRuntimeInfo | null = null;
            if (shouldProvisionRuntime) {
              runtime = await handleApiResponse<SessionRuntimeInfo>(
                await fetch(
                  buildApiUrl(API.CONTROLLER.RUNTIME_ENSURE, {
                    sessionId: sessionData.session_id,
                  }),
                  {
                    method: 'POST',
                    headers: getAuthHeaders(sessionToken),
                    body: JSON.stringify({
                      org: 'yudai',
                      repo_owner: repoOwner,
                      repo_name: repoName,
                      environment: repository.branch || 'main',
                      repo_branch: repository.branch || 'main',
                      repo_url: repository.repository.html_url,
                    }),
                  }
                )
              );

            }

            const resolvedSession: Session = {
              ...sessionData,
              runtime_id: runtime?.runtime_id || sessionData.runtime_id,
              sandbox_id: runtime?.sandbox_id || sessionData.sandbox_id,
              tunnel_url: runtime?.tunnel_url || sessionData.tunnel_url,
            };

            set({
              activeSessionId: resolvedSession.session_id,
              currentSession: resolvedSession,
              runtime,
              selectedRepository: repository,
              sessionInitialized: true,
              isLoading: false,
              error: null,
              sessionStatus: 'ready',
              lastActivity: new Date(),
            });

            return resolvedSession.session_id;
          } catch (error) {
            const appError = toAppError(error, 'SESSION_CREATE_FAILED', 'Failed to create session');
            console.error('Failed to create session:', appError);
            set({
              isLoading: false,
              error: appError.message,
              sessionStatus: 'error',
            });
            throw appError;
          }
        },

        loadSession: async (sessionId: string) => {
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!sessionToken) {
            throw new AppError('AUTH_MISSING_TOKEN', 'No session token available');
          }

          try {
            set({ isLoading: true, error: null });

            const shouldLoadRuntime =
              realtimeFeatureFlags.controllerSplitEnabled ||
              realtimeFeatureFlags.controllerBrokerEnabled;
            let runtime: SessionRuntimeInfo | null = null;
            if (shouldLoadRuntime) {
              runtime = await handleApiResponse<SessionRuntimeInfo>(
                await fetch(
                  buildApiUrl(API.CONTROLLER.RUNTIME_DETAIL, { sessionId }),
                  {
                    method: 'GET',
                    headers: getAuthHeaders(sessionToken),
                  }
                )
              );

            }

            if (runtime) {
              set({ runtime });
            }

            const sessionDetailUrl = buildSessionTargetUrl(API.SESSIONS.DETAIL, {
              sessionId,
            });

            const context = await handleApiResponse<SessionContext>(
              await fetch(sessionDetailUrl, {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );

            const mergedSession: Session | null = context.session
              ? {
                  ...context.session,
                  runtime_id: runtime?.runtime_id || context.session.runtime_id,
                  sandbox_id: runtime?.sandbox_id || context.session.sandbox_id,
                  tunnel_url: runtime?.tunnel_url || context.session.tunnel_url,
                }
              : null;

            // Update all session state from context
            set({
              activeSessionId: sessionId,
              currentSession: mergedSession,
              runtime,
              sessionContext: context,
              messages: context.messages || [],
              contextCards: [],
              fileContext: context.file_embeddings || [],
              userIssues: context.user_issues || [],
              totalTokens: context.statistics?.total_tokens || 0,
              sessionInitialized: true,
              isLoading: false,
              error: null,
              sessionStatus: 'ready',
              lastActivity: new Date(),
            });
          } catch (error) {
            const appError = toAppError(error, 'SESSION_LOAD_FAILED', 'Failed to load session');
            console.error('Failed to load session:', appError);
            set({
              isLoading: false,
              error: appError.message,
              sessionStatus: 'error',
            });
            throw appError;
          }
        },

        updateSession: async (sessionId: string, updates: UpdateSessionRequest) => {
          // TODO: Implement when backend API is available
          console.log('Update session not yet implemented:', sessionId, updates);
          return false;
        },

        deleteSession: async (sessionId: string) => {
          // TODO: Implement when backend API is available
          console.log('Delete session not yet implemented:', sessionId);
          return false;
        },

        ensureSessionExists: async (sessionId: string) => {
          try {
            const sessionToken = useAuthStore.getState().sessionToken;
            if (!sessionToken) {
              console.warn('[SessionStore] No session token available for session validation');
              get().clearSession();
              throw new AppError('AUTH_MISSING_TOKEN', 'No session token available');
            }

            const shouldLoadRuntime =
              realtimeFeatureFlags.controllerSplitEnabled ||
              realtimeFeatureFlags.controllerBrokerEnabled;
            let runtime: SessionRuntimeInfo | null = null;
            if (shouldLoadRuntime) {
              runtime = await handleApiResponse<SessionRuntimeInfo>(
                await fetch(
                  buildApiUrl(API.CONTROLLER.RUNTIME_DETAIL, { sessionId }),
                  {
                    method: 'GET',
                    headers: getAuthHeaders(sessionToken),
                  }
                )
              );

            }

            if (runtime) {
              set({ runtime });
            }

            const sessionDetailUrl = buildSessionTargetUrl(API.SESSIONS.DETAIL, {
              sessionId,
            });

            await handleApiResponse<SessionContext>(
              await fetch(sessionDetailUrl, {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );

            set({
              activeSessionId: sessionId,
              sessionInitialized: true,
              error: null,
              sessionStatus: 'ready',
              runtime,
            });
          } catch (error) {
            console.warn(`[SessionStore] Session ${sessionId} does not exist or is not accessible:`, error);

            const errorMessage = error instanceof Error ? error.message : String(error);
            const isSessionNotFound = errorMessage.includes('Session not found') ||
                                     errorMessage.includes('404') ||
                                     errorMessage.includes('Not Found');

            if (isSessionNotFound) {
              console.log('[SessionStore] Session not found, clearing invalid session');
              get().clearSession();
              const notFoundError = new AppError('SESSION_NOT_FOUND', 'Session not found');
              set({ error: notFoundError.message, sessionStatus: 'error' });
              throw notFoundError;
            } else {
              const appError = toAppError(error, 'SESSION_VALIDATE_FAILED', 'Session validation failed');
              set({
                activeSessionId: null,
                sessionInitialized: false,
                error: appError.message,
                sessionStatus: 'error',
              });
              throw appError;
            }
          }
        },

        setIndexCodebaseEnabled: (enabled: boolean) => {
          set({ indexCodebaseEnabled: enabled });
        },

        // ============================================================================
        // REPOSITORY ACTIONS
        // ============================================================================

        loadRepositories: async () => {
          const sessionToken = useAuthStore.getState().sessionToken;

          try {
            set({ isLoadingRepositories: true, repositoryError: null });

            const repositories = await handleApiResponse<GitHubRepository[]>(
              await fetch(buildApiUrl(API.GITHUB.REPOS), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken || ''),
              })
            );

            set({
              availableRepositories: repositories,
              isLoadingRepositories: false,
              repositoryError: null,
            });
            return repositories;
          } catch (error) {
            const appError = toAppError(error, 'REPOSITORIES_LOAD_FAILED', 'Failed to load repositories');
            console.error('Failed to load repositories:', appError);
            set({
              isLoadingRepositories: false,
              repositoryError: appError.message
            });
            throw appError;
          }
        },

        setSelectedRepository: (repository: SelectedRepository | null) =>
          set((state) => ({
            selectedRepository: repository,
            repositoryError: null,
            sessionStatus: repository
              ? state.activeSessionId
                ? 'ready'
                : 'awaiting_session'
              : 'no_repo',
          })),

        setAvailableRepositories: (repositories: GitHubRepository[]) =>
          set({ availableRepositories: repositories }),

        setRepositoryLoading: (loading: boolean) =>
          set({ isLoadingRepositories: loading }),

        setRepositoryError: (error: string | null) =>
          set({ repositoryError: error }),

        // ============================================================================
        // MESSAGE ACTIONS (matches ChatMessage APIs)
        // ============================================================================

        addMessage: (message: ChatMessage) => {
          set((state) => ({
            messages: [...state.messages, message],
            totalTokens: state.totalTokens + (message.tokens || 0),
            lastActivity: new Date(),
          }));
        },

        updateMessage: async (messageId: string, updates: Partial<ChatMessage>) => {
          // TODO: Implement when backend API is available
          console.log('Update message not yet implemented:', messageId, updates);
          return false;
        },

        removeMessage: async (messageId: string) => {
          // TODO: Implement when backend API is available
          console.log('Remove message not yet implemented:', messageId);
          return false;
        },

        loadMessages: async (sessionId: string) => {
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!sessionToken) {
            const authError = new AppError('AUTH_MISSING_TOKEN', 'No session token available');
            set({
              isLoadingMessages: false,
              messageError: authError.message
            });
            throw authError;
          }

          try {
            set({ isLoadingMessages: true, messageError: null });

            const messagesUrl = buildSessionTargetUrl(API.SESSIONS.MESSAGES, {
              sessionId,
            });

            const messages = await handleApiResponse<ChatMessage[]>(
              await fetch(messagesUrl, {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );

            set({
              messages,
              isLoadingMessages: false,
              messageError: null,
            });
            return messages;
          } catch (error) {
            const appError = toAppError(error, 'MESSAGES_LOAD_FAILED', 'Failed to load messages');
            console.error('Failed to load messages:', appError);
            set({
              isLoadingMessages: false,
              messageError: appError.message
            });
            throw appError;
          }
        },

        setMessages: (messages: ChatMessage[]) => {
          const totalTokens = messages.reduce((sum, msg) => sum + (msg.tokens || 0), 0);
          set({ messages, totalTokens, lastActivity: new Date() });
        },

        setMessageLoading: (loading: boolean) => set({ isLoadingMessages: loading }),
        setMessageError: (error: string | null) => set({ messageError: error }),

        // ============================================================================
        // CONTEXT CARD ACTIONS (matches ContextCard APIs)
        // ============================================================================

        createContextCard: async (card: CreateContextCardRequest) => {
          const { activeSessionId } = get();
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!activeSessionId || !sessionToken) {
            throw new AppError('SESSION_NOT_READY', 'No active session or session token available');
          }

          try {
            set({ isLoadingContextCards: true, contextCardError: null });

            const createCardUrl = buildSessionTargetUrl(API.SESSIONS.CONTEXT_CARDS, {
              sessionId: activeSessionId,
            });

            const newCard = await handleApiResponse<ContextCard>(
              await fetch(createCardUrl, {
                method: 'POST',
                headers: getAuthHeaders(sessionToken),
                body: JSON.stringify(card),
              })
            );

            set((state) => ({
              contextCards: [...state.contextCards, {
                id: newCard.id.toString(),
                title: newCard.title,
                description: newCard.description,
                tokens: newCard.tokens,
                source: newCard.source as 'chat' | 'file-deps' | 'upload',
                content: newCard.content,
              }],
              isLoadingContextCards: false,
              totalTokens: state.totalTokens + newCard.tokens,
              lastActivity: new Date(),
            }));

            return {
              id: newCard.id.toString(),
              title: newCard.title,
              description: newCard.description,
              tokens: newCard.tokens,
              source: newCard.source as 'chat' | 'file-deps' | 'upload',
              content: newCard.content,
            };
          } catch (error) {
            const appError = toAppError(error, 'CONTEXT_CARD_CREATE_FAILED', 'Failed to create context card');
            console.error('Failed to create context card:', appError);
            set({
              isLoadingContextCards: false,
              contextCardError: appError.message
            });
            throw appError;
          }
        },

        updateContextCard: async (cardId: string, updates: Partial<CreateContextCardRequest>) => {
          // TODO: Implement when backend API is available
          console.log('Update context card not yet implemented:', cardId, updates);
          return false;
        },

        deleteContextCard: async (cardId: string) => {
          const { activeSessionId } = get();
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!activeSessionId || !sessionToken) {
            throw new AppError('SESSION_NOT_READY', 'No active session or session token available');
          }

          try {
            set({ isLoadingContextCards: true, contextCardError: null });

            const deleteCardUrl = buildSessionTargetUrl(
              API.SESSIONS.CONTEXT_CARD_DETAIL,
              { sessionId: activeSessionId, cardId }
            );

            await handleApiResponse<{ success: boolean; message: string }>(
              await fetch(deleteCardUrl, {
                method: 'DELETE',
                headers: getAuthHeaders(sessionToken),
              })
            );

            set((state) => {
              const cardToRemove = state.contextCards.find(c => c.id === cardId);
              return {
                contextCards: state.contextCards.filter(c => c.id !== cardId),
                isLoadingContextCards: false,
                totalTokens: state.totalTokens - (cardToRemove?.tokens || 0),
                lastActivity: new Date(),
              };
            });
          } catch (error) {
            const appError = toAppError(error, 'CONTEXT_CARD_DELETE_FAILED', 'Failed to delete context card');
            console.error('Failed to delete context card:', appError);
            set({
              isLoadingContextCards: false,
              contextCardError: appError.message
            });
            throw appError;
          }
        },

        loadContextCards: async (sessionId: string) => {
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!sessionToken) {
            const authError = new AppError('AUTH_MISSING_TOKEN', 'No session token available');
            set({
              isLoadingContextCards: false,
              contextCardError: authError.message
            });
            throw authError;
          }

          try {
            set({ isLoadingContextCards: true, contextCardError: null });

            const contextCardsUrl = buildSessionTargetUrl(
              API.SESSIONS.CONTEXT_CARDS,
              { sessionId }
            );

            const cards = await handleApiResponse<ContextCard[]>(
              await fetch(contextCardsUrl, {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );

            const transformedCards: ContextCard[] = cards.map(card => ({
              id: card.id.toString(),
              title: card.title,
              description: card.description,
              tokens: card.tokens,
              source: card.source as 'chat' | 'file-deps' | 'upload',
            }));

            set({
              contextCards: transformedCards,
              isLoadingContextCards: false,
              contextCardError: null,
            });
            return transformedCards;
          } catch (error) {
            const appError = toAppError(error, 'CONTEXT_CARDS_LOAD_FAILED', 'Failed to load context cards');
            console.error('Failed to load context cards:', appError);
            set({
              isLoadingContextCards: false,
              contextCardError: appError.message
            });
            throw appError;
          }
        },

        setContextCards: (cards: ContextCard[]) => {
          const totalTokens = cards.reduce((sum, card) => sum + card.tokens, 0);
          set((state) => ({
            contextCards: cards,
            totalTokens: state.messages.reduce((sum, msg) => sum + (msg.tokens || 0), 0) + totalTokens,
            lastActivity: new Date(),
          }));
        },

        setContextCardLoading: (loading: boolean) => set({ isLoadingContextCards: loading }),
        setContextCardError: (error: string | null) => set({ contextCardError: error }),

        // ============================================================================
        // FILE DEPENDENCY ACTIONS (matches FileEmbedding APIs)
        // ============================================================================

        createFileEmbedding: async (embedding: CreateFileEmbeddingRequest) => {
          // TODO: Implement when backend API is available
          console.log('Create file embedding not yet implemented:', embedding);
          return false;
        },

        updateFileEmbedding: async (fileId: string, updates: Partial<CreateFileEmbeddingRequest>) => {
          // TODO: Implement when backend API is available
          console.log('Update file embedding not yet implemented:', fileId, updates);
          return false;
        },

        deleteFileEmbedding: async (fileId: string) => {
          // TODO: Implement when backend API is available
          console.log('Delete file embedding not yet implemented:', fileId);
          return false;
        },

        loadFileDependencies: async (sessionId: string) => {
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!sessionToken) {
            const authError = new AppError('AUTH_MISSING_TOKEN', 'No session token available');
            set({
              isLoadingFileContext: false,
              fileContextError: authError.message
            });
            throw authError;
          }

          try {
            set({ isLoadingFileContext: true, fileContextError: null });

            const fileDepsUrl = buildSessionTargetUrl(
              API.SESSIONS.FILE_DEPS_SESSION,
              { sessionId }
            );

            const deps = await handleApiResponse<FileItem[]>(
              await fetch(fileDepsUrl, {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );

            const transformedFiles: FileItem[] = deps.map(dep => ({
              id: dep.id.toString(),
              name: dep.file_name || 'Unknown',
              path: dep.file_path,
              type: 'INTERNAL' as const,
              tokens: dep.tokens,
              category: dep.category || dep.file_type || 'unknown',
              created_at: dep.created_at,
            }));

            set({
              fileContext: transformedFiles,
              isLoadingFileContext: false,
              fileContextError: null,
            });
            return transformedFiles;
          } catch (error) {
            const appError = toAppError(error, 'FILE_DEPS_LOAD_FAILED', 'Failed to load file dependencies');
            console.error('Failed to load file dependencies:', appError);
            set({
              isLoadingFileContext: false,
              fileContextError: appError.message
            });
            throw appError;
          }
        },

        setFileContext: (files: FileItem[]) => {
          set({ fileContext: files, lastActivity: new Date() });
        },

        setFileContextLoading: (loading: boolean) => set({ isLoadingFileContext: loading }),
        setFileContextError: (error: string | null) => set({ fileContextError: error }),

        // ============================================================================
        // USER ISSUE ACTIONS (matches UserIssue APIs)
        // ============================================================================

        createUserIssue: async (issue: UserIssue) => {
          // TODO: Implement with proper typing when backend API is available
          console.log('Create user issue not yet implemented:', issue);
          return false;
        },

        updateUserIssue: async (issueId: string, updates: Partial<UserIssue>) => {
          // TODO: Implement with proper typing when backend API is available
          console.log('Update user issue not yet implemented:', issueId, updates);
          return false;
        },

        deleteUserIssue: async (issueId: string) => {
          // TODO: Implement when backend API is available
          console.log('Delete user issue not yet implemented:', issueId);
          return false;
        },

        loadUserIssues: async (sessionId: string) => {
          // TODO: Implement when backend API is available
          console.log('Load user issues not yet implemented:', sessionId);
        },

        setUserIssues: (issues: UserIssue[]) => set({ userIssues: issues }),
        setCurrentIssue: (issue: UserIssue | null) => set({ currentIssue: issue }),
        setIssueLoading: (loading: boolean) => set({ isLoadingIssues: loading }),
        setIssueError: (error: string | null) => set({ issueError: error }),

        // ============================================================================
        // AGENT ACTIONS (for AI solver integration)
        // ============================================================================

        updateAgentStatus: (status: AgentStatus | null) => set({ agentStatus: status }),
        addAgentHistoryEntry: (entry: AgentStatus) => {
          set((state) => ({
            agentHistory: [...state.agentHistory, entry]
          }));
        },
        clearAgentHistory: () => set({ agentHistory: [] }),

        // ============================================================================
        // CORE ACTIONS
        // ============================================================================

        setActiveSession: (sessionId: string) =>
          set({
            activeSessionId: sessionId,
            error: null,
            sessionInitialized: true,
            sessionStatus: 'ready',
          }),

        clearSession: () => {
          console.log('[SessionStore] Clearing session state');
          set({
            activeSessionId: null,
            currentSession: null,
            sessionContext: null,
            error: null,
            sessionInitialized: false,
            sessionStatus: get().selectedRepository ? 'awaiting_session' : 'no_repo',
            runtime: null,
            messages: [],
            contextCards: [],
            fileContext: [],
            userIssues: [],
            currentIssue: null,
            totalTokens: 0,
            lastActivity: null,
            agentStatus: null,
            agentHistory: [],
          });
        },

        setLoading: (loading: boolean) => set({ isLoading: loading }),
        setError: (error: string | null) => set({ error: error }),
        setSessionInitialized: (initialized: boolean) => set({ sessionInitialized: initialized }),
        setActiveTab: (tab: TabType) => set({ activeTab: tab }),
        setSidebarCollapsed: (collapsed: boolean) => set({ sidebarCollapsed: collapsed }),
        setSessionLoadingEnabled: (enabled: boolean) => set({ sessionLoadingEnabled: enabled }),
        updateSessionStats: (tokens: number) => {
          set((state) => ({
            totalTokens: state.totalTokens + tokens,
            lastActivity: new Date()
          }));
        },
        setConnectionStatus: (status: 'connected' | 'disconnected' | 'reconnecting') =>
          set({ connectionStatus: status }),
        setSessionStatus: (status: SessionStatus) =>
          set({ sessionStatus: status }),
        setRuntime: (runtime: SessionRuntimeInfo | null) =>
          set({ runtime }),

        // ============================================================================
        // CHAT MESSAGE SENDING IMPLEMENTATION
        // ============================================================================

        sendChatMessage: async (message: string, contextCards?: string[], repository?: SelectedRepository) => {
          const { activeSessionId } = get();
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!activeSessionId || !sessionToken) {
            throw new AppError('SESSION_NOT_READY', 'No active session or session token available');
          }

          try {
            set({ isLoadingMessages: true, messageError: null, sessionStatus: 'sending' });

            const chatRequest: ChatRequest = {
              session_id: activeSessionId,
              message: {
                message_text: message,
              },
              context_cards: contextCards,
              repository: repository ? {
                owner: repository.repository.owner?.login || repository.repository.full_name.split('/')[0],
                name: repository.repository.name,
                branch: repository.branch,
              } : undefined,
            };

            const chatUrl = buildSessionTargetUrl(API.SESSIONS.CHAT, {
              sessionId: activeSessionId,
            });

            const response = await handleApiResponse<ChatResponse>(
              await fetch(chatUrl, {
                method: 'POST',
                headers: getAuthHeaders(sessionToken),
                body: JSON.stringify(chatRequest),
              })
            );

            // Deterministic local append for both user and assistant response.
            const now = new Date().toISOString();
            const localUserMessage: ChatMessage = {
              id: Date.now(),
              message_id: `local_user_${Date.now()}`,
              message_text: message,
              sender_type: 'user',
              role: 'user',
              tokens: Math.max(1, Math.ceil(message.length / 4)),
              created_at: now,
              updated_at: now,
            };
            const localAssistantMessage: ChatMessage = {
              id: Date.now() + 1,
              message_id: response.message_id || `local_assistant_${Date.now()}`,
              message_text: response.reply || '',
              sender_type: 'assistant',
              role: 'assistant',
              tokens: Math.max(1, Math.ceil((response.reply || '').length / 4)),
              created_at: now,
              updated_at: now,
            };

            set((state) => ({
              messages: [...state.messages, localUserMessage, localAssistantMessage],
              isLoadingMessages: false,
              messageError: null,
              sessionStatus: 'ready',
              lastActivity: new Date(),
            }));

            // Best-effort reconciliation with backend state.
            void get().loadMessages(activeSessionId).catch((reconcileError) => {
              console.warn('[SessionStore] Message reconciliation failed:', reconcileError);
            });

            return response;
          } catch (error) {
            const appError = toAppError(error, 'CHAT_SEND_FAILED', 'Failed to send message');
            console.error('Failed to send chat message:', appError);
            set({
              isLoadingMessages: false,
              messageError: appError.message,
              sessionStatus: 'error',
            });
            throw appError;
          }
        },

        // ============================================================================
        // USER ISSUE CREATION IMPLEMENTATION
        // ============================================================================

        createIssueWithContext: async (request: CreateIssueWithContextRequest) => {
          const { activeSessionId, selectedRepository, currentSession } = get();
          const sessionToken = useAuthStore.getState().sessionToken;

          try {
            set({ isLoadingIssues: true, issueError: null });

            const normalizeSelection = (repository: SelectedRepository) => ({
              owner: repository.repository.owner?.login || repository.repository.full_name.split('/')[0],
              name: repository.repository.name,
              branch: repository.branch || '',
            });

            const selectionInfo = selectedRepository ? normalizeSelection(selectedRepository) : null;
            const sessionMatchesSelection = selectionInfo && currentSession
              ? currentSession.repo_owner === selectionInfo.owner
                && currentSession.repo_name === selectionInfo.name
                && (currentSession.repo_branch || '') === selectionInfo.branch
              : false;

            let sessionIdToUse = activeSessionId;
            if (selectionInfo && (!sessionIdToUse || !sessionMatchesSelection)) {
              const newSessionId = await get().createSessionForRepository(selectedRepository!);
              sessionIdToUse = newSessionId;
            }

            if (!sessionIdToUse) {
              throw new Error('No active session available');
            }

            const repositoryInfo = selectionInfo
              ? { owner: selectionInfo.owner, name: selectionInfo.name, branch: selectionInfo.branch || undefined }
              : request.repository_info;

            const mergedRequest = {
              ...request,
              repository_info: repositoryInfo,
            };

            const response = await handleApiResponse<IssueCreationResponse>(
              await fetch(
                buildSessionTargetUrl(API.SESSIONS.ISSUES.CREATE, {
                  sessionId: sessionIdToUse,
                }),
                {
                method: 'POST',
                headers: getAuthHeaders(sessionToken || ''),
                body: JSON.stringify(mergedRequest),
                }
              )
            );

            set({ isLoadingIssues: false });
            return response;
          } catch (error) {
            const appError = toAppError(error, 'ISSUE_CREATE_FAILED', 'Failed to create issue');
            console.error('Failed to create issue with context:', appError);
            set({
              isLoadingIssues: false,
              issueError: appError.message
            });
            throw appError;
          }
        },

        // ============================================================================
        // FILE DEPENDENCY EXTRACTION IMPLEMENTATION
        // ============================================================================
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        extractFileDependenciesForSession: async (_sessionId: string, _repoUrl: string) => {
          

          try {
            // Deprecated: extraction now starts automatically after session creation.
            console.info('[SessionStore] extractFileDependenciesForSession is deprecated. Indexing happens automatically.');
            return true; // treat as success/no-op
          } catch (error) {
            console.error('Failed to extract file dependencies:', error);
            set({
              isLoadingFileContext: false,
              fileContextError: error instanceof Error ? error.message : 'Failed to extract file dependencies'
            });
            return false;
          }
        },

        // ============================================================================
        // REPOSITORY BRANCH LOADING IMPLEMENTATION
        // ============================================================================

        loadRepositoryBranches: async (owner: string, repo: string) => {
          const sessionToken = useAuthStore.getState().sessionToken;

          try {
            const branches = await handleApiResponse<GitHubBranch[]>(
              await fetch(buildApiUrl(API.GITHUB.REPO_BRANCHES, { owner, repo }), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken || ''),
              })
            );

            // Transform API response to match frontend GitHubBranch type
            const transformedBranches: GitHubBranch[] = branches.map(branch => ({
              name: branch.name,
              commit: branch.commit,
              protected: false // API doesn't provide this, set default
            }));

            return transformedBranches;
          } catch (error) {
            console.error('Failed to load repository branches:', error);
            throw error;
          }
        },

        // ============================================================================
        // GITHUB ISSUE CREATION IMPLEMENTATION
        // ============================================================================

        createGitHubIssueFromUserIssue: async (issueId: string) => {
          const { activeSessionId } = get();
          const sessionToken = useAuthStore.getState().sessionToken;

          if (!activeSessionId) {
            throw new Error('No active session available');
          }

          const response = await handleApiResponse<CreateGitHubIssueResponse>(
            await fetch(
              buildSessionTargetUrl(API.SESSIONS.ISSUES.CREATE_GITHUB_ISSUE, {
                sessionId: activeSessionId,
                issueId,
              }),
              {
              method: 'POST',
              headers: getAuthHeaders(sessionToken || ''),
              }
            )
          );
          return response;
        },
      }),
      {
        name: 'session-storage',
        // Only persist certain parts of the state for security and performance
        partialize: (state) => ({
          // UI preferences (no session persistence)
          activeTab: state.activeTab,
          sidebarCollapsed: state.sidebarCollapsed,
          sessionLoadingEnabled: state.sessionLoadingEnabled,
          indexCodebaseEnabled: state.indexCodebaseEnabled,

          // Connection status
          connectionStatus: state.connectionStatus,
        }),
      }
    ),
    {
      name: 'session-store',
    }
  )
);
