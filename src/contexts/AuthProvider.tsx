import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User } from '../types';
import { ApiService } from '../services/api';

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

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    sessionToken: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Initialize auth state from URL parameters (OAuth callback)
  const initializeAuth = useCallback(async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      // Check for GitHub token in URL parameters (OAuth callback)
      const urlParams = new URLSearchParams(window.location.search);
      const githubToken = urlParams.get('github_token');
      const code = urlParams.get('code');

      if (githubToken) {
        // We have GitHub token from OAuth callback, create session
        try {
          const sessionData = await ApiService.createSession(githubToken);
          
          setAuthState({
            user: sessionData.user,
            sessionToken: sessionData.session_token,
            isAuthenticated: true,
            isLoading: false,
          });

          // Clear URL parameters after successful auth
          const newUrl = new URL(window.location.href);
          newUrl.search = '';
          window.history.replaceState({}, '', newUrl.toString());
          
        } catch (error) {
          console.warn('Session creation failed:', error);
          setAuthState({
            user: null,
            sessionToken: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      } else if (code) {
        // We have authorization code but no token yet, redirect to login
        console.warn('Authorization code received but no token, redirecting to login');
        window.location.href = '/auth/login';
      } else {
        // No auth data in URL, check if we're on a protected route
        const currentPath = window.location.pathname;
        if (currentPath.startsWith('/auth/callback')) {
          // We're on callback page but no auth data, redirect to login
          window.location.href = '/auth/login';
        } else {
          // Not on callback page, just set as not authenticated
          setAuthState(prev => ({ ...prev, isLoading: false }));
        }
      }
    } catch (error) {
      console.error('Auth initialization failed:', error);
      setAuthState({
        user: null,
        sessionToken: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  }, []);

  // Initialize on mount
  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  const login = async (): Promise<void> => {
    try {
      // Get login URL from backend and redirect
      const { login_url } = await ApiService.getLoginUrl();
      window.location.href = login_url;
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const logout = async (): Promise<void> => {
    try {
      if (authState.sessionToken) {
        await ApiService.logout(authState.sessionToken);
      }
    } catch (error) {
      console.warn('Logout API call failed:', error);
    } finally {
      // Always clear local state
      setAuthState({
        user: null,
        sessionToken: null,
        isAuthenticated: false,
        isLoading: false,
      });
      
      // Redirect to login page
      window.location.href = '/auth/login';
    }
  };

  const refreshAuth = async () => {
    await initializeAuth();
  };

  const contextValue: AuthContextValue = {
    ...authState,
    login,
    logout,
    refreshAuth
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};