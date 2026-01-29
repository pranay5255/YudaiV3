import { useEffect } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useAuthStore } from '../stores/authStore';
import { logger } from '../utils/logger';

/**
 * Custom hook to access authentication state from the auth store
 */
export const useAuth = () => {
  const {
    user,
    sessionToken,
    isAuthenticated,
    isLoading,
    error: authError,
    initializeAuth,
    login,
    logout,
    refreshAuth,
    setAuthFromCallback,
  } = useAuthStore(
    useShallow((state) => ({
      user: state.user,
      sessionToken: state.sessionToken,
      isAuthenticated: state.isAuthenticated,
      isLoading: state.isLoading,
      error: state.error,
      initializeAuth: state.initializeAuth,
      login: state.login,
      logout: state.logout,
      refreshAuth: state.refreshAuth,
      setAuthFromCallback: state.setAuthFromCallback,
    }))
  );

  // Debug logging for auth state changes
  useEffect(() => {
    logger.info('[Auth] Auth state from auth store:', {
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
    refreshAuth,
    setAuthFromCallback,
  };
};

/**
 * Helper hook to get only authentication status (for components that don't need full auth context)
 */
export const useAuthStatus = () => {
  const { isAuthenticated, isLoading } = useAuth();
  return { isAuthenticated, isLoading };
};
