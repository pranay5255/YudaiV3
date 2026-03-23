import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { AuthSuccess } from '@/components/AuthSuccess';
import { useAuthStore } from '@/stores/authStore';
import { useSessionStore } from '@/stores/sessionStore';

const resetStores = () => {
  localStorage.clear();
  useAuthStore.setState({
    user: null,
    sessionToken: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });
  useSessionStore.setState({
    activeSessionId: null,
    currentSession: null,
    sessionContext: null,
    isLoading: false,
    error: null,
    sessionInitialized: false,
    sessionStatus: 'no_repo',
    runtime: null,
    runtimeStatus: 'not_provisioned',
    runtimeError: null,
    selectedRepository: null,
    availableRepositories: [],
    isLoadingRepositories: false,
    repositoryError: null,
    messages: [],
    isLoadingMessages: false,
    messageError: null,
    contextCards: [],
    fileContext: [],
    userIssues: [],
    currentIssue: null,
    isLoadingIssues: false,
    issueError: null,
    activeTab: 'solve',
    totalTokens: 0,
    lastActivity: null,
  });
};

describe('AuthSuccess', () => {
  beforeEach(() => {
    resetStores();
    window.history.pushState(
      {},
      '',
      '/auth/success?session_token=test-token&user_id=1&username=tester&name=Tester&email=tester%40example.com'
    );
  });

  afterEach(() => {
    cleanup();
    resetStores();
  });

  it('resets the app to the chat tab after processing OAuth callback data', async () => {
    render(
      <MemoryRouter>
        <AuthSuccess />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(useAuthStore.getState().sessionToken).toBe('test-token');
    });

    expect(useSessionStore.getState().activeTab).toBe('chat');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });
});
