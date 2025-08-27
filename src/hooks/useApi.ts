import { useCallback, useMemo } from 'react';
import { ApiService } from '../services/api';
import { sessionApi } from '../services/sessionApi';
import { useAuth } from './useAuth';

/**
 * Centralized API hook for consistent service access across components
 * Provides authenticated API calls with automatic token management
 */
export const useApi = () => {
  const { sessionToken } = useAuth();

  // Wrap ApiService methods to automatically include session token
  const api = useCallback(() => {
    return {
      // Auth methods
      validateSessionToken: ApiService.validateSessionToken,
      logout: (token?: string) => ApiService.logout(token || sessionToken || ''),
      getLoginUrl: ApiService.getLoginUrl,

      // Session management methods
      createSession: (request: Parameters<typeof sessionApi.createSession>[0]) =>
        sessionApi.createSession(request, sessionToken || undefined),
      getSessionContext: (sessionId: string) =>
        sessionApi.getSessionContext(sessionId, sessionToken || undefined),


      // Chat methods
      sendChatMessage: (request: Parameters<typeof ApiService.sendChatMessage>[0]) =>
        ApiService.sendChatMessage(request, sessionToken || undefined),


      // Issue management methods
      createIssueWithContext: (request: Parameters<typeof ApiService.createIssueWithContext>[0]) =>
        ApiService.createIssueWithContext(request, sessionToken || undefined),
      getIssues: (repoOwner?: string, repoName?: string, limit?: number) =>
        ApiService.getIssues(repoOwner, repoName, limit, sessionToken || undefined),


      // Repository methods
      getRepositories: () =>
        ApiService.getRepositories(sessionToken || undefined),

      getUserRepositories: () =>
        ApiService.getUserRepositories(sessionToken || undefined),
      getRepositoryBranches: (owner: string, repo: string) =>
        ApiService.getRepositoryBranches(owner, repo, sessionToken || undefined),

      // Chat Messages CRUD methods
      getChatMessages: (sessionId: string, limit?: number) =>
        sessionApi.getChatMessages(sessionId, limit, sessionToken || undefined),


      // Context Cards CRUD methods
      addContextCard: (sessionId: string, request: Parameters<typeof sessionApi.addContextCard>[1]) =>
        sessionApi.addContextCard(sessionId, request, sessionToken || undefined),
      getContextCards: (sessionId: string) =>
        sessionApi.getContextCards(sessionId, sessionToken || undefined),
      deleteContextCard: (sessionId: string, cardId: number) =>
        sessionApi.deleteContextCard(sessionId, cardId, sessionToken || undefined),

      // File Dependencies CRUD methods

      getFileDependenciesSession: (sessionId: string) =>
        sessionApi.getFileDependenciesSession(sessionId, sessionToken || undefined),
      extractFileDependenciesForSession: (sessionId: string, repoUrl: string) =>
        sessionApi.extractFileDependenciesForSession(sessionId, repoUrl, sessionToken || undefined),


      // GitHub integration methods
      createGitHubIssueFromUserIssue: (issueId: string) =>
        ApiService.createGitHubIssueFromUserIssue(issueId, sessionToken || undefined),

    };
  }, [sessionToken]);

  // Use useMemo to stabilize the returned object and prevent infinite loops
  // This ensures the API object only changes when sessionToken changes
  return useMemo(() => api(), [api]);
};