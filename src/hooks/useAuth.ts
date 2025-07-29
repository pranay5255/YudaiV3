import { useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { AuthState } from '../types';

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 