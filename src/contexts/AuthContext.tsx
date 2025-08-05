import { createContext } from 'react';
import { User } from '../types/unifiedState';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => void;  // Simplified: no need for async logout
  refreshAuth: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
