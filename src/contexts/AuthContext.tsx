import { createContext } from 'react';
import { AuthState } from '../types';

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

 
