import { useCallback } from 'react';
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
      createSession: ApiService.createSession,
      validateSessionToken: ApiService.validateSessionToken,
      logout: (token?: string) => ApiService.logout(token || sessionToken || ''),
      getLoginUrl: ApiService.getLoginUrl,

      // Session management methods
      getSessionContext: (sessionId: string) =>
        ApiService.getSessionContext(sessionId, sessionToken || undefined),

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

      // File dependencies methods
      analyzeFileDependencies: (files: File[]) =>
        ApiService.analyzeFileDependencies(files, sessionToken || undefined),
      getFileDependencies: (fileId: string) =>
        ApiService.getFileDependencies(fileId, sessionToken || undefined),
      extractFileDependencies: (repoUrl: string) =>
        ApiService.extractFileDependencies(repoUrl, sessionToken || undefined),

      // GitHub integration methods
      createGitHubIssueFromUserIssue: (issueId: string) =>
        ApiService.createGitHubIssueFromUserIssue(issueId, sessionToken || undefined),
    };
  }, [sessionToken]);

  return api();
};