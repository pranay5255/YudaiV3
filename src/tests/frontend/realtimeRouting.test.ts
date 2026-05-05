import { describe, expect, it } from 'vitest';
import { API } from '@/config/api';
import {
  buildControllerSessionTargetUrl,
  buildRealtimeSessionEventsUrl,
} from '@/utils/realtimeRouting';

describe('realtime routing helpers', () => {
  it('builds controller session target URL through same-origin middleware', () => {
    const result = buildControllerSessionTargetUrl(API.SESSIONS.MESSAGES, {
      sessionId: 'session_abc',
    });

    expect(result).toBe('/daifu/sessions/session_abc/messages');
  });

  it('builds authenticated SSE event URLs without token query params', () => {
    expect(buildRealtimeSessionEventsUrl('session_abc')).toBe(
      '/realtime/sessions/session_abc/events'
    );
  });
});
