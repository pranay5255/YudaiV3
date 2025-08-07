import { useSession } from '../contexts/SessionProvider';
import { UnifiedSessionState, TabState } from '../types';

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
  const session = useSession();
  return {
    // Session state
    sessionId: session.sessionId,
    session: session.session,
    repository: session.repository,
    branch: session.branch,
    repositoryInfo: session.repositoryInfo,
    messages: session.messages,
    isLoadingMessages: session.isLoadingMessages,
    messageRefreshKey: session.messageRefreshKey,
    contextCards: session.contextCards,
    fileContext: session.fileContext,
    totalTokens: session.totalTokens,
    userIssues: session.userIssues,
    currentIssue: session.currentIssue,
    agentStatus: session.agentStatus,
    agentHistory: session.agentHistory,
    statistics: session.statistics,
    isLoading: session.isLoading,
    error: session.error,
    lastUpdated: session.lastUpdated,
    connectionStatus: session.connectionStatus,
    
    // Tab state
    tabState: session.tabState,
    selectedRepository: session.selectedRepository,
    availableRepositories: session.availableRepositories,
    isLoadingRepositories: session.isLoadingRepositories,
    repositoryError: session.repositoryError,
  };
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