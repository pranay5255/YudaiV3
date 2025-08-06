import { useSession } from './useSession';
import { UnifiedSessionState } from '../types/unifiedState';
import { TabState } from '../types';

/**
 * Simplified session state hooks.
 * Provides basic session state access.
 * Session management is not implemented as per requirements.
 */

/**
 * Helper hook to get current session state
 * Useful for components that only need to read session data
 */
export const useSessionState = (): UnifiedSessionState => {
  const { sessionState } = useSession();
  return sessionState;
};

/**
 * Helper hook to get current tab state
 * Useful for components that only need to read tab data
 */
export const useTabState = (): TabState => {
  const { tabState } = useSession();
  return tabState;
};

/**
 * Helper hook to get connection status
 * Simplified since session management is not implemented
 */
export const useConnectionStatus = (): 'connected' | 'disconnected' | 'reconnecting' => {
  const { connectionStatus } = useSession();
  return connectionStatus;
};