import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuthStore } from '@/stores/authStore';
import { useSessionStore } from '@/stores/sessionStore';
import type {
  ChatResponse,
  CreateIssueWithContextRequest,
  IssueCreationResponse,
  SelectedRepository,
  Session,
  SessionContext,
} from '@/types/sessionTypes';

const mockRepository: SelectedRepository = {
  repository: {
    id: 1,
    name: 'yudaiv3',
    full_name: 'octocat/yudaiv3',
    private: false,
    html_url: 'https://github.com/octocat/yudaiv3',
    default_branch: 'main',
    owner: {
      login: 'octocat',
      id: 7,
    },
  },
  branch: 'main',
};

const baseSession: Session = {
  id: 1,
  session_id: 'session_123',
  title: 'Chat - octocat/yudaiv3',
  repo_owner: 'octocat',
  repo_name: 'yudaiv3',
  repo_branch: 'main',
  repo_url: 'https://github.com/octocat/yudaiv3.git',
  is_active: true,
  total_messages: 0,
  total_tokens: 0,
  created_at: new Date().toISOString(),
};

const sessionContext: SessionContext = {
  session: baseSession,
  messages: [],
  context_cards: [],
  file_embeddings_count: 0,
  statistics: {
    total_messages: 0,
    total_tokens: 0,
    total_cost: 0,
    session_duration: 0,
  },
  user_issues: [],
  file_embeddings: [],
};

const issueRequest: CreateIssueWithContextRequest = {
  title: 'Fix onboarding flow',
  description: 'The onboarding state never completes.',
  chat_messages: [],
  file_context: [],
};

const issueResponse: IssueCreationResponse = {
  success: true,
  preview_only: true,
  github_preview: {
    title: 'Fix onboarding flow',
    body: 'The onboarding state never completes.',
    labels: ['bug'],
    assignees: [],
    metadata: {
      chat_messages_count: 0,
      files_context_count: 0,
      total_tokens: 0,
      generated_at: new Date().toISOString(),
      generation_method: 'test',
    },
  },
  message: 'Preview ready',
};

const chatResponse: ChatResponse = {
  reply: 'Here is a plan.',
  conversation: [['hello', 'Here is a plan.']],
  message_id: 'assistant_1',
  processing_time: 0.5,
  session_id: 'session_123',
};

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

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
    messages: [],
    isLoadingMessages: false,
    messageError: null,
    contextCards: [],
    fileContext: [],
    userIssues: [],
    currentIssue: null,
    isLoadingIssues: false,
    issueError: null,
    totalTokens: 0,
    lastActivity: null,
  });
  useAuthStore.setState({
    user: {
      id: 1,
      github_username: 'tester',
      github_user_id: '1',
      email: 'tester@example.com',
      display_name: 'Tester',
      created_at: new Date().toISOString(),
      last_login: new Date().toISOString(),
    },
    sessionToken: 'test-token',
    isAuthenticated: true,
    isLoading: false,
    error: null,
  });
};

describe('sessionStore runtime split', () => {
  beforeEach(() => {
    resetStores();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetStores();
  });

  it('creates a session without auto-provisioning a runtime', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(baseSession));

    const sessionId = await useSessionStore.getState().createSessionForRepository(mockRepository);

    expect(sessionId).toBe('session_123');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/daifu/sessions');

    const state = useSessionStore.getState();
    expect(state.sessionStatus).toBe('ready');
    expect(state.runtime).toBeNull();
    expect(state.runtimeStatus).toBe('not_provisioned');
    expect(state.runtimeError).toBeNull();
    expect(state.currentSession?.runtime_id).toBeUndefined();
  });

  it('loads an existing session when no runtime is provisioned yet', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/daifu/sessions/session_123')) {
        return jsonResponse(sessionContext);
      }
      if (url.includes('/controller/sessions/session_123/runtime')) {
        return jsonResponse({ status: 'not_provisioned' });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await useSessionStore.getState().loadSession('session_123');

    const state = useSessionStore.getState();
    expect(state.sessionStatus).toBe('ready');
    expect(state.currentSession?.session_id).toBe('session_123');
    expect(state.runtime).toBeNull();
    expect(state.runtimeStatus).toBe('not_provisioned');
    expect(state.error).toBeNull();
  });

  it('keeps session hydration successful when runtime lookup fails', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/daifu/sessions/session_123')) {
        return jsonResponse(sessionContext);
      }
      if (url.includes('/controller/sessions/session_123/runtime')) {
        return jsonResponse(
          {
            detail: {
              message: 'Modal build failed',
            },
          },
          503
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await expect(useSessionStore.getState().loadSession('session_123')).resolves.toBeUndefined();

    const state = useSessionStore.getState();
    expect(state.sessionStatus).toBe('ready');
    expect(state.currentSession?.session_id).toBe('session_123');
    expect(state.runtime).toBeNull();
    expect(state.runtimeStatus).toBe('failed');
    expect(state.runtimeError).toBe('Modal build failed');
  });

  it('creates GitHub issue previews without requiring a runtime', async () => {
    const fetchMock = vi.mocked(fetch);
    useSessionStore.getState().setSelectedRepository(mockRepository);

    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/daifu/sessions') && !url.includes('/issues/')) {
        return jsonResponse(baseSession);
      }
      if (url.includes('/issues/create-with-context')) {
        return jsonResponse(issueResponse);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const response = await useSessionStore.getState().createIssueWithContext(issueRequest);

    expect(response.success).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.some(([input]) =>
      String(input).includes('/controller/sessions/session_123/runtime')
    )).toBe(false);

    const state = useSessionStore.getState();
    expect(state.activeSessionId).toBe('session_123');
    expect(state.runtimeStatus).toBe('not_provisioned');
  });

  it('sends chat messages without requiring a runtime', async () => {
    const fetchMock = vi.mocked(fetch);
    useSessionStore.setState({
      activeSessionId: 'session_123',
      currentSession: baseSession,
      sessionInitialized: true,
      sessionStatus: 'ready',
      runtime: null,
      runtimeStatus: 'not_provisioned',
      runtimeError: null,
    });

    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/daifu/sessions/session_123/chat')) {
        return jsonResponse(chatResponse);
      }
      if (url.includes('/daifu/sessions/session_123/messages')) {
        return jsonResponse([]);
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const response = await useSessionStore.getState().sendChatMessage(
      'hello',
      [],
      mockRepository
    );

    expect(response.reply).toBe('Here is a plan.');

    const state = useSessionStore.getState();
    expect(state.sessionStatus).toBe('ready');
    expect(state.runtimeStatus).toBe('not_provisioned');
    expect(state.messageError).toBeNull();
    expect(state.messages).toHaveLength(2);
  });
});
