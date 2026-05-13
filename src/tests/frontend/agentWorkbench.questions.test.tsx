import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentWorkbench } from '@/components/AgentWorkbench';
import { agentApi } from '@/services/agentApi';

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    logout: vi.fn(),
    sessionToken: 'test-token',
    user: {
      display_name: 'Test User',
      github_username: 'tester',
    },
  }),
}));

vi.mock('@/services/agentApi', () => {
  class AgentApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }

  return {
    AgentApiError,
    agentApi: {
      answerQuestion: vi.fn(),
      cancelExecution: vi.fn(),
      createSession: vi.fn(),
      ensureRuntime: vi.fn(),
      getExecutionStatus: vi.fn(),
      getExecutionEvents: vi.fn(),
      getSessionContext: vi.fn(),
      listBranches: vi.fn(),
      listContextCards: vi.fn(),
      listRepositories: vi.fn(),
      listRepositoryIssues: vi.fn(),
      listSessionIssues: vi.fn(),
      listTrajectories: vi.fn(),
      startExecution: vi.fn(),
    },
  };
});

const repo = {
  clone_url: 'https://github.com/octocat/yudaiv3.git',
  default_branch: 'main',
  description: 'Repository for question tests',
  full_name: 'octocat/yudaiv3',
  html_url: 'https://github.com/octocat/yudaiv3',
  id: 1,
  language: 'TypeScript',
  name: 'yudaiv3',
  open_issues_count: 3,
  owner: { login: 'octocat' },
  private: false,
};

const session = {
  created_at: '2026-04-28T00:00:00Z',
  current_mode: 'pending',
  id: 10,
  is_active: true,
  mode_metadata: { gathering_state: 'complete' },
  mode_status: 'idle',
  repo_branch: 'main',
  repo_name: 'yudaiv3',
  repo_owner: 'octocat',
  session_id: 'session_question_ui',
  title: 'octocat/yudaiv3:main',
  total_messages: 0,
  total_tokens: 0,
};

const contextCard = {
  content: 'Auth token flow context',
  created_at: '2026-04-28T00:00:02Z',
  description: 'Auth context',
  id: 42,
  is_active: true,
  session_id: 10,
  source: 'chat' as const,
  title: 'Auth flow',
  tokens: 12,
  updated_at: null,
};

const executionStatus = {
  cancel_requested: false,
  execution_id: 'exec_1',
  mode: 'pending',
  session_id: session.session_id,
  started_at: '2026-04-28T00:00:05Z',
  status: 'idle',
  waiting_for_input: false,
};

const runtime = {
  completion_detected: false,
  completion_issue_created: false,
  completion_pr_created: false,
  identity_key: 'runtime_identity',
  metadata: {},
  runtime_id: 'runtime_1',
  sandbox_id: 'sandbox_1',
  status: 'ready',
  token_ttl_seconds: null,
  tunnel_expires_at: null,
  tunnel_url: null,
};

const emptySessionContext = {
  messages: [],
  pending_questions: [],
  session,
  statistics: { total_messages: 0, total_tokens: 0 },
  user_issues: [],
};

const assistantMessage = {
  actions: [],
  context_cards: [],
  created_at: '2026-04-28T00:00:04Z',
  error_message: null,
  id: 100,
  is_code: false,
  message_id: 'assistant_streamed',
  message_text: 'Streamed hello',
  model_used: 'test-model',
  processing_time: 0.2,
  referenced_files: [],
  role: 'assistant',
  sender_type: 'assistant',
  tokens: 5,
  updated_at: null,
};

const question = {
  asked_at: '2026-04-28T00:00:01Z',
  multi_select: false,
  options: [{ id: 'jwt', label: 'JWT' }],
  prompt: 'Which auth flow?',
  question_id: 'q_auth_flow',
  selected_option_ids: [],
  session_id: session.session_id,
  status: 'pending',
};

function sseResponse(chunks: unknown[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
      });
      controller.enqueue(encoder.encode('data: [DONE]\n\n'));
      controller.close();
    },
  });

  return new Response(body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'x-vercel-ai-ui-message-stream': 'v1',
    },
    status: 200,
  });
}

function successfulAiStreamResponse(): Response {
  return sseResponse([
    { type: 'start', messageId: 'assistant_streaming' },
    { type: 'text-start', id: 'text_1' },
    { type: 'text-delta', id: 'text_1', delta: 'Streamed' },
    { type: 'text-delta', id: 'text_1', delta: ' hello' },
    { type: 'text-end', id: 'text_1' },
    { type: 'finish', finishReason: 'stop' },
  ]);
}

async function renderStartedWorkbench(): Promise<ReturnType<typeof userEvent.setup>> {
  const user = userEvent.setup();
  render(<AgentWorkbench />);

  await user.click(await screen.findByRole('button', { name: /start session/i }));
  await waitFor(() => {
    expect(agentApi.getSessionContext).toHaveBeenCalled();
  });

  return user;
}

describe('AgentWorkbench pending questions', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(successfulAiStreamResponse()));
    vi.mocked(agentApi.listRepositories).mockResolvedValue([repo]);
    vi.mocked(agentApi.listBranches).mockResolvedValue([{
      commit: {
        sha: 'abc123',
        url: 'https://api.github.test/commit/abc123',
      },
      name: 'main',
      protected: false,
    }]);
    vi.mocked(agentApi.listRepositoryIssues).mockResolvedValue([]);
    vi.mocked(agentApi.createSession).mockResolvedValue(session);
    vi.mocked(agentApi.ensureRuntime).mockResolvedValue(runtime);
    vi.mocked(agentApi.getSessionContext).mockResolvedValue(emptySessionContext);
    vi.mocked(agentApi.listContextCards).mockResolvedValue([contextCard]);
    vi.mocked(agentApi.listSessionIssues).mockResolvedValue([]);
    vi.mocked(agentApi.getExecutionStatus).mockResolvedValue(executionStatus);
    vi.mocked(agentApi.getExecutionEvents).mockResolvedValue([]);
    vi.mocked(agentApi.listTrajectories).mockResolvedValue([]);
    vi.mocked(agentApi.answerQuestion).mockResolvedValue({
      mode_status: 'idle',
      question: {
        asked_at: '2026-04-28T00:00:01Z',
        answered_at: '2026-04-28T00:00:03Z',
        multi_select: false,
        options: [{ id: 'jwt', label: 'JWT' }],
        prompt: 'Which auth flow?',
        question_id: 'q_auth_flow',
        selected_option_ids: ['jwt'],
        session_id: session.session_id,
        status: 'answered',
      },
      resumed: false,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('renders hydrated pending questions and submits an answer', async () => {
    vi.mocked(agentApi.getSessionContext).mockResolvedValue({
      ...emptySessionContext,
      pending_questions: [question],
    });
    const user = await renderStartedWorkbench();

    expect(await screen.findByText('Which auth flow?')).toBeInTheDocument();

    await user.click(screen.getByLabelText('JWT'));
    await user.click(screen.getByRole('button', { name: /submit answer/i }));

    await waitFor(() => {
      expect(agentApi.answerQuestion).toHaveBeenCalledWith(
        session.session_id,
        'q_auth_flow',
        {
          answer_text: undefined,
          resume_execution: true,
          selected_option_ids: ['jwt'],
        },
        'test-token'
      );
    });
  });

  it('uses top repository controls and prepares runtime on explicit start', async () => {
    const user = userEvent.setup();
    const { container } = render(<AgentWorkbench />);

    expect(await screen.findByRole('button', { name: /selected repository octocat\/yudaiv3/i }))
      .toBeInTheDocument();
    expect(container.querySelector('main')?.className).not.toContain('320px');

    await user.click(screen.getByRole('button', { name: /start session & prepare runtime/i }));

    await waitFor(() => {
      expect(agentApi.createSession).toHaveBeenCalledWith({
        description: 'Repository for question tests',
        repo_branch: 'main',
        repo_name: 'yudaiv3',
        repo_owner: 'octocat',
        title: 'octocat/yudaiv3:main',
      }, 'test-token');
      expect(agentApi.ensureRuntime).toHaveBeenCalledWith(
        session.session_id,
        {
          environment: 'main',
          org: 'yudai',
          repo_branch: 'main',
          repo_name: 'yudaiv3',
          repo_owner: 'octocat',
          repo_url: 'https://github.com/octocat/yudaiv3.git',
        },
        'test-token'
      );
    });
    expect(await screen.findAllByText(/Runtime running/i)).not.toHaveLength(0);
  });

  it('shows the run monitor without direct start controls', async () => {
    const user = await renderStartedWorkbench();

    await user.click(screen.getByRole('button', { name: /runs/i }));

    expect(screen.getByText('Run monitor')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /start run/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/objective/i)).not.toBeInTheDocument();
    expect(agentApi.startExecution).not.toHaveBeenCalled();
  });

  it('sends chat through the AI SDK stream endpoint with auth and Yudai context', async () => {
    vi.mocked(agentApi.getSessionContext)
      .mockResolvedValueOnce(emptySessionContext)
      .mockResolvedValue({
        ...emptySessionContext,
        messages: [assistantMessage],
        session: {
          ...session,
          total_messages: 1,
          total_tokens: 5,
        },
      });
    const user = await renderStartedWorkbench();

    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText('Message'), 'hello');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await screen.findByText('Streamed hello');
    expect(await screen.findByText('test-model')).toBeInTheDocument();

    const fetchMock = vi.mocked(fetch);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('/ai/sessions/session_question_ui/stream');

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe('POST');
    const headers = new Headers(init.headers);
    expect(headers.get('authorization')).toBe('Bearer test-token');
    expect(headers.get('content-type')).toBe('application/json');

    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({
      context_card_ids: ['42'],
      messageId: null,
      repository: {
        branch: 'main',
        name: 'yudaiv3',
        owner: 'octocat',
      },
      session_id: session.session_id,
      trigger: 'submit-message',
    });
    expect(body).not.toHaveProperty('token');
    expect(body.messages.at(-1)).toMatchObject({
      parts: [{ text: 'hello', type: 'text' }],
      role: 'user',
    });

    await waitFor(() => {
      expect(agentApi.getSessionContext).toHaveBeenCalledTimes(2);
    });
  });

  it('auto-creates a chat session without preparing runtime', async () => {
    const user = userEvent.setup();
    render(<AgentWorkbench />);

    await screen.findByRole('button', { name: /selected repository octocat\/yudaiv3/i });
    await user.type(screen.getByLabelText('Message'), 'chat only');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
    expect(agentApi.createSession).toHaveBeenCalledTimes(1);
    expect(agentApi.ensureRuntime).not.toHaveBeenCalled();
  });

  it('renders streamed data agent questions with the existing prompt component', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(sseResponse([
      { type: 'start', messageId: 'assistant_question' },
      {
        type: 'data-agent-question',
        id: 'q_auth_flow',
        data: {
          multi_select: false,
          options: [{ id: 'jwt', label: 'JWT' }],
          question_id: 'q_auth_flow',
          question_text: 'Which auth flow?',
        },
      },
      { type: 'finish', finishReason: 'stop' },
    ]));
    vi.mocked(agentApi.getSessionContext)
      .mockResolvedValueOnce(emptySessionContext)
      .mockResolvedValue({
        ...emptySessionContext,
        pending_questions: [question],
      });
    const user = await renderStartedWorkbench();

    await user.type(screen.getByLabelText('Message'), 'ask a question');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    expect(await screen.findByText('Which auth flow?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit answer/i })).toBeInTheDocument();
  });

  it('keeps the draft recoverable and shows a notice when the stream fails', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('stream exploded', { status: 500 }));
    const user = await renderStartedWorkbench();

    await user.type(screen.getByLabelText('Message'), 'please fail');
    await user.click(screen.getByRole('button', { name: /^send$/i }));

    expect(await screen.findByDisplayValue('please fail')).toBeInTheDocument();
    expect(await screen.findByText('stream exploded')).toBeInTheDocument();
  });

  it('keeps emergency cancel on the Python execution endpoint', async () => {
    vi.mocked(agentApi.cancelExecution).mockResolvedValue({
      message: 'Run cancelled',
      session_id: session.session_id,
      status: 'cancelled',
    });
    vi.mocked(agentApi.getExecutionStatus).mockResolvedValue({
      ...executionStatus,
      mode: 'architect',
      status: 'running',
    });
    const user = await renderStartedWorkbench();

    await user.click(screen.getByRole('button', { name: /runs/i }));
    await user.click(screen.getByRole('button', { name: /emergency cancel/i }));

    await waitFor(() => {
      expect(agentApi.cancelExecution).toHaveBeenCalledWith(session.session_id, 'test-token');
    });
  });
});
