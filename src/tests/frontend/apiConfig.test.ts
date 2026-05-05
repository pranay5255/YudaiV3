import { describe, expect, it } from 'vitest';
import {
  API,
  buildApiUrl,
  resolveAiApiBase,
  resolveApiBase,
  resolveAuthApiBase,
} from '@/config/api';

describe('api config', () => {
  it('defaults app API base to same-origin middleware', () => {
    expect(resolveApiBase(undefined)).toBe('');
    expect(resolveApiBase('')).toBe('');
  });

  it('trims API base values', () => {
    expect(resolveApiBase('  https://api.example.com  ')).toBe('https://api.example.com');
    expect(resolveApiBase(' / ')).toBe('');
    expect(resolveApiBase(' /app-api ')).toBe('/app-api');
    expect(resolveApiBase('https://api.example.com/')).toBe('https://api.example.com');
  });

  it('keeps auth API base separate from middleware app APIs', () => {
    expect(resolveAuthApiBase('  https://auth.example.com/// ')).toBe('https://auth.example.com');
    expect(resolveAuthApiBase('/api')).toBe('/api');
  });

  it('replaces endpoint params when building URLs', () => {
    const url = buildApiUrl(API.SESSIONS.ISSUES.CREATE_GITHUB_ISSUE, {
      sessionId: 'session_123',
      issueId: 'issue_9',
    });
    expect(url).toContain('/daifu/sessions/session_123/issues/issue_9/create-github-issue');
  });

  it('defaults AI API base to same origin', () => {
    expect(resolveAiApiBase(undefined)).toBe('');
    expect(resolveAiApiBase('')).toBe('');
  });

  it('trims trailing slashes from AI API base values', () => {
    expect(resolveAiApiBase('  https://ai.example.com///  ')).toBe('https://ai.example.com');
    expect(resolveAiApiBase('/')).toBe('');
  });

  it('builds AI chat stream URLs', () => {
    expect(buildApiUrl(API.AI.CHAT_STREAM, { sessionId: 'session_123' }))
      .toBe('/ai/sessions/session_123/stream');
  });
});
