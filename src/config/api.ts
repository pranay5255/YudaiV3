// src/config/api.ts - Ultra-minimal Contract One API Configuration

const DEFAULT_PROD_API_BASE = 'https://api.yudai.app';

// Contract One:
// - Production should call backend domain directly (https://api.yudai.app)
// - Local development uses /api with Vite proxy rewrite to backend root
export const resolveApiBase = (value?: string): string => {
  const raw = (value || '').trim();
  const fallback = import.meta.env.PROD ? DEFAULT_PROD_API_BASE : '/api';
  const normalized = (raw || fallback).trim() || fallback;

  if (normalized === '/') {
    return normalized;
  }

  return normalized.replace(/\/+$/, '');
};

// VITE_API_BASE_URL is set via:
// 1. Vercel environment variables (production)
// 2. .env.local or .env.production (build time)
// 3. Falls back to production backend domain in prod, /api in local development
export const API_BASE = resolveApiBase(import.meta.env.VITE_API_BASE_URL);

export const API = {
  AUTH: {
    LOGIN: `${API_BASE}/auth/api/login`,
    CALLBACK: '/auth/callback', // GitHub OAuth redirect (top-level)
    USER: `${API_BASE}/auth/api/user`,
    LOGOUT: `${API_BASE}/auth/api/logout`,
  },
  GITHUB: {
    REPOS: `${API_BASE}/github/repositories`,
    REPO_BRANCHES: `${API_BASE}/github/repositories/{owner}/{repo}/branches`,
  },
  SESSIONS: {
    BASE: `${API_BASE}/daifu/sessions`,
    DETAIL: `${API_BASE}/daifu/sessions/{sessionId}`,
    MESSAGES: `${API_BASE}/daifu/sessions/{sessionId}/messages`,
    CHAT: `${API_BASE}/daifu/sessions/{sessionId}/chat`,
    CONVERSATION: `${API_BASE}/daifu/sessions/{sessionId}/conversation`,
    EXECUTION: `${API_BASE}/daifu/sessions/{sessionId}/execution`,
    EXECUTION_CANCEL: `${API_BASE}/daifu/sessions/{sessionId}/execution/cancel`,
    ASK_QUESTION: `${API_BASE}/daifu/sessions/{sessionId}/ask-question`,
    ANSWER_QUESTION: `${API_BASE}/daifu/sessions/{sessionId}/questions/{questionId}/answer`,
    CONTEXT_CARDS: `${API_BASE}/daifu/sessions/{sessionId}/context-cards`,
    CONTEXT_CARD_DETAIL: `${API_BASE}/daifu/sessions/{sessionId}/context-cards/{cardId}`,
    FILE_DEPS_SESSION: `${API_BASE}/daifu/sessions/{sessionId}/file-deps/session`,
    EXTRACT: `${API_BASE}/daifu/sessions/{sessionId}/extract`,
    ISSUES: {
      CREATE: `${API_BASE}/daifu/sessions/{sessionId}/issues/create-with-context`,
      LIST: `${API_BASE}/daifu/sessions/{sessionId}/issues`,
      DETAIL: `${API_BASE}/daifu/sessions/{sessionId}/issues/{issueId}`,
      CREATE_GITHUB_ISSUE: `${API_BASE}/daifu/sessions/{sessionId}/issues/{issueId}/create-github-issue`,
    },
  },
  CONTROLLER: {
    SANDBOXES: `${API_BASE}/controller/sandboxes`,
    SANDBOX_DETAIL: `${API_BASE}/controller/sandboxes/{sandboxId}`,
    HEARTBEAT: `${API_BASE}/controller/sandboxes/{sandboxId}/heartbeat`,
    CLEANUP: `${API_BASE}/controller/sandboxes/cleanup`,
    RUNTIME_ENSURE: `${API_BASE}/controller/sessions/{sessionId}/runtime`,
    RUNTIME_DETAIL: `${API_BASE}/controller/sessions/{sessionId}/runtime`,
    UNIFIED_WS: `${API_BASE}/controller/sessions/{sessionId}/ws/unified`,
  },
  SYSTEM: {
    HEALTH: `${API_BASE}/health`,
    REALTIME_FLAGS: `${API_BASE}/realtime/flags`,
  },
} as const;

export const buildApiUrl = (endpoint: string, params?: Record<string, string>) => {
  let url = endpoint;
  if (params) {
    Object.entries(params).forEach(([k, v]) => url = url.replace(`{${k}}`, v));
  }
  return url;
};
