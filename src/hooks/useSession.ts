import { useContext } from 'react';
import { SessionContext, SessionContextValue } from '../contexts/SessionContext';

/**
 * Custom hook to access session context
 * Provides comprehensive session state management and real-time updates
 * 
 * @throws Error if used outside of SessionProvider
 * @returns SessionContextValue - Complete session management interface
 */
export const useSession = (): SessionContextValue => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};