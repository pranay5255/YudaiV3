import React, { useEffect, useState, ReactNode, useCallback } from 'react';
import { AuthContext } from './AuthContext';
import { AuthService } from '../services/authService';
import { User } from '../types/unifiedState';

interface AuthState {
  user: User | null;
  sessionToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    sessionToken: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Initialize auth state - simplified version
  const initializeAuth = useCallback(async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      const storedSessionToken = AuthService.getStoredSessionToken();
      const storedUser = AuthService.getStoredUserData();

      if (storedSessionToken && storedUser) {
        // We have stored data, verify it's still valid
        try {
          const authCheck = await AuthService.verifyAuth();
          
          if (authCheck.authenticated && authCheck.user) {
            setAuthState({
              user: authCheck.user,
              sessionToken: storedSessionToken,
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

  // Add periodic token validation (every 5 minutes)
  useEffect(() => {
    const interval = setInterval(async () => {
      if (authState.isAuthenticated && authState.sessionToken) {
        const isValid = await AuthService.refreshTokenIfNeeded();
        if (!isValid) {
          console.warn('Session token validation failed, clearing auth state');
          clearAuthState();
        }
      }
    }, 5 * 60 * 1000); // Check every 5 minutes
    
    return () => clearInterval(interval);
  }, [authState.isAuthenticated, authState.sessionToken]);

  const login = async (): Promise<void> => {
    try {
      await AuthService.login();
      // Note: This will redirect to GitHub, so execution won't continue here
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const logout = async (): Promise<void> => {
    await AuthService.logout();
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
          sessionToken: AuthService.getStoredSessionToken(),
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
      sessionToken: null,
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