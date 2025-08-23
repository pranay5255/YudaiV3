import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { SelectedRepository, TabType, ContextCard, FileItem, ChatMessageAPI, GitHubRepository, User } from '../types';
import { ApiService } from '../services/api';
import { sessionApi } from '../services/sessionApi';

// Enhanced types for the session store with auth state
interface SessionState {
  // Controls whether session loading is enabled
  sessionLoadingEnabled: boolean;
  setSessionLoadingEnabled: (enabled: boolean) => void;
  // Auth state
  user: User | null;
  sessionToken: string | null;
  githubToken: string | null;
  isAuthenticated: boolean;
  authLoading: boolean;
  authError: string | null;
  
  // Core session state
  activeSessionId: string | null;
  isLoading: boolean;
  error: string | null;
  sessionInitialized: boolean;
  
  // Repository state
  selectedRepository: SelectedRepository | null;
  availableRepositories: GitHubRepository[];
  isLoadingRepositories: boolean;
  repositoryError: string | null;
  
  // UI state
  activeTab: TabType;
  sidebarCollapsed: boolean;
  
  // Session data (local cache)
  sessionData: {
    messages: ChatMessageAPI[];
    contextCards: ContextCard[];
    fileContext: FileItem[];
    totalTokens: number;
    lastUpdated: Date | null;
  };
  
  // Auth actions
  initializeAuth: () => Promise<void>;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  setAuthLoading: (loading: boolean) => void;
  setAuthError: (error: string | null) => void;
  
  // Session creation actions
  createSessionForRepository: (repository: SelectedRepository) => Promise<string | null>;
  ensureSessionExists: (sessionId: string) => Promise<boolean>;
  validatePersistedSession: () => Promise<void>;
  
  // Core actions
  setActiveSession: (sessionId: string) => void;
  clearSession: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSessionInitialized: (initialized: boolean) => void;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  setAvailableRepositories: (repositories: GitHubRepository[]) => void;
  setRepositoryLoading: (loading: boolean) => void;
  setRepositoryError: (error: string | null) => void;
  setActiveTab: (tab: TabType) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  
  // Session data actions
  addMessage: (message: ChatMessageAPI) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessageAPI>) => void;
  removeMessage: (messageId: string) => void;
  setMessages: (messages: ChatMessageAPI[]) => void;
  
  addContextCard: (card: ContextCard) => void;
  removeContextCard: (cardId: string) => void;
  setContextCards: (cards: ContextCard[]) => void;
  
  addFileItem: (file: FileItem) => void;
  removeFileItem: (fileId: string) => void;
  setFileContext: (files: FileItem[]) => void;
  
  updateSessionData: (data: Partial<SessionState['sessionData']>) => void;
}

// Create the session store with persistence
export const useSessionStore = create<SessionState>()(
  devtools(
    persist(
      (set, get) => ({
  // Controls whether session loading is enabled
  sessionLoadingEnabled: false,
  setSessionLoadingEnabled: (enabled: boolean) => set({ sessionLoadingEnabled: enabled }),
        // Auth state
        user: null,
        sessionToken: null,
        githubToken: null,
        isAuthenticated: false,
        authLoading: true,
        authError: null,
        
        // Initial state
        activeSessionId: null,
        isLoading: false,
        error: null,
        sessionInitialized: false,
        
        // Repository state
        selectedRepository: null,
        availableRepositories: [],
        isLoadingRepositories: false,
        repositoryError: null,
        
        // UI state
        activeTab: 'chat',
        sidebarCollapsed: false,
        
        // Session data
        sessionData: {
          messages: [],
          contextCards: [],
          fileContext: [],
          totalTokens: 0,
          lastUpdated: null,
        },
        
        // Auth actions
        initializeAuth: async () => {
          try {
            console.log('[SessionStore] Starting authentication initialization');
            console.log('[SessionStore] Current URL:', window.location.href);
            console.log('[SessionStore] Current pathname:', window.location.pathname);
            console.log('[SessionStore] Current search:', window.location.search);
            set({ authLoading: true, authError: null });

            // Check for session token in URL parameters (OAuth callback)
            const urlParams = new URLSearchParams(window.location.search);
            const sessionToken = urlParams.get('session_token');
            // const githubToken = urlParams.get('github_token');
            const userId = urlParams.get('user_id');
            const username = urlParams.get('username');
            const code = urlParams.get('code');

            if (sessionToken && userId && username) {
              // We have session token from OAuth callback, use the data directly from URL
              console.log('[SessionStore] Found session token in URL parameters, using callback data directly');
              
              // Extract user data from URL parameters (already provided by OAuth callback)
              const name = urlParams.get('name') || username;
              const email = urlParams.get('email') || '';
              const avatar = urlParams.get('avatar') || '';
              const githubId = urlParams.get('github_id') || '';
              
              // Create user object from callback data
              const user: User = {
                id: parseInt(userId),
                github_username: username,
                github_user_id: githubId,
                email: email,
                display_name: name,
                avatar_url: avatar,
                created_at: new Date().toISOString(),
                last_login: new Date().toISOString(),
              };
              
              console.log('[SessionStore] User data from callback:', user);
              
              set({
                user: user,
                sessionToken: sessionToken,
                githubToken: sessionToken, // No github_token in URL, but we have github_id
                isAuthenticated: true,
                authLoading: false,
                authError: null,
              });

              // Store session token in localStorage for persistence
              localStorage.setItem('session_token', sessionToken);
              
              // Clear any old persisted session that might be invalid
              get().clearSession();
              
              // Clear URL parameters after successful auth
              const newUrl = new URL(window.location.href);
              newUrl.search = '';
              window.history.replaceState({}, '', newUrl.toString());
              
              console.log('[SessionStore] Authentication completed successfully from callback');
            } else if (code) {
              // We have authorization code but no session token yet, redirect to login
              window.location.href = '/auth/login';
            } else {
              // No auth data in URL, check for stored session token
              console.log('[SessionStore] No auth data in URL, checking localStorage for stored tokens');
              const storedSessionToken = localStorage.getItem('session_token');
              const storedGithubToken = localStorage.getItem('github_token');
              console.log('[SessionStore] Stored session token:', storedSessionToken ? 'Found' : 'Not found');
              console.log('[SessionStore] Stored GitHub token:', storedGithubToken ? 'Found' : 'Not found');
              
              if (storedSessionToken) {
                console.log('[SessionStore] Found stored session token, validating...');
                try {
                  const userData = await ApiService.validateSessionToken(storedSessionToken);
                  const user: User = {
                    id: userData.id,
                    github_username: userData.github_username,
                    github_user_id: userData.github_id,
                    email: userData.email,
                    display_name: userData.display_name,
                    avatar_url: userData.avatar_url,
                    created_at: new Date().toISOString(),
                    last_login: new Date().toISOString(),
                  };
                  
                  set({
                    user: user,
                    sessionToken: storedSessionToken,
                    githubToken: storedGithubToken,
                    isAuthenticated: true,
                    authLoading: false,
                    authError: null,
                  });

                  // After successful auth, validate any persisted session
                  await get().validatePersistedSession();
                } catch (error) {
                  console.warn('[SessionStore] Stored session validation failed:', error);
                  console.error('[SessionStore] Stored session validation error details:', {
                    error: error instanceof Error ? error.message : error,
                    stack: error instanceof Error ? error.stack : undefined
                  });
                  localStorage.removeItem('session_token');
                  localStorage.removeItem('github_token');
                  
                  // Clear any persisted session state since auth failed
                  get().clearSession();
                  
                  set({
                    user: null,
                    sessionToken: null,
                    githubToken: null,
                    isAuthenticated: false,
                    authLoading: false,
                    authError: 'Stored session validation failed',
                  });
                }
              } else {
                // No stored token, check if we're on a protected route
                console.log('[SessionStore] No stored session token found');
                const currentPath = window.location.pathname;
                console.log('[SessionStore] Current path:', currentPath);
                if (currentPath.startsWith('/auth/callback') || currentPath.startsWith('/auth/success')) {
                  // We're on callback page but no auth data, redirect to login
                  console.log('[SessionStore] On callback page without auth data, redirecting to login');
                  window.location.href = '/auth/login';
                } else {
                  // Not on callback page, explicitly set as not authenticated
                  console.log('[SessionStore] Setting user as not authenticated');
                  
                  // Clear any persisted session state since not authenticated
                  get().clearSession();
                  
                  set({
                    user: null,
                    sessionToken: null,
                    githubToken: null,
                    isAuthenticated: false,
                    authLoading: false,
                    authError: null,
                  });
                }
              }
            }
            console.log('[SessionStore] Authentication initialization completed');
          } catch (error) {
            console.error('[SessionStore] Auth initialization failed:', error);
            console.error('[SessionStore] Auth initialization error details:', {
              error: error instanceof Error ? error.message : error,
              stack: error instanceof Error ? error.stack : undefined
            });
            
            // Clear any persisted session state since auth initialization failed
            get().clearSession();
            
            set({
              user: null,
              sessionToken: null,
              githubToken: null,
              isAuthenticated: false,
              authLoading: false,
              authError: 'Auth initialization failed',
            });
          }
        },

        login: async () => {
          try {
            set({ authLoading: true, authError: null });
            // Get login URL from backend and redirect
            const { login_url } = await ApiService.getLoginUrl();
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
              await ApiService.logout(sessionToken);
            }
          } catch (error) {
            console.warn('Logout API call failed:', error);
          } finally {
            // Always clear local state and storage
            localStorage.removeItem('session_token');
            localStorage.removeItem('github_token');
            set({
              user: null,
              sessionToken: null,
              githubToken: null,
              isAuthenticated: false,
              authLoading: false,
              authError: null,
              activeSessionId: null,
              error: null,
              sessionInitialized: false,
              sessionData: {
                messages: [],
                contextCards: [],
                fileContext: [],
                totalTokens: 0,
                lastUpdated: null,
              }
            });
            
            // Redirect to login page
            window.location.href = '/auth/login';
          }
        },

        refreshAuth: async () => {
          await get().initializeAuth();
        },

        setAuthLoading: (loading: boolean) =>
          set({ authLoading: loading }),

        setAuthError: (error: string | null) =>
          set({ authError: error }),

        // Session creation actions
          createSessionForRepository: async (repository: SelectedRepository) => {
            const { sessionLoadingEnabled, activeSessionId } = get();
            // If session loading is enabled and a session exists, try to load it
            if (sessionLoadingEnabled && activeSessionId) {
              const loaded = await get().ensureSessionExists(activeSessionId);
              if (loaded) {
                set({ isLoading: false });
                return activeSessionId;
              }
            }
          try {
            set({ isLoading: true, error: null });
            
            const { sessionToken } = get();
            if (!sessionToken) {
              throw new Error('No session token available');
            }

            const repoOwner = repository.repository.owner?.login || repository.repository.full_name.split('/')[0];
            const repoName = repository.repository.name;

            const sessionData = await sessionApi.createSession(
              {
                repo_owner: repoOwner,
                repo_name: repoName,
                repo_branch: repository.branch,
                title: `Chat - ${repoOwner}/${repoName}`,
              },
              sessionToken,
            );

            set({ 
              activeSessionId: sessionData.session_id,
              selectedRepository: repository,
              sessionInitialized: true,
              isLoading: false,
              error: null,
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
  ensureSessionExists: async (sessionId: string) => {
    const { sessionLoadingEnabled } = get();
    if (!sessionLoadingEnabled) return false;
    try {
      const { sessionToken } = get();
      if (!sessionToken) {
        console.warn('[SessionStore] No session token available for session validation');
        get().clearSession();
        return false;
      }

      // Try to get session context to verify it exists
      await sessionApi.getSessionContext(sessionId, sessionToken);

      set({
        activeSessionId: sessionId,
        sessionInitialized: true,
        error: null,
      });

      return true;
    } catch (error) {
      console.warn(`[SessionStore] Session ${sessionId} does not exist or is not accessible:`, error);

      // Check if it's a session not found error
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
            // Try to validate the persisted session
            await sessionApi.getSessionContext(activeSessionId, sessionToken);
            console.log(`[SessionStore] Persisted session ${activeSessionId} is valid`);
            
            // Session is valid, mark as initialized
            set({
              sessionInitialized: true,
              error: null,
            });
          } catch (error) {
            console.warn(`[SessionStore] Persisted session ${activeSessionId} is invalid:`, error);
            
            // Check if it's a session not found error
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
        
        // Core actions
        setActiveSession: (sessionId: string) =>
          set({ activeSessionId: sessionId, error: null, sessionInitialized: true }),
        
        clearSession: () => {
          console.log('[SessionStore] Clearing session state');
          set({
            activeSessionId: null,
            error: null,
            sessionInitialized: false,
            selectedRepository: null,
            sessionData: {
              messages: [],
              contextCards: [],
              fileContext: [],
              totalTokens: 0,
              lastUpdated: null,
            }
          });
        },
        
        setLoading: (loading: boolean) =>
          set({ isLoading: loading }),
        
        setError: (error: string | null) =>
          set({ error }),
        
        setSessionInitialized: (initialized: boolean) =>
          set({ sessionInitialized: initialized }),
        
        // Repository actions
        setSelectedRepository: (repository: SelectedRepository | null) =>
          set({ selectedRepository: repository, repositoryError: null }),
        
        setAvailableRepositories: (repositories: GitHubRepository[]) =>
          set({ availableRepositories: repositories }),
        
        setRepositoryLoading: (loading: boolean) =>
          set({ isLoadingRepositories: loading }),
        
        setRepositoryError: (error: string | null) =>
          set({ repositoryError: error }),
        
        // UI actions
        setActiveTab: (tab: TabType) =>
          set({ activeTab: tab }),
        
        setSidebarCollapsed: (collapsed: boolean) =>
          set({ sidebarCollapsed: collapsed }),
        
        // Message actions
        addMessage: (message: ChatMessageAPI) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages: [...state.sessionData.messages, message],
              totalTokens: state.sessionData.totalTokens + (message.tokens || 0),
              lastUpdated: new Date(),
            }
          })),
        
        updateMessage: (messageId: string, updates: Partial<ChatMessageAPI>) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages: state.sessionData.messages.map(msg => 
                msg.message_id === messageId ? { ...msg, ...updates } : msg
              ),
              lastUpdated: new Date(),
            }
          })),
        
        removeMessage: (messageId: string) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages: state.sessionData.messages.filter(msg => msg.message_id !== messageId),
              lastUpdated: new Date(),
            }
          })),
        
        setMessages: (messages: ChatMessageAPI[]) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages,
              totalTokens: messages.reduce((sum, msg) => sum + (msg.tokens || 0), 0),
              lastUpdated: new Date(),
            }
          })),
        
        // Context card actions
        addContextCard: (card: ContextCard) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              contextCards: [...state.sessionData.contextCards, card],
              totalTokens: state.sessionData.totalTokens + card.tokens,
              lastUpdated: new Date(),
            }
          })),
        
        removeContextCard: (cardId: string) =>
          set((state) => {
            const removedCard = state.sessionData.contextCards.find(c => c.id === cardId);
            return {
              sessionData: {
                ...state.sessionData,
                contextCards: state.sessionData.contextCards.filter(c => c.id !== cardId),
                totalTokens: state.sessionData.totalTokens - (removedCard?.tokens || 0),
                lastUpdated: new Date(),
              }
            };
          }),
        
        setContextCards: (cards: ContextCard[]) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              contextCards: cards,
              lastUpdated: new Date(),
            }
          })),
        
        // File context actions
        addFileItem: (file: FileItem) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              fileContext: [...state.sessionData.fileContext, file],
              totalTokens: state.sessionData.totalTokens + file.tokens,
              lastUpdated: new Date(),
            }
          })),
        
        removeFileItem: (fileId: string) =>
          set((state) => {
            const removedFile = state.sessionData.fileContext.find(f => f.id === fileId);
            return {
              sessionData: {
                ...state.sessionData,
                fileContext: state.sessionData.fileContext.filter(f => f.id !== fileId),
                totalTokens: state.sessionData.totalTokens - (removedFile?.tokens || 0),
                lastUpdated: new Date(),
              }
            };
          }),
        
        setFileContext: (files: FileItem[]) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              fileContext: files,
              lastUpdated: new Date(),
            }
          })),
        
        updateSessionData: (data: Partial<SessionState['sessionData']>) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              ...data,
              lastUpdated: new Date(),
            }
          })),
      }),
      {
        name: 'session-storage',
        // Only persist certain parts of the state
        partialize: (state) => ({
          activeSessionId: state.activeSessionId,
          selectedRepository: state.selectedRepository,
          activeTab: state.activeTab,
          sidebarCollapsed: state.sidebarCollapsed,
          sessionInitialized: state.sessionInitialized,
          // persist auth state
          user: state.user,
          sessionToken: state.sessionToken,
          isAuthenticated: state.isAuthenticated,
        }),
      }
    ),
    {
      name: 'session-store',
    }
  )
);



