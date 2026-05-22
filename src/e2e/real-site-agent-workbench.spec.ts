import {
  authenticateViaCallback,
  expect,
  installRepositoryApiMocks,
  responseJson,
  selectConfiguredRepository,
  test,
} from './fixtures';

type CreateSessionPayload = {
  session?: {
    session_id?: unknown;
  };
  session_id?: unknown;
};

type ExecutionEventPayload = unknown[];

type QuestionPayload = {
  question?: {
    question_id?: unknown;
  };
};

type SessionContextPayload = {
  pending_questions?: Array<{
    question_id?: unknown;
  }>;
};

function extractSessionId(payload: CreateSessionPayload): string {
  if (typeof payload.session_id === 'string' && payload.session_id) {
    return payload.session_id;
  }

  if (typeof payload.session?.session_id === 'string' && payload.session.session_id) {
    return payload.session.session_id;
  }

  throw new Error('Create session response did not include a session_id.');
}

function extractQuestionId(payload: QuestionPayload): string {
  if (typeof payload.question?.question_id === 'string' && payload.question.question_id) {
    return payload.question.question_id;
  }

  throw new Error('Question response did not include a question_id.');
}

function extractPendingQuestionId(payload: SessionContextPayload): string {
  const questionId = payload.pending_questions?.[0]?.question_id;
  if (typeof questionId === 'string' && questionId) {
    return questionId;
  }

  throw new Error('Session context did not include a pending question_id.');
}

test.describe('real-site AgentWorkbench control flow', () => {
  test('validates PR 193 session execution gates without starting runtime', async ({
    authApi,
    e2eConfig,
    page,
  }) => {
    let pendingQuestionId: string | undefined;
    let sessionId: string | undefined;
    let failure: unknown;

    try {
      await installRepositoryApiMocks(page, e2eConfig);

      await test.step('authenticate through the real callback route', async () => {
        await authenticateViaCallback(page, e2eConfig);
        await expect(page.getByRole('button', { name: /selected repository/i }))
          .toBeVisible();
      });

      await test.step('select the configured repository', async () => {
        await selectConfiguredRepository(page, e2eConfig);
      });

      await test.step('create a chat-only session through the UI', async () => {
        const createSessionResponse = page.waitForResponse((response) => {
          const url = new URL(response.url());
          return response.request().method() === 'POST' && url.pathname === '/daifu/sessions';
        });

        await expect(page.getByRole('button', { name: /^start chat session$/i }))
          .toBeEnabled();
        await page.getByRole('button', { name: /^start chat session$/i }).click();

        const response = await createSessionResponse;
        expect(response.ok(), 'session creation response').toBe(true);

        const payload = await responseJson<CreateSessionPayload>(
          response,
          'Create session response'
        );
        sessionId = extractSessionId(payload);
      });

      await test.step('verify the run monitor and removed legacy controls', async () => {
        await page.getByRole('button', { name: /^runs$/i }).click();
        await expect(page.getByRole('heading', { name: 'Run monitor' })).toBeVisible();
        await expect(page.getByRole('button', { name: /^start run$/i })).toHaveCount(0);
        await expect(page.getByLabel(/objective/i)).toHaveCount(0);
      });

      await test.step('verify direct execution is blocked and events are readable', async () => {
        if (!sessionId) {
          throw new Error('Missing session_id before execution endpoint checks.');
        }

        const directStart = await authApi.post(`/daifu/sessions/${sessionId}/execution`, {
          force_mode: 'architect',
          objective: 'Real-site E2E control-flow check. Do not start live execution.',
        });
        expect(directStart.status(), 'direct execution start status').toBe(409);

        const eventsResponse = await authApi.get(`/daifu/sessions/${sessionId}/execution/events`);
        expect(eventsResponse.ok(), 'execution events response').toBe(true);
        const events = await responseJson<ExecutionEventPayload>(
          eventsResponse,
          'Execution events response'
        );
        expect(Array.isArray(events), 'execution events payload').toBe(true);
      });

      await test.step('seed and render a stage approval card', async () => {
        if (!sessionId) {
          throw new Error('Missing session_id before seeding stage approval.');
        }

        const seedResponse = await authApi.post(`/daifu/sessions/${sessionId}/ask-question`, {
          metadata: {
            admin_required: false,
            approval_scope: 'session_execution',
            next_mode: 'architect',
            origin: 'stage_gate',
            pending_tool: 'run_architect_mode',
            recommendation: 'Daifu recommends starting Architect first.',
            required_actor: 'session_user',
            summary: 'Real-site PR 193 control-flow gate is ready for approval.',
            target_mode: 'architect',
            target_type: 'agent_stage',
          },
          mode: 'architect',
          multi_select: false,
          objective: 'Real-site E2E stage approval control-flow check.',
          options: [
            { id: 'start_next_stage', label: 'Start Architect' },
            { id: 'add_notes', label: 'Add notes or constraints' },
            { id: 'stop_here', label: 'Stop here' },
          ],
          prompt: 'Start Architect?',
        });
        expect(seedResponse.status(), 'seed stage approval status').toBe(201);
        pendingQuestionId = extractQuestionId(await responseJson<QuestionPayload>(
          seedResponse,
          'Seed stage approval response'
        ));

        await page.getByRole('button', { exact: true, name: 'Chat' }).click();
        await page.getByRole('button', { name: 'Refresh workspace' }).click();

        const approvalCard = page.locator(`[data-question-id="${pendingQuestionId}"]`);
        await expect(approvalCard.getByText('Stage approval')).toBeVisible();
        await expect(approvalCard.getByText('Real-site PR 193 control-flow gate is ready for approval.'))
          .toBeVisible();
        await expect(approvalCard.getByText('Daifu recommends starting Architect first.')).toBeVisible();
        await expect(approvalCard.getByLabel('Start Architect')).toBeVisible();
        await expect(approvalCard.getByLabel('Add notes or constraints')).toBeVisible();
        await expect(approvalCard.getByLabel('Stop here')).toBeVisible();
      });

      await test.step('submit notes and keep the approval card usable', async () => {
        if (!sessionId || !pendingQuestionId) {
          throw new Error('Missing session_id before answering stage approval with notes.');
        }

        const approvalCard = page.locator(`[data-question-id="${pendingQuestionId}"]`);
        const answerResponse = page.waitForResponse((response) => {
          const url = new URL(response.url());
          return response.request().method() === 'POST'
            && url.pathname.includes(`/daifu/sessions/${sessionId}/questions/`)
            && url.pathname.endsWith('/answer');
        });

        await approvalCard.getByLabel('Add notes or constraints').check();
        await approvalCard.getByPlaceholder('Notes or constraints')
          .fill('Keep this as a control-flow-only E2E check.');
        await approvalCard.getByRole('button', { name: /submit answer/i }).click();

        const response = await answerResponse;
        expect(response.ok(), 'add-notes answer response').toBe(true);
        const contextResponse = await authApi.get(`/daifu/sessions/${sessionId}`);
        expect(contextResponse.ok(), 'post-notes context refresh response').toBe(true);
        const nextContext = await responseJson<SessionContextPayload>(
          contextResponse,
          'Post-notes context refresh response'
        );
        pendingQuestionId = extractPendingQuestionId(nextContext);

        const nextApprovalCard = page.locator(`[data-question-id="${pendingQuestionId}"]`);
        await page.getByRole('button', { name: 'Refresh workspace' }).click();
        await expect(nextApprovalCard.getByText('Stage approval')).toBeVisible();
        await expect(nextApprovalCard.getByLabel('Stop here')).toBeEnabled();
      });

      await test.step('stop at the stage gate and clear the pending approval', async () => {
        if (!sessionId || !pendingQuestionId) {
          throw new Error('Missing session_id before stopping at stage gate.');
        }

        const approvalCard = page.locator(`[data-question-id="${pendingQuestionId}"]`);
        const answerResponse = page.waitForResponse((response) => {
          const url = new URL(response.url());
          return response.request().method() === 'POST'
            && url.pathname.includes(`/daifu/sessions/${sessionId}/questions/`)
            && url.pathname.endsWith('/answer');
        });

        await approvalCard.getByLabel('Stop here').check();
        await expect(approvalCard.getByLabel('Stop here')).toBeChecked();
        await expect(approvalCard.getByRole('button', { name: /submit answer/i })).toBeEnabled();
        await approvalCard.getByRole('button', { name: /submit answer/i }).click();

        const response = await answerResponse;
        expect(response.ok(), 'stop-here answer response').toBe(true);
        const refreshedContext = await authApi.get(`/daifu/sessions/${sessionId}`);
        expect(refreshedContext.ok(), 'post-stop context refresh response').toBe(true);
        const contextPayload = await responseJson<SessionContextPayload>(
          refreshedContext,
          'Post-stop context refresh response'
        );
        expect(contextPayload.pending_questions || []).toHaveLength(0);
        await page.getByRole('button', { name: 'Refresh workspace' }).click();
        await expect(approvalCard).toHaveCount(0);
      });
    } catch (error) {
      failure = error;
    } finally {
      if (sessionId) {
        const cleanupResponse = await authApi.put(`/daifu/sessions/${sessionId}`, {
          is_active: false,
        });
        if (!cleanupResponse.ok() && !failure) {
          failure = new Error('Failed to mark the disposable E2E session inactive.');
        }
      }
    }

    if (failure) {
      throw failure;
    }
  });
});
