import { UnifiedSessionState } from '../types/unifiedState';

/**
 * Session utility functions
 * Extracted to fix React Fast Refresh warnings
 */

// Storage keys for persistent state
export const STORAGE_KEYS = {
  SESSION_STATE: 'yudai_session_state',
  TAB_STATE: 'yudai_tab_state',
  CONNECTION_STATE: 'yudai_connection_state'
} as const;

/**
 * Helper hook to get current session state without management functions
 * Useful for components that only need to read session data
 */
export const getSessionState = (sessionState: UnifiedSessionState): UnifiedSessionState => {
  return sessionState;
};

/**
 * Helper function to get current tab state without management functions
 * Useful for components that only need to read tab data
 */
export const getTabState = (tabState: unknown): unknown => {
  return tabState;
};

/**
 * Helper function to get real-time connection status
 * Useful for displaying connection indicators
 */
export const getConnectionStatus = (connectionStatus: 'connected' | 'disconnected' | 'reconnecting'): 'connected' | 'disconnected' | 'reconnecting' => {
  return connectionStatus;
};