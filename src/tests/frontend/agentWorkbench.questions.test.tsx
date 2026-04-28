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
      getExecutionStatus: vi.fn(),
      getSessionContext: vi.fn(),
      getWorkflow: vi.fn(),
      listBranches: vi.fn(),
      listContextCards: vi.fn(),
      listRepositories: vi.fn(),
      listRepositoryIssues: vi.fn(),
      listSessionIssues: vi.fn(),
      listTrajectories: vi.fn(),
      sendChatMessage: vi.fn(),
      selectWorkflowIssue: vi.fn(),
      startExecution: vi.fn(),
      updateWorkflowContext: vi.fn(),
    },
  };
});

const repo = {
  default_branch: 'main',
  description: 'Repository for question tests',
  full_name: 'octocat/yudaiv3',
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

const executionStatus = (overrides: Record<string, unknown> = {}) => ({
  cancel_requested: false,
  mode: 'pending',
  plan: [],
  session_id: session.session_id,
  status: 'idle',
  waiting_for_input: false,
  ...overrides,
});

describe('AgentWorkbench pending questions', () => {
  beforeEach(() => {
    vi.mocked(agentApi.listRepositories).mockResolvedValue([repo]);
    vi.mocked(agentApi.listBranches).mockResolvedValue([
      {
        commit: { sha: 'abc123', url: 'https://api.github.com/repos/octocat/yudaiv3/commits/abc123' },
        name: 'main',
        protected: false,
      },
    ]);
    vi.mocked(agentApi.listRepositoryIssues).mockResolvedValue([]);
    vi.mocked(agentApi.createSession).mockResolvedValue(session);
    vi.mocked(agentApi.getSessionContext).mockResolvedValue({
      messages: [],
      pending_questions: [
        {
          asked_at: '2026-04-28T00:00:01Z',
          multi_select: false,
          options: [{ id: 'jwt', label: 'JWT' }],
          prompt: 'Which auth flow?',
          question_id: 'q_auth_flow',
          selected_option_ids: [],
          session_id: session.session_id,
          status: 'pending',
        },
      ],
      session,
      statistics: { total_messages: 0, total_tokens: 0 },
      user_issues: [],
    });
    vi.mocked(agentApi.listContextCards).mockResolvedValue([]);
    vi.mocked(agentApi.listSessionIssues).mockResolvedValue([]);
    vi.mocked(agentApi.getExecutionStatus).mockResolvedValue(executionStatus());
    vi.mocked(agentApi.listTrajectories).mockResolvedValue([]);
    vi.mocked(agentApi.getWorkflow).mockResolvedValue({
      artifact: null,
      execution: executionStatus(),
      pending_questions: [
        {
          asked_at: '2026-04-28T00:00:01Z',
          multi_select: false,
          options: [{ id: 'jwt', label: 'JWT' }],
          prompt: 'Which auth flow?',
          question_id: 'q_auth_flow',
          selected_option_ids: [],
          session_id: session.session_id,
          status: 'pending',
        },
      ],
      pr_readiness: {},
      selected_issue: null,
      session,
      stage_results: {},
      user_context: { affected_systems: [] },
    });
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
  });

  it('renders hydrated pending questions and submits an answer', async () => {
    const user = userEvent.setup();
    render(<AgentWorkbench />);

    await user.click(await screen.findByRole('button', { name: /start session/i }));

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

  it('selects an issue and starts the pipeline without forcing a mode', async () => {
    const user = userEvent.setup();
    const issue = {
      body: 'Fix the callback state handling.',
      comments: 2,
      created_at: '2026-04-27T00:00:00Z',
      html_url: 'https://github.com/octocat/yudaiv3/issues/42',
      labels: ['bug'],
      number: 42,
      state: 'open',
      title: 'Fix auth callback state',
      updated_at: '2026-04-28T00:00:00Z',
    };
    const workflow = {
      artifact: null,
      execution: executionStatus({
        mode: 'architect',
        status: 'idle',
      }),
      pending_questions: [],
      pr_readiness: { status: 'drafting' },
      selected_issue: issue,
      session,
      stage_results: {},
      user_context: { affected_systems: [] },
    };

    vi.mocked(agentApi.listRepositoryIssues).mockResolvedValue([issue]);
    vi.mocked(agentApi.selectWorkflowIssue).mockResolvedValue(workflow);
    vi.mocked(agentApi.updateWorkflowContext).mockResolvedValue(workflow);
    vi.mocked(agentApi.startExecution).mockResolvedValue({
      cancel_requested: false,
      execution_id: 'exec_42',
      mode: 'architect',
      plan: [],
      session_id: session.session_id,
      started_at: '2026-04-28T00:00:05Z',
      status: 'running',
      waiting_for_input: false,
    });

    render(<AgentWorkbench />);

    await user.click(await screen.findByRole('button', { name: /start session/i }));
    await user.click(screen.getByRole('button', { name: /^issues$/i }));
    await user.click(await screen.findByRole('button', { name: /discuss issue 42/i }));
    await user.click(screen.getByRole('button', { name: /^runs$/i }));
    await user.click(await screen.findByRole('button', { name: /start pipeline/i }));

    await waitFor(() => {
      expect(agentApi.startExecution).toHaveBeenCalledWith(
        session.session_id,
        expect.not.objectContaining({ force_mode: expect.anything() }),
        'test-token'
      );
    });
  });
});
