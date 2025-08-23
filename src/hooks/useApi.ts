import { useCallback, useMemo } from 'react';
import { ApiService } from '../services/api';
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
      createSession: (request: Parameters<typeof ApiService.createSession>[0]) =>
        ApiService.createSession(request, sessionToken || undefined),
      getSessionContext: (sessionId: string) =>
        ApiService.getSessionContext(sessionId, sessionToken || undefined),
      getUserSessions: () =>
        ApiService.getUserSessions(sessionToken || undefined),
      updateSession: (sessionId: string, updates: Parameters<typeof ApiService.updateSession>[1]) =>
        ApiService.updateSession(sessionId, updates, sessionToken || undefined),
      deleteSession: (sessionId: string) =>
        ApiService.deleteSession(sessionId, sessionToken || undefined),

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
      addChatMessage: (sessionId: string, request: Parameters<typeof ApiService.addChatMessage>[1]) =>
        ApiService.addChatMessage(sessionId, request, sessionToken || undefined),
      getChatMessages: (sessionId: string, limit?: number) =>
        ApiService.getChatMessages(sessionId, limit, sessionToken || undefined),
      updateChatMessage: (sessionId: string, messageId: string, updates: Parameters<typeof ApiService.updateChatMessage>[2]) =>
        ApiService.updateChatMessage(sessionId, messageId, updates, sessionToken || undefined),
      deleteChatMessage: (sessionId: string, messageId: string) =>
        ApiService.deleteChatMessage(sessionId, messageId, sessionToken || undefined),

      // Context Cards CRUD methods
      addContextCard: (sessionId: string, request: Parameters<typeof ApiService.addContextCard>[1]) =>
        ApiService.addContextCard(sessionId, request, sessionToken || undefined),
      getContextCards: (sessionId: string) =>
        ApiService.getContextCards(sessionId, sessionToken || undefined),
      deleteContextCard: (sessionId: string, cardId: number) =>
        ApiService.deleteContextCard(sessionId, cardId, sessionToken || undefined),

      // File Dependencies CRUD methods
      addFileDependency: (sessionId: string, request: Parameters<typeof ApiService.addFileDependency>[1]) =>
        ApiService.addFileDependency(sessionId, request, sessionToken || undefined),
      getFileDependenciesSession: (sessionId: string) =>
        ApiService.getFileDependenciesSession(sessionId, sessionToken || undefined),
      extractFileDependenciesForSession: (sessionId: string, repoUrl: string) =>
        ApiService.extractFileDependenciesForSession(sessionId, repoUrl, sessionToken || undefined),
      deleteFileDependency: (sessionId: string, fileId: number) =>
        ApiService.deleteFileDependency(sessionId, fileId, sessionToken || undefined),

      // GitHub integration methods
      createGitHubIssueFromUserIssue: (issueId: string) =>
        ApiService.createGitHubIssueFromUserIssue(issueId, sessionToken || undefined),
    };
  }, [sessionToken]);

  // Use useMemo to stabilize the returned object and prevent infinite loops
  // This ensures the API object only changes when sessionToken changes
  return useMemo(() => api(), [api]);
};