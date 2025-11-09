import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import {
  SelectedRepository,
  TabType,
  ContextCard,
  FileItem,
  ChatMessage,
  GitHubRepository,
  User,
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
  CreateGitHubIssueResponse
} from '../types/sessionTypes';
import { API, buildApiUrl } from '../config/api';

// Helper function to safely retrieve session token from localStorage
const getStoredSessionToken = (): string | null => {
  try {
    return localStorage.getItem('session_token');
  } catch (error) {
    console.warn('Failed to access localStorage:', error);
    return null;
  }
};

// Helper function to get auth headers
const getAuthHeaders = (sessionToken?: string): HeadersInit => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = sessionToken || getStoredSessionToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

// Helper function to handle API responses
const handleApiResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    let errorMessage = `HTTP error! status: ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      // ignore parse errors
    }
    throw new Error(errorMessage);
  }
  return response.json() as Promise<T>;
};

// Unified Session State Interface - matches backend models perfectly
interface SessionState {
  // ============================================================================
  // AUTH STATE (only for login/entry point)
  // ============================================================================
  user: User | null;
  sessionToken: string | null;
  isAuthenticated: boolean;
  authLoading: boolean;
  authError: string | null;

  // ============================================================================
  // SESSION STATE (core session management)
  // ============================================================================
  activeSessionId: string | null;
  currentSession: Session | null;
  sessionContext: SessionContext | null;
  isLoading: boolean;
  error: string | null;
  sessionInitialized: boolean;

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

  // ============================================================================
  // SESSION STATISTICS & METADATA
  // ============================================================================
  totalTokens: number;
  lastActivity: Date | null;
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';

  // ============================================================================
  // AUTH ACTIONS (only for login/logout)
  // ============================================================================
  initializeAuth: () => Promise<void>;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  setAuthFromCallback: (authData: { user: User; sessionToken: string }) => Promise<void>;
  setAuthLoading: (loading: boolean) => void;
  setAuthError: (error: string | null) => void;

  // ============================================================================
  // SESSION MANAGEMENT ACTIONS (matches backend session APIs)
  // ============================================================================
  createSessionForRepository: (repository: SelectedRepository) => Promise<string | null>;
  loadSession: (sessionId: string) => Promise<boolean>;
  updateSession: (sessionId: string, updates: UpdateSessionRequest) => Promise<boolean>;
  deleteSession: (sessionId: string) => Promise<boolean>;
  ensureSessionExists: (sessionId: string) => Promise<boolean>;
  validatePersistedSession: () => Promise<void>;

  // ============================================================================
  // REPOSITORY ACTIONS
  // ============================================================================
  loadRepositories: () => Promise<void>;
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
  loadMessages: (sessionId: string) => Promise<void>;
  setMessages: (messages: ChatMessage[]) => void;
  setMessageLoading: (loading: boolean) => void;
  setMessageError: (error: string | null) => void;

  // ============================================================================
  // CONTEXT CARD ACTIONS (matches ContextCard APIs)
  // ============================================================================
  createContextCard: (card: CreateContextCardRequest) => Promise<boolean>;
  updateContextCard: (cardId: string, updates: Partial<CreateContextCardRequest>) => Promise<boolean>;
  deleteContextCard: (cardId: string) => Promise<boolean>;
  loadContextCards: (sessionId: string) => Promise<void>;
  setContextCards: (cards: ContextCard[]) => void;
  setContextCardLoading: (loading: boolean) => void;
  setContextCardError: (error: string | null) => void;

  // ============================================================================
  // FILE DEPENDENCY ACTIONS (matches FileEmbedding APIs)
  // ============================================================================
  createFileEmbedding: (embedding: CreateFileEmbeddingRequest) => Promise<boolean>;
  updateFileEmbedding: (fileId: string, updates: Partial<CreateFileEmbeddingRequest>) => Promise<boolean>;
  deleteFileEmbedding: (fileId: string) => Promise<boolean>;
  loadFileDependencies: (sessionId: string) => Promise<void>;
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

  // ============================================================================
  // CHAT MESSAGE SENDING (for sending messages through backend chat endpoint)
  // ============================================================================

  sendChatMessage: (message: string, contextCards?: string[], repository?: SelectedRepository) => Promise<ChatResponse | null>;

  // ============================================================================
  // USER ISSUE CREATION (for creating issues with context)
  // ============================================================================

  createIssueWithContext: (request: CreateIssueWithContextRequest) => Promise<IssueCreationResponse | null>;

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

        // Auth state (only for login/logout)
        user: null,
        sessionToken: null,
        isAuthenticated: false,
        authLoading: true,
        authError: null,

        // Session state
        activeSessionId: null,
        currentSession: null,
        sessionContext: null,
        isLoading: false,
        error: null,
        sessionInitialized: false,

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

        // Session statistics
        totalTokens: 0,
        lastActivity: null,
        connectionStatus: 'disconnected',
        
        // ============================================================================
        // AUTH ACTIONS (only for login/logout - matches backend auth flow)
        // ============================================================================

        initializeAuth: async () => {
          try {
            console.log('[SessionStore] Starting authentication initialization');
            set({ authLoading: true, authError: null });

            const storedSessionToken = getStoredSessionToken();

            if (storedSessionToken) {
              console.log('[SessionStore] Found stored session token, validating...');
              try {
                const userData = await handleApiResponse<{
                  id: string;
                  github_username: string;
                  github_id: string;
                  email: string;
                  display_name: string;
                  avatar_url: string;
                }>(
                  await fetch(buildApiUrl(API.AUTH.USER), {
                    method: 'GET',
                    headers: getAuthHeaders(storedSessionToken),
                  })
                );
                const user: User = {
                  id: parseInt(userData.id),
                  github_username: userData.github_username,
                  github_user_id: userData.github_id,
                  email: userData.email,
                  display_name: userData.display_name,
                  avatar_url: userData.avatar_url,
                  created_at: new Date().toISOString(),
                  last_login: new Date().toISOString(),
                };

                set({
                  user,
                  sessionToken: storedSessionToken,
                  isAuthenticated: true,
                  authLoading: false,
                  authError: null,
                });

                // After successful auth, validate any persisted session
                await get().validatePersistedSession();
              } catch (error) {
                console.warn('[SessionStore] Stored session validation failed:', error);
                localStorage.removeItem('session_token');
                get().clearSession();

                set({
                  user: null,
                  sessionToken: null,
                  isAuthenticated: false,
                  authLoading: false,
                  authError: 'Stored session validation failed',
                });
              }
            } else {
              console.log('[SessionStore] No stored session token found');
              get().clearSession();

              set({
                user: null,
                sessionToken: null,
                isAuthenticated: false,
                authLoading: false,
                authError: null,
              });
            }
            console.log('[SessionStore] Authentication initialization completed');
          } catch (error) {
            console.error('[SessionStore] Auth initialization failed:', error);
            get().clearSession();

            set({
              user: null,
              sessionToken: null,
              isAuthenticated: false,
              authLoading: false,
              authError: 'Auth initialization failed',
            });
          }
        },

        login: async () => {
          try {
            set({ authLoading: true, authError: null });
            const { login_url } = await handleApiResponse<{ login_url: string }>(
              await fetch(buildApiUrl(API.AUTH.LOGIN), {
                method: 'GET',
                headers: getAuthHeaders(),
              })
            );
            window.location.href = login_url;
          } catch (error) {
            console.error('Login failed:', error);
            set({ authLoading: false, authError: 'Login failed' });
            throw error;
          }
        },

        logout: async () => {
          try {
            const { sessionToken } = get();
            if (sessionToken) {
              await handleApiResponse<{ success: boolean }>(
                await fetch(buildApiUrl(API.AUTH.LOGOUT), {
                  method: 'POST',
                  headers: getAuthHeaders(sessionToken),
                  body: JSON.stringify({ session_token: sessionToken }),
                })
              );
            }
          } catch (error) {
            console.warn('Logout API call failed:', error);
          } finally {
            localStorage.removeItem('session_token');
            set({
              user: null,
              sessionToken: null,
              isAuthenticated: false,
              authLoading: false,
              authError: null,
              activeSessionId: null,
              error: null,
              sessionInitialized: false,
              messages: [],
              contextCards: [],
              fileContext: [],
              userIssues: [],
              currentIssue: null,
              totalTokens: 0,
              lastActivity: null,
            });
            window.location.href = '/auth/login';
          }
        },

        refreshAuth: async () => {
          await get().initializeAuth();
        },

        setAuthFromCallback: async (authData: { user: User; sessionToken: string }) => {
          try {
            console.log('[SessionStore] Setting auth from callback:', authData);

            localStorage.setItem('session_token', authData.sessionToken);

            set({
              user: authData.user,
              sessionToken: authData.sessionToken,
              isAuthenticated: true,
              authLoading: false,
              authError: null,
            });

            get().clearSession();
            console.log('[SessionStore] Auth from callback completed successfully');
          } catch (error) {
            console.error('[SessionStore] Error setting auth from callback:', error);
            set({ authError: 'Failed to set auth from callback' });
            throw error;
          }
        },

        setAuthLoading: (loading: boolean) => set({ authLoading: loading }),
        setAuthError: (error: string | null) => set({ authError: error }),

        // ============================================================================
        // SESSION MANAGEMENT ACTIONS (matches backend session APIs)
        // ============================================================================

        createSessionForRepository: async (repository: SelectedRepository) => {
          const { sessionToken } = get();

          if (!sessionToken) {
            throw new Error('No session token available');
          }

          try {
            set({ isLoading: true, error: null });

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
                  index_codebase: true,
                }),
              })
            );

            set({
              activeSessionId: sessionData.session_id,
              currentSession: sessionData,
              selectedRepository: repository,
              sessionInitialized: true,
              isLoading: false,
              error: null,
              lastActivity: new Date(),
            });

            return sessionData.session_id;
          } catch (error) {
            console.error('Failed to create session:', error);
            set({
              isLoading: false,
              error: error instanceof Error ? error.message : 'Failed to create session'
            });
            return null;
          }
        },

        loadSession: async (sessionId: string) => {
          const { sessionToken } = get();

          if (!sessionToken) {
            throw new Error('No session token available');
          }

          try {
            set({ isLoading: true, error: null });

            const context = await handleApiResponse<SessionContext>(
              await fetch(buildApiUrl(API.SESSIONS.DETAIL, { sessionId }), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );

            // Update all session state from context
            set({
              activeSessionId: sessionId,
              currentSession: context.session,
              sessionContext: context,
              messages: context.messages || [],
              contextCards: [],
              fileContext: context.file_embeddings || [],
              userIssues: context.user_issues || [],
              totalTokens: context.statistics?.total_tokens || 0,
              sessionInitialized: true,
              isLoading: false,
              error: null,
              lastActivity: new Date(),
            });

            return true;
          } catch (error) {
            console.error('Failed to load session:', error);
            set({
              isLoading: false,
              error: error instanceof Error ? error.message : 'Failed to load session'
            });
            return false;
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
            const { sessionToken } = get();
            if (!sessionToken) {
              console.warn('[SessionStore] No session token available for session validation');
              get().clearSession();
              return false;
            }

            await handleApiResponse<SessionContext>(
              await fetch(buildApiUrl(API.SESSIONS.DETAIL, { sessionId }), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );

            set({
              activeSessionId: sessionId,
              sessionInitialized: true,
              error: null,
            });

            return true;
          } catch (error) {
            console.warn(`[SessionStore] Session ${sessionId} does not exist or is not accessible:`, error);

            const errorMessage = error instanceof Error ? error.message : String(error);
            const isSessionNotFound = errorMessage.includes('Session not found') ||
                                     errorMessage.includes('404') ||
                                     errorMessage.includes('Not Found');

            if (isSessionNotFound) {
              console.log('[SessionStore] Session not found, clearing invalid session');
              get().clearSession();
              set({ error: 'Session not found - cleared invalid session' });
            } else {
              set({
                activeSessionId: null,
                sessionInitialized: false,
                error: 'Session validation failed',
              });
            }

            return false;
          }
        },

        validatePersistedSession: async () => {
          const { activeSessionId, sessionToken } = get();

          if (!activeSessionId || !sessionToken) {
            console.log('[SessionStore] No persisted session to validate');
            return;
          }

          console.log(`[SessionStore] Validating persisted session: ${activeSessionId}`);

          try {
            await handleApiResponse<SessionContext>(
              await fetch(buildApiUrl(API.SESSIONS.DETAIL, { sessionId: activeSessionId }), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken),
              })
            );
            console.log(`[SessionStore] Persisted session ${activeSessionId} is valid`);

            set({
              sessionInitialized: true,
              error: null,
            });
          } catch (error) {
            console.warn(`[SessionStore] Persisted session ${activeSessionId} is invalid:`, error);

            const errorMessage = error instanceof Error ? error.message : String(error);
            const isSessionNotFound = errorMessage.includes('Session not found') ||
                                     errorMessage.includes('404') ||
                                     errorMessage.includes('Not Found');

            if (isSessionNotFound) {
              console.log('[SessionStore] Persisted session not found, clearing');
              get().clearSession();
            }
          }
        },

        // ============================================================================
        // REPOSITORY ACTIONS
        // ============================================================================

        loadRepositories: async () => {
          const { sessionToken } = get();

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
          } catch (error) {
            console.error('Failed to load repositories:', error);
            set({
              isLoadingRepositories: false,
              repositoryError: error instanceof Error ? error.message : 'Failed to load repositories'
            });
          }
        },

        setSelectedRepository: (repository: SelectedRepository | null) =>
          set({ selectedRepository: repository, repositoryError: null }),

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
          const { sessionToken } = get();

          try {
            set({ isLoadingMessages: true, messageError: null });

            const allMessages = await handleApiResponse<ChatMessage[]>(
              await fetch(buildApiUrl(API.SESSIONS.MESSAGES, { sessionId }), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken || ''),
              })
            );
            
            const messages = allMessages;

            set({
              messages,
              isLoadingMessages: false,
              messageError: null,
            });
          } catch (error) {
            console.error('Failed to load messages:', error);
            set({
              isLoadingMessages: false,
              messageError: error instanceof Error ? error.message : 'Failed to load messages'
            });
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
          const { activeSessionId, sessionToken } = get();

          if (!activeSessionId || !sessionToken) {
            throw new Error('No active session or session token available');
          }

          try {
            set({ isLoadingContextCards: true, contextCardError: null });

            const newCard = await handleApiResponse<ContextCard>(
              await fetch(buildApiUrl(API.SESSIONS.CONTEXT_CARDS, { sessionId: activeSessionId }), {
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
              }],
              isLoadingContextCards: false,
              totalTokens: state.totalTokens + newCard.tokens,
              lastActivity: new Date(),
            }));

            return true;
          } catch (error) {
            console.error('Failed to create context card:', error);
            set({
              isLoadingContextCards: false,
              contextCardError: error instanceof Error ? error.message : 'Failed to create context card'
            });
            return false;
          }
        },

        updateContextCard: async (cardId: string, updates: Partial<CreateContextCardRequest>) => {
          // TODO: Implement when backend API is available
          console.log('Update context card not yet implemented:', cardId, updates);
          return false;
        },

        deleteContextCard: async (cardId: string) => {
          const { activeSessionId, sessionToken } = get();

          if (!activeSessionId || !sessionToken) {
            throw new Error('No active session or session token available');
          }

          try {
            set({ isLoadingContextCards: true, contextCardError: null });

            await handleApiResponse<{ success: boolean; message: string }>(
              await fetch(buildApiUrl(API.SESSIONS.CONTEXT_CARD_DETAIL, { sessionId: activeSessionId, cardId }), {
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

            return true;
          } catch (error) {
            console.error('Failed to delete context card:', error);
            set({
              isLoadingContextCards: false,
              contextCardError: error instanceof Error ? error.message : 'Failed to delete context card'
            });
            return false;
          }
        },

        loadContextCards: async (sessionId: string) => {
          const { sessionToken } = get();

          try {
            set({ isLoadingContextCards: true, contextCardError: null });

            const cards = await handleApiResponse<ContextCard[]>(
              await fetch(buildApiUrl(API.SESSIONS.CONTEXT_CARDS, { sessionId }), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken || ''),
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
          } catch (error) {
            console.error('Failed to load context cards:', error);
            set({
              isLoadingContextCards: false,
              contextCardError: error instanceof Error ? error.message : 'Failed to load context cards'
            });
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
          const { sessionToken } = get();

          try {
            set({ isLoadingFileContext: true, fileContextError: null });

            const deps = await handleApiResponse<FileItem[]>(
              await fetch(buildApiUrl(API.SESSIONS.FILE_DEPS_SESSION, { sessionId }), {
                method: 'GET',
                headers: getAuthHeaders(sessionToken || ''),
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
          } catch (error) {
            console.error('Failed to load file dependencies:', error);
            set({
              isLoadingFileContext: false,
              fileContextError: error instanceof Error ? error.message : 'Failed to load file dependencies'
            });
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
          set({ activeSessionId: sessionId, error: null, sessionInitialized: true }),

        clearSession: () => {
          console.log('[SessionStore] Clearing session state');
          set({
            activeSessionId: null,
            currentSession: null,
            sessionContext: null,
            error: null,
            sessionInitialized: false,
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

        // ============================================================================
        // CHAT MESSAGE SENDING IMPLEMENTATION
        // ============================================================================

        sendChatMessage: async (message: string, contextCards?: string[], repository?: SelectedRepository) => {
          const { activeSessionId, sessionToken } = get();

          if (!activeSessionId || !sessionToken) {
            throw new Error('No active session or session token available');
          }

          try {
            set({ isLoadingMessages: true, messageError: null });

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

            const response = await handleApiResponse<ChatResponse>(
              await fetch(buildApiUrl(API.SESSIONS.CHAT, { sessionId: activeSessionId }), {
                method: 'POST',
                headers: getAuthHeaders(sessionToken),
                body: JSON.stringify(chatRequest),
              })
            );

            // Add the message to local state immediately
            const newMessage = {
              id: response.message_id ? (parseInt(response.message_id) || Date.now()) : Date.now(),
              message_id: response.message_id || `msg_${Date.now()}`,
              message_text: message,
              sender_type: 'user' as const,
              role: 'user' as const,
              tokens: 0, // Will be updated when message is processed
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            };

            get().addMessage(newMessage);

            set({ isLoadingMessages: false });
            return response;
          } catch (error) {
            console.error('Failed to send chat message:', error);
            set({
              isLoadingMessages: false,
              messageError: error instanceof Error ? error.message : 'Failed to send message'
            });
            return null;
          }
        },

        // ============================================================================
        // USER ISSUE CREATION IMPLEMENTATION
        // ============================================================================

        createIssueWithContext: async (request: CreateIssueWithContextRequest) => {
          const { sessionToken } = get();

          try {
            set({ isLoadingIssues: true, issueError: null });

            const { activeSessionId } = get();
            if (!activeSessionId) {
              throw new Error('No active session available');
            }

            const response = await handleApiResponse<IssueCreationResponse>(
              await fetch(buildApiUrl(API.SESSIONS.ISSUES.CREATE, { sessionId: activeSessionId }), {
                method: 'POST',
                headers: getAuthHeaders(sessionToken || ''),
                body: JSON.stringify(request),
              })
            );

            set({ isLoadingIssues: false });
            return response;
          } catch (error) {
            console.error('Failed to create issue with context:', error);
            set({
              isLoadingIssues: false,
              issueError: error instanceof Error ? error.message : 'Failed to create issue'
            });
            return null;
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
          const { sessionToken } = get();

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
          const { sessionToken, activeSessionId } = get();

          if (!activeSessionId) {
            throw new Error('No active session available');
          }

          const response = await handleApiResponse<CreateGitHubIssueResponse>(
            await fetch(buildApiUrl(API.SESSIONS.ISSUES.CREATE_GITHUB_ISSUE, { sessionId: activeSessionId, issueId }), {
              method: 'POST',
              headers: getAuthHeaders(sessionToken || ''),
            })
          );
          return response;
        },
      }),
      {
        name: 'session-storage',
        // Only persist certain parts of the state for security and performance
        partialize: (state) => ({
          // Auth state - persist session token and user info
          user: state.user,
          sessionToken: state.sessionToken,
          isAuthenticated: state.isAuthenticated,

          // Session state - persist session info but not full data
          activeSessionId: state.activeSessionId,
          currentSession: state.currentSession,
          selectedRepository: state.selectedRepository,
          sessionInitialized: state.sessionInitialized,

          // UI preferences
          activeTab: state.activeTab,
          sidebarCollapsed: state.sidebarCollapsed,
          sessionLoadingEnabled: state.sessionLoadingEnabled,

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
