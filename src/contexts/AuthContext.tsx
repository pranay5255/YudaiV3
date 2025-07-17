import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { AuthState } from '../types';
import { AuthService } from '../services/authService';

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

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

  // Initialize auth state on mount
  useEffect(() => {
    initializeAuth();
  }, []);

  // Handle OAuth callback on page load
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');

    if (code) {
      handleOAuthCallback(code, state || undefined);
    }
  }, []);

  const initializeAuth = async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      // Check if we have a stored token
      const storedToken = AuthService.getStoredToken();
      const storedUser = AuthService.getStoredUserData();

      if (storedToken && storedUser) {
        // Verify the token is still valid
        const statusCheck = await AuthService.checkAuthStatus();
        
        if (statusCheck.authenticated && statusCheck.user) {
          setAuthState({
            user: statusCheck.user,
            token: storedToken,
            isAuthenticated: true,
            isLoading: false,
          });
          
          // Update stored user data if it changed
          AuthService.storeUserData(statusCheck.user);
        } else {
          // Token is invalid, clear auth state
          clearAuthState();
        }
      } else {
        // No stored auth data
        setAuthState(prev => ({ 
          ...prev, 
          isLoading: false 
        }));
      }
    } catch (error) {
      console.error('Auth initialization failed:', error);
      clearAuthState();
    }
  };

  const handleOAuthCallback = async (code: string, state: string | null | undefined) => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      const loginResponse = await AuthService.handleCallback(code, state || undefined);
      
      setAuthState({
        user: loginResponse.user,
        token: loginResponse.access_token,
        isAuthenticated: true,
        isLoading: false,
      });

      // Store user data
      AuthService.storeUserData(loginResponse.user);

      // Clean up URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
    } catch (error) {
      console.error('OAuth callback failed:', error);
      clearAuthState();
    }
  };

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
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));
      await AuthService.logout();
      clearAuthState();
    } catch (error) {
      console.error('Logout failed:', error);
      // Still clear local state even if API call fails
      clearAuthState();
      throw error;
    }
  };

  const refreshAuth = async (): Promise<void> => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));
      
      const statusCheck = await AuthService.checkAuthStatus();
      
      if (statusCheck.authenticated && statusCheck.user) {
        setAuthState({
          user: statusCheck.user,
          token: AuthService.getStoredToken(),
          isAuthenticated: true,
          isLoading: false,
        });
        
        AuthService.storeUserData(statusCheck.user);
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

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 
