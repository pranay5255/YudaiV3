import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Chat } from '../src/components/Chat';
import { useAuthStore } from '../src/stores/authStore';
import { useSessionStore } from '../src/stores/sessionStore';
import type { ChatMessage, SelectedRepository } from '../src/types/sessionTypes';

const selectedRepository: SelectedRepository = {
  repository: {
    id: 1,
    name: 'repo',
    full_name: 'owner/repo',
    private: false,
    html_url: 'https://github.com/owner/repo',
    owner: {
      login: 'owner',
      id: 1,
      avatar_url: 'https://example.com/avatar.png',
      html_url: 'https://github.com/owner',
    },
  },
  branch: 'main',
};

const mockUser = {
  id: 1,
  github_username: 'owner',
  github_user_id: '1',
  email: 'owner@example.com',
  display_name: 'Owner',
  avatar_url: 'https://example.com/avatar.png',
  created_at: new Date().toISOString(),
  last_login: new Date().toISOString(),
};

const resetStores = () => {
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
    selectedRepository: null,
    availableRepositories: [],
    isLoadingRepositories: false,
    repositoryError: null,
    messages: [],
    isLoadingMessages: false,
    messageError: null,
    contextCards: [],
    isLoadingContextCards: false,
    contextCardError: null,
    fileContext: [],
    isLoadingFileContext: false,
    fileContextError: null,
    userIssues: [],
    currentIssue: null,
    isLoadingIssues: false,
    issueError: null,
    agentStatus: null,
    agentHistory: [],
    activeTab: 'chat',
    sidebarCollapsed: false,
    sessionLoadingEnabled: false,
    indexCodebaseEnabled: true,
    totalTokens: 0,
    lastActivity: null,
    connectionStatus: 'disconnected',
  });

  const persisted = useSessionStore as unknown as {
    persist?: { clearStorage?: () => void };
  };
  persisted.persist?.clearStorage?.();
  window.localStorage.clear();
};

describe('Chat Flow Invariants', () => {
  beforeEach(() => {
    resetStores();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps send disabled while session is not ready', () => {
    useSessionStore.setState({
      selectedRepository,
      activeSessionId: null,
      sessionStatus: 'awaiting_session',
    });

    render(<Chat />);

    expect(screen.getByText('Preparing Session')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Preparing session...')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  });

  it('throws when sending without an active session', async () => {
    useAuthStore.setState({
      user: mockUser,
      sessionToken: 'token',
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    await expect(useSessionStore.getState().sendChatMessage('hello')).rejects.toThrow(
      'No active session or session token available'
    );
  });

  it('shows assistant response immediately after successful chat POST', async () => {
    const now = new Date().toISOString();
    const backendMessages: ChatMessage[] = [
      {
        id: 11,
        message_id: 'msg-user-1',
        message_text: 'hello from test',
        sender_type: 'user',
        role: 'user',
        tokens: 4,
        created_at: now,
        updated_at: now,
      },
      {
        id: 12,
        message_id: 'msg-assistant-1',
        message_text: 'Mock assistant reply',
        sender_type: 'assistant',
        role: 'assistant',
        tokens: 5,
        created_at: now,
        updated_at: now,
      },
    ];

    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            reply: 'Mock assistant reply',
            conversation: [],
            message_id: 'msg-assistant-1',
            processing_time: 0.2,
            session_id: 'sess-1',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(backendMessages), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    vi.stubGlobal('fetch', fetchMock);

    useAuthStore.setState({
      user: mockUser,
      sessionToken: 'token',
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });

    useSessionStore.setState({
      selectedRepository,
      activeSessionId: 'sess-1',
      sessionStatus: 'ready',
      messages: [],
    });

    const user = userEvent.setup();
    render(<Chat />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'hello from test');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Mock assistant reply')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
  });
});
