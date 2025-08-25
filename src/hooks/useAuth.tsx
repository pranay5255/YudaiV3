import { useEffect } from 'react';
import { useSessionStore } from '../stores/sessionStore';

/**
 * Custom hook to access authentication state from the session store
 */
export const useAuth = () => {
  const { 
    user, 
    sessionToken,
    isAuthenticated, 
    authLoading: isLoading, 
    authError,
    initializeAuth,
    login,
    logout,
    refreshAuth 
  } = useSessionStore();

  // Debug logging for auth state changes
  useEffect(() => {
    console.log('[useAuth] Auth state from session store:', {
      isAuthenticated,
      isLoading,
      hasUser: !!user,
      hasSessionToken: !!sessionToken,
      authError,
      timestamp: new Date().toISOString()
    });
  }, [isAuthenticated, isLoading, user, sessionToken, authError]);

  // Note: /auth/success route is now handled by the AuthSuccess component with React Router

  return {
    user,
    sessionToken,
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