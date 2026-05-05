import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { useSessionWebSocket } from '@/hooks/useSessionWebSocket';
import { useAuthStore } from '@/stores/authStore';

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });

const sseResponse = (events: unknown[]): Response => {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      events.forEach((event) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      });
      controller.close();
    },
  });

  return new Response(body, {
    headers: { 'content-type': 'text/event-stream' },
    status: 200,
  });
};

const resetAuth = () => {
  localStorage.clear();
  useAuthStore.setState({
    error: null,
    isAuthenticated: true,
    isLoading: false,
    sessionToken: 'session-token',
    user: {
      created_at: new Date().toISOString(),
      display_name: 'Tester',
      email: 'tester@example.com',
      github_user_id: '1',
      github_username: 'tester',
      id: 1,
      last_login: new Date().toISOString(),
    },
  });
};

describe('useSessionWebSocket SSE bridge', () => {
  beforeEach(() => {
    resetAuth();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetAuth();
  });

  it('connects to the authenticated same-origin SSE bridge and handles events', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(sseResponse([
      { type: 'status', payload: { status: 'connected', session_id: 'session_123' } },
      {
        type: 'agent_question',
        payload: {
          multi_select: false,
          options: [{ id: 'tests', label: 'Tests' }],
          question_id: 'q_1',
          question_text: 'What should we test?',
        },
      },
      { type: 'done', payload: {} },
    ]));

    const { result } = renderHook(() => useSessionWebSocket({
      enabled: true,
      sessionId: 'session_123',
    }));

    await waitFor(() => {
      expect(result.current.status).toBe('completed');
    });

    expect(fetch).toHaveBeenCalledWith('/realtime/sessions/session_123/events', {
      headers: { Authorization: 'Bearer session-token' },
      signal: expect.any(AbortSignal),
    });
    expect(result.current.agentQuestion).toMatchObject({
      options: [{ id: 'tests', label: 'Tests' }],
      question_id: 'q_1',
      question_text: 'What should we test?',
    });
  });

  it('surfaces failed SSE connection attempts', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('missing secret', { status: 500 }));

    const { result } = renderHook(() => useSessionWebSocket({
      enabled: true,
      sessionId: 'session_123',
    }));

    await waitFor(() => {
      expect(result.current.error).toBe('Realtime stream failed with status 500');
    });
  });

  it('answers questions through the Python REST endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ status: 'answered' }));

    const { result } = renderHook(() => useSessionWebSocket({
      enabled: false,
      sessionId: 'session_123',
    }));

    await act(async () => {
      await result.current.sendUserResponse('q_1', ['tests'], 'Focus on tests');
    });

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/daifu/sessions/session_123/questions/q_1/answer');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({
      Authorization: 'Bearer session-token',
      'Content-Type': 'application/json',
    });
    expect(JSON.parse(String(init.body))).toEqual({
      answer_text: 'Focus on tests',
      resume_execution: true,
      selected_option_ids: ['tests'],
    });
  });
});
