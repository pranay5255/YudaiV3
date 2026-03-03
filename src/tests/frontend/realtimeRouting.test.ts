import { describe, expect, it } from 'vitest';
import { API } from '@/config/api';
import {
  buildControllerSessionTargetUrl,
  buildControllerUnifiedWsEndpoint,
  buildUnifiedSessionWebSocketUrl,
} from '@/utils/realtimeRouting';

describe('realtime routing helpers', () => {
  it('builds controller session target URL directly (no proxy/tunnel rewrite)', () => {
    const result = buildControllerSessionTargetUrl(API.SESSIONS.MESSAGES, {
      sessionId: 'session_abc',
    });

    expect(result).toBe('/api/daifu/sessions/session_abc/messages');
  });

  it('builds controller unified websocket URL using wss on https frontends', () => {
    const result = buildUnifiedSessionWebSocketUrl({
      sessionId: 'session_abc',
      sessionToken: 'tok+en/123',
      currentOrigin: 'https://my-frontend.vercel.app',
    });

    expect(result).toBe(
      'wss://my-frontend.vercel.app/api/controller/sessions/session_abc/ws/unified?token=tok%2Ben%2F123'
    );
  });

  it('builds websocket URL from absolute controller ws endpoint', () => {
    const result = buildUnifiedSessionWebSocketUrl({
      sessionId: 'session_abc',
      sessionToken: 'token',
      controllerWsBaseUrl:
        'http://139.84.154.9:8000/controller/sessions/session_abc/ws/unified',
    });

    expect(result).toBe(
      'ws://139.84.154.9:8000/controller/sessions/session_abc/ws/unified?token=token'
    );
  });

  it('builds websocket URL from WS base host by appending unified endpoint', () => {
    const endpoint = buildControllerUnifiedWsEndpoint({
      sessionId: 'session_abc',
      controllerWsBaseUrl: 'ws://139.84.154.9:8000',
    });

    expect(endpoint).toBe(
      'ws://139.84.154.9:8000/controller/sessions/session_abc/ws/unified'
    );

    const url = buildUnifiedSessionWebSocketUrl({
      sessionId: 'session_abc',
      sessionToken: 'token',
      controllerWsBaseUrl: 'ws://139.84.154.9:8000',
    });

    expect(url).toBe(
      'ws://139.84.154.9:8000/controller/sessions/session_abc/ws/unified?token=token'
    );
  });
});
