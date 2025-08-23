import { useSessionStore } from '../stores/sessionStore';

/**
 * Custom hook to access authentication state and methods from the session store
 * This replaces the AuthProvider and makes the session store the sole source of truth
 */
export const useAuth = () => {
  const {
    user,
    sessionToken,
    githubToken,
    isAuthenticated,
    authLoading,
    authError,
    initializeAuth,
    login,
    logout,
    refreshAuth,
    setAuthLoading,
    setAuthError,
  } = useSessionStore();

  return {
    user,
    sessionToken,
    githubToken,
    isAuthenticated,
    isLoading: authLoading,
    error: authError,
    login,
    logout,
    refreshAuth,
    initializeAuth,
    setAuthLoading,
    setAuthError,
  };
};

/**
 * Helper hook to get only authentication status (for components that don't need full auth context)
 */
export const useAuthStatus = () => {
  const { isAuthenticated, isLoading } = useAuth();
  return { isAuthenticated, isLoading };
};