import { useShallow } from 'zustand/react/shallow';
import { useAuthStore } from '../stores/authStore';

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
    clearAuth,
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
      clearAuth: state.clearAuth,
    }))
  );

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
    clearAuth,
  };
};

/**
 * Helper hook to get only authentication status (for components that don't need full auth context)
 */
export const useAuthStatus = () => {
  const { isAuthenticated, isLoading } = useAuth();
  return { isAuthenticated, isLoading };
};
