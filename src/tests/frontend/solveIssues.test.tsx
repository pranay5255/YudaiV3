import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { SolveIssues } from '@/components/SolveIssues';
import { useAuthStore } from '@/stores/authStore';
import { useSessionStore } from '@/stores/sessionStore';

const resetStores = () => {
  localStorage.clear();
  useAuthStore.getState().clearAuth();
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
    userIssues: [],
    currentIssue: null,
    isLoadingIssues: false,
    issueError: null,
    activeTab: 'solve',
    totalTokens: 0,
    lastActivity: null,
  });
};

describe('SolveIssues', () => {
  beforeEach(() => {
    resetStores();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetStores();
  });

  it('renders the empty repository state without triggering a render loop', () => {
    render(
      <StrictMode>
        <SolveIssues />
      </StrictMode>
    );

    expect(screen.getByText('No repository selected')).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});
