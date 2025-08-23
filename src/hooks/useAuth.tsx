import { useSessionStore } from '../stores/sessionStore';

/**
 * Custom hook to access authentication state from the session store
 */
export const useAuth = () => {
  const { 
    user, 
    isAuthenticated, 
    authLoading: isLoading, 
    authError,
    initializeAuth,
    login,
    logout,
    refreshAuth 
  } = useSessionStore();

  return {
    user,
    isAuthenticated,
    isLoading,
    authError,
    initializeAuth,
    login,
    logout,
    refreshAuth
  };
};

/**
 * Helper hook to get only authentication status (for components that don't need full auth context)
 */
export const useAuthStatus = () => {
  const { isAuthenticated, isLoading } = useAuth();
  return { isAuthenticated, isLoading };
};