import { useContext } from 'react';
import { AuthContext, AuthContextValue } from '../contexts/AuthProvider';

/**
 * Custom hook to access authentication state and methods
 * Must be used within an AuthProvider
 */
export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

/**
 * Helper hook to get only authentication status (for components that don't need full auth context)
 */
export const useAuthStatus = (): { isAuthenticated: boolean; isLoading: boolean } => {
  const { isAuthenticated, isLoading } = useAuth();
  return { isAuthenticated, isLoading };
};