import { describe, expect, it } from 'vitest';
import { API, buildApiUrl, resolveApiBase } from '@/config/api';

describe('api config', () => {
  it('defaults API base to /api when env value is missing', () => {
    expect(resolveApiBase(undefined)).toBe('/api');
    expect(resolveApiBase('')).toBe('/api');
  });

  it('trims API base values', () => {
    expect(resolveApiBase('  https://api.example.com  ')).toBe('https://api.example.com');
    expect(resolveApiBase(' /api ')).toBe('/api');
    expect(resolveApiBase('https://api.example.com/')).toBe('https://api.example.com');
  });

  it('replaces endpoint params when building URLs', () => {
    const url = buildApiUrl(API.SESSIONS.ISSUES.CREATE_GITHUB_ISSUE, {
      sessionId: 'session_123',
      issueId: 'issue_9',
    });
    expect(url).toContain('/daifu/sessions/session_123/issues/issue_9/create-github-issue');
  });
});
