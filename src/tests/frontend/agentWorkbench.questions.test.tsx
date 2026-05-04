import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentWorkbench } from '@/components/AgentWorkbench';
import { agentApi } from '@/services/agentApi';
import { EXECUTION_OBJECTIVE_MAX_CHARS } from '@/utils/workflowObjective';

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
      listBranches: vi.fn(),
      listContextCards: vi.fn(),
      listRepositories: vi.fn(),
      listRepositoryIssues: vi.fn(),
      listSessionIssues: vi.fn(),
      listTrajectories: vi.fn(),
      sendChatMessage: vi.fn(),
      startExecution: vi.fn(),
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

describe('AgentWorkbench pending questions', () => {
  beforeEach(() => {
    vi.mocked(agentApi.listRepositories).mockResolvedValue([repo]);
    vi.mocked(agentApi.listBranches).mockResolvedValue([
      {
        commit: {},
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
    vi.mocked(agentApi.getExecutionStatus).mockResolvedValue({
      cancel_requested: false,
      mode: 'pending',
      session_id: session.session_id,
      status: 'idle',
      waiting_for_input: false,
    });
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

  it('caps a long run objective before starting execution', async () => {
    const user = userEvent.setup();
    vi.mocked(agentApi.getSessionContext).mockResolvedValue({
      messages: [],
      pending_questions: [],
      session,
      statistics: { total_messages: 0, total_tokens: 0 },
      user_issues: [],
    });
    vi.mocked(agentApi.startExecution).mockResolvedValue({
      cancel_requested: false,
      execution_id: 'exec_long_objective',
      mode: 'architect',
      plan: [],
      session_id: session.session_id,
      started_at: '2026-04-28T00:00:04Z',
      status: 'running',
      waiting_for_input: false,
    });
    render(<AgentWorkbench />);

    await user.click(await screen.findByRole('button', { name: /start session/i }));
    await user.click(screen.getByRole('button', { name: /runs/i }));

    fireEvent.change(screen.getByLabelText(/objective/i), {
      target: { value: `Fix the workflow boundary\n${'x'.repeat(12000)}` },
    });
    await user.click(screen.getByRole('button', { name: /start run/i }));

    await waitFor(() => {
      expect(agentApi.startExecution).toHaveBeenCalled();
    });
    const request = vi.mocked(agentApi.startExecution).mock.calls[0][1];
    expect(request.objective.length).toBeLessThanOrEqual(EXECUTION_OBJECTIVE_MAX_CHARS);
    expect(request.objective).toContain('Fix the workflow boundary');
  });
});
