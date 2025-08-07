import React, { createContext, useState, useEffect, useCallback } from 'react';
import { User, AuthState } from '../types';
import { ApiService } from '../services/api';

export interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

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

      // Check for session token in URL parameters (OAuth callback)
      const urlParams = new URLSearchParams(window.location.search);
      const sessionToken = urlParams.get('session_token');
      const userId = urlParams.get('user_id');
      const username = urlParams.get('username');
      const code = urlParams.get('code');

      if (sessionToken && userId && username) {
        // We have session token from OAuth callback, validate it
        try {
          const userData = await ApiService.validateSessionToken(sessionToken);
          
          // Transform userData to match User type with proper field mapping
          const user: User = {
            id: userData.id,
            github_username: userData.github_username,
            github_user_id: userData.github_id, // Map github_id to github_user_id
            email: userData.email,
            display_name: userData.display_name,
            avatar_url: userData.avatar_url,
            created_at: new Date().toISOString(),
            last_login: new Date().toISOString(),
          };
          
          setAuthState({
            user: user,
            sessionToken: sessionToken,
            isAuthenticated: true,
            isLoading: false,
          });

          // Store session token in localStorage for persistence
          localStorage.setItem('session_token', sessionToken);

          // Clear URL parameters after successful auth
          const newUrl = new URL(window.location.href);
          newUrl.search = '';
          window.history.replaceState({}, '', newUrl.toString());
          
        } catch (error) {
          console.warn('Session validation failed:', error);
          // Clear any stored token on validation failure
          localStorage.removeItem('session_token');
          setAuthState({
            user: null,
            sessionToken: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      } else if (code) {
        // We have authorization code but no session token yet, redirect to login
        console.warn('Authorization code received but no session token, redirecting to login');
        window.location.href = '/auth/login';
      } else {
        // No auth data in URL, check for stored session token
        const storedToken = localStorage.getItem('session_token');
        if (storedToken) {
          try {
            const userData = await ApiService.validateSessionToken(storedToken);
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
            
            setAuthState({
              user: user,
              sessionToken: storedToken,
              isAuthenticated: true,
              isLoading: false,
            });
          } catch (error) {
            console.warn('Stored session validation failed:', error);
            localStorage.removeItem('session_token');
            setAuthState(prev => ({ ...prev, isLoading: false }));
          }
        } else {
          // No stored token, check if we're on a protected route
          const currentPath = window.location.pathname;
          if (currentPath.startsWith('/auth/callback')) {
            // We're on callback page but no auth data, redirect to login
            window.location.href = '/auth/login';
          } else {
            // Not on callback page, just set as not authenticated
            setAuthState(prev => ({ ...prev, isLoading: false }));
          }
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
      // Always clear local state and storage
      localStorage.removeItem('session_token');
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

