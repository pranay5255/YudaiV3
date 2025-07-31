import { useSession } from './useSession';
import { UnifiedSessionState } from '../types/unifiedState';
import { TabState } from '../types';

/**
 * Session state hooks
 * Extracted to separate file for better organization and Fast Refresh compatibility
 */

/**
 * Helper hook to get current session state without management functions
 * Useful for components that only need to read session data
 */
export const useSessionState = (): UnifiedSessionState => {
  const { sessionState } = useSession();
  return sessionState;
};

/**
 * Helper hook to get current tab state without management functions
 * Useful for components that only need to read tab data
 */
export const useTabState = (): TabState => {
  const { tabState } = useSession();
  return tabState;
};

/**
 * Helper hook to get real-time connection status
 * Useful for displaying connection indicators
 */
export const useConnectionStatus = (): 'connected' | 'disconnected' | 'reconnecting' => {
  const { connectionStatus } = useSession();
  return connectionStatus;
};