import { describe, expect, it } from 'vitest';
import { API } from '../../src/config/api';
import {
  buildControllerProxySessionUrl,
  buildRealtimeSessionTargetUrl,
  buildUnifiedSessionWebSocketUrl,
} from '../../src/utils/realtimeRouting';

describe('realtime routing helpers', () => {
  it('builds controller proxy session URL from relative session endpoint', () => {
    const result = buildControllerProxySessionUrl(
      '/api/daifu/sessions/session_abc/messages?limit=10',
      'https://frontend.example.com'
    );

    expect(result).toBe(
      '/api/controller/proxy/sessions/session_abc/sessions/session_abc/messages?limit=10'
    );
  });

  it('builds controller proxy session URL from absolute backend endpoint', () => {
    const result = buildControllerProxySessionUrl(
      'https://api.example.com/api/daifu/sessions/session_abc/chat'
    );

    expect(result).toBe(
      'https://api.example.com/api/controller/proxy/sessions/session_abc/sessions/session_abc/chat'
    );
  });

  it('returns direct resolved URL when proxy/tunnel flags are disabled', () => {
    const result = buildRealtimeSessionTargetUrl({
      endpoint: API.SESSIONS.DETAIL,
      params: { sessionId: 'session_abc' },
      flags: { controllerProxyEnabled: false, tunnelModeEnabled: false },
      currentOrigin: 'https://frontend.example.com',
    });

    expect(result).toBe('/api/daifu/sessions/session_abc');
  });

  it('builds tunnel URL when tunnel mode is enabled', () => {
    const result = buildRealtimeSessionTargetUrl({
      endpoint: API.SESSIONS.SOLVER.STATUS,
      params: { sessionId: 'session_abc', solveSessionId: 'solve_1' },
      flags: { controllerProxyEnabled: false, tunnelModeEnabled: true },
      tunnelUrl: 'https://sandbox.modal.run/',
      currentOrigin: 'https://frontend.example.com',
    });

    expect(result).toBe('https://sandbox.modal.run/sessions/session_abc/solve/status/solve_1');
  });

  it('throws when tunnel mode is enabled but no tunnel URL is available', () => {
    expect(() =>
      buildRealtimeSessionTargetUrl({
        endpoint: API.SESSIONS.CHAT,
        params: { sessionId: 'session_abc' },
        flags: { controllerProxyEnabled: false, tunnelModeEnabled: true },
        currentOrigin: 'https://frontend.example.com',
      })
    ).toThrow('Sandbox tunnel is unavailable');
  });

  it('builds same-origin proxy websocket URL using wss on https frontends', () => {
    const result = buildUnifiedSessionWebSocketUrl({
      sessionId: 'session_abc',
      sessionToken: 'tok+en/123',
      currentOrigin: 'https://my-frontend.vercel.app',
    });

    expect(result).toBe(
      'wss://my-frontend.vercel.app/api/controller/proxy/sessions/session_abc/ws/sessions/session_abc/ws/unified?token=tok%2Ben%2F123'
    );
  });

  it('builds websocket URL from absolute proxy base (split deployment)', () => {
    const result = buildUnifiedSessionWebSocketUrl({
      sessionId: 'session_abc',
      sessionToken: 'token',
      proxyBaseUrl: 'http://139.84.154.9:8000/controller/proxy/sessions/session_abc',
    });

    expect(result).toBe(
      'ws://139.84.154.9:8000/controller/proxy/sessions/session_abc/ws/sessions/session_abc/ws/unified?token=token'
    );
  });
});
