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
      getUserSessions: () => sessionApi.getUserSessions(sessionToken || undefined),
      updateSession: (sessionId: string, updates: Parameters<typeof sessionApi.updateSession>[1]) =>
        sessionApi.updateSession(sessionId, updates, sessionToken || undefined),
      deleteSession: (sessionId: string) =>
        sessionApi.deleteSession(sessionId, sessionToken || undefined),

      // Chat methods
      sendChatMessage: (request: Parameters<typeof ApiService.sendChatMessage>[0]) =>
        ApiService.sendChatMessage(request, sessionToken || undefined),
      createIssueFromChat: (request: Parameters<typeof ApiService.createIssueFromChat>[0]) =>
        ApiService.createIssueFromChat(request, sessionToken || undefined),

      // Issue management methods
      createIssueWithContext: (request: Parameters<typeof ApiService.createIssueWithContext>[0]) =>
        ApiService.createIssueWithContext(request, sessionToken || undefined),
      getIssues: (repoOwner?: string, repoName?: string, limit?: number) =>
        ApiService.getIssues(repoOwner, repoName, limit, sessionToken || undefined),
      getIssue: (issueId: string) =>
        ApiService.getIssue(issueId, sessionToken || undefined),
      updateIssue: (issueId: string, updates: Parameters<typeof ApiService.updateIssue>[1]) =>
        ApiService.updateIssue(issueId, updates, sessionToken || undefined),
      deleteIssue: (issueId: string) =>
        ApiService.deleteIssue(issueId, sessionToken || undefined),

      // Repository methods
      getRepositories: () =>
        ApiService.getRepositories(sessionToken || undefined),
      getRepository: (owner: string, name: string) =>
        ApiService.getRepository(owner, name, sessionToken || undefined),
      getUserRepositories: () =>
        ApiService.getUserRepositories(sessionToken || undefined),
      getRepositoryBranches: (owner: string, repo: string) =>
        ApiService.getRepositoryBranches(owner, repo, sessionToken || undefined),

      // Chat Messages CRUD methods
      addChatMessage: (sessionId: string, request: Parameters<typeof sessionApi.addChatMessage>[1]) =>
        sessionApi.addChatMessage(sessionId, request, sessionToken || undefined),
      getChatMessages: (sessionId: string, limit?: number) =>
        sessionApi.getChatMessages(sessionId, limit, sessionToken || undefined),
      updateChatMessage: (
        sessionId: string,
        messageId: string,
        updates: Parameters<typeof sessionApi.updateChatMessage>[2],
      ) => sessionApi.updateChatMessage(sessionId, messageId, updates, sessionToken || undefined),
      deleteChatMessage: (sessionId: string, messageId: string) =>
        sessionApi.deleteChatMessage(sessionId, messageId, sessionToken || undefined),

      // Context Cards CRUD methods
      addContextCard: (sessionId: string, request: Parameters<typeof sessionApi.addContextCard>[1]) =>
        sessionApi.addContextCard(sessionId, request, sessionToken || undefined),
      getContextCards: (sessionId: string) =>
        sessionApi.getContextCards(sessionId, sessionToken || undefined),
      deleteContextCard: (sessionId: string, cardId: number) =>
        sessionApi.deleteContextCard(sessionId, cardId, sessionToken || undefined),

      // File Dependencies CRUD methods
      addFileDependency: (sessionId: string, request: Parameters<typeof sessionApi.addFileDependency>[1]) =>
        sessionApi.addFileDependency(sessionId, request, sessionToken || undefined),
      getFileDependenciesSession: (sessionId: string) =>
        sessionApi.getFileDependenciesSession(sessionId, sessionToken || undefined),
      extractFileDependenciesForSession: (sessionId: string, repoUrl: string) =>
        sessionApi.extractFileDependenciesForSession(sessionId, repoUrl, sessionToken || undefined),
      deleteFileDependency: (sessionId: string, fileId: number) =>
        sessionApi.deleteFileDependency(sessionId, fileId, sessionToken || undefined),

      // GitHub integration methods
      createGitHubIssueFromUserIssue: (issueId: string) =>
        ApiService.createGitHubIssueFromUserIssue(issueId, sessionToken || undefined),
    };
  }, [sessionToken]);

  // Use useMemo to stabilize the returned object and prevent infinite loops
  // This ensures the API object only changes when sessionToken changes
  return useMemo(() => api(), [api]);
};