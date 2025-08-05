import React, { useEffect, useState, ReactNode, useCallback } from 'react';
import { AuthContext } from './AuthContext';
import { AuthService } from '../services/authService';
import { User } from '../types/unifiedState';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => void;
  refreshAuth: () => Promise<void>;
}

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Initialize auth state - simplified version
  const initializeAuth = useCallback(async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      const storedToken = AuthService.getStoredToken();
      const storedUser = AuthService.getStoredUserData();

      if (storedToken && storedUser) {
        // We have stored data, verify it's still valid
        try {
          const authCheck = await AuthService.verifyAuth();
          
          if (authCheck.authenticated && authCheck.user) {
            setAuthState({
              user: authCheck.user,
              token: storedToken,
              isAuthenticated: true,
              isLoading: false,
            });
          } else {
            // Invalid auth, clear it
            clearAuthState();
          }
        } catch (error) {
          console.warn('Auth verification failed, clearing auth:', error);
          clearAuthState();
        }
      } else {
        // No stored auth
        setAuthState(prev => ({ ...prev, isLoading: false }));
      }
    } catch (error) {
      console.error('Auth initialization failed:', error);
      clearAuthState();
    }
  }, []);

  // Initialize on mount
  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  const login = async (): Promise<void> => {
    try {
      await AuthService.login();
      // Note: This will redirect to GitHub, so execution won't continue here
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const logout = (): void => {
    AuthService.logout();
    clearAuthState();
    // AuthService.logout() already redirects to home
  };

  const refreshAuth = async (): Promise<void> => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));
      
      const authCheck = await AuthService.verifyAuth();
      
      if (authCheck.authenticated && authCheck.user) {
        setAuthState({
          user: authCheck.user,
          token: AuthService.getStoredToken(),
          isAuthenticated: true,
          isLoading: false,
        });
      } else {
        clearAuthState();
      }
    } catch (error) {
      console.error('Auth refresh failed:', error);
      clearAuthState();
      throw error;
    }
  };

  const clearAuthState = () => {
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
  };

  const contextValue: AuthContextValue = {
    ...authState,
    login,
    logout,
    refreshAuth,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};