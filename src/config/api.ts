// src/config/api.ts - Ultra-minimal Contract One API Configuration

const DEFAULT_PROD_API_BASE = 'https://api.yudai.app';

// Auth remains a light REST API on the Python backend. All non-auth app
// traffic defaults to same-origin Node middleware routes.
export const resolveApiBase = (value?: string): string => {
  const raw = (value || '').trim();
  const normalized = raw.trim();

  return normalized === '/' ? '' : normalized.replace(/\/+$/, '');
};

export const resolveAuthApiBase = (value?: string): string => {
  const raw = (value || '').trim();
  const fallback = import.meta.env.PROD ? DEFAULT_PROD_API_BASE : '/api';
  const normalized = (raw || fallback).trim() || fallback;

  return normalized.replace(/\/+$/, '');
};

// VITE_API_BASE_URL points to the Node middleware origin for non-auth app APIs.
// Leave it empty in Vercel so calls stay same-origin.
export const API_BASE = resolveApiBase(import.meta.env.VITE_API_BASE_URL);
export const AUTH_API_BASE = resolveAuthApiBase(import.meta.env.VITE_AUTH_API_BASE_URL);

export const resolveAiApiBase = (value?: string): string => {
  const raw = (value || '').trim();
  const normalized = raw.replace(/\/+$/, '');

  return normalized === '/' ? '' : normalized;
};

export const AI_API_BASE = resolveAiApiBase(import.meta.env.VITE_AI_API_BASE_URL);

export const API = {
  AI: {
    CHAT_STREAM: `${AI_API_BASE}/ai/sessions/{sessionId}/stream`,
  },
  AUTH: {
    LOGIN: `${AUTH_API_BASE}/auth/api/login`,
    CALLBACK: '/auth/callback', // GitHub OAuth redirect (top-level)
    USER: `${AUTH_API_BASE}/auth/api/user`,
    LOGOUT: `${AUTH_API_BASE}/auth/api/logout`,
  },
  GITHUB: {
    REPOS: `${API_BASE}/github/repositories`,
    REPO_BRANCHES: `${API_BASE}/github/repositories/{owner}/{repo}/branches`,
  },
  SESSIONS: {
    BASE: `${API_BASE}/daifu/sessions`,
    DETAIL: `${API_BASE}/daifu/sessions/{sessionId}`,
    MESSAGES: `${API_BASE}/daifu/sessions/{sessionId}/messages`,
    CONTEXT_CARDS: `${API_BASE}/daifu/sessions/{sessionId}/context-cards`,
    CONTEXT_CARD_DETAIL: `${API_BASE}/daifu/sessions/{sessionId}/context-cards/{cardId}`,
    EXECUTION: `${API_BASE}/daifu/sessions/{sessionId}/execution`,
    EXECUTION_CANCEL: `${API_BASE}/daifu/sessions/{sessionId}/execution/cancel`,
    EXECUTION_EVENTS: `${API_BASE}/daifu/sessions/{sessionId}/execution/events`,
    EXECUTION_STOP: `${API_BASE}/daifu/sessions/{sessionId}/execution/stop`,
    CREATE_GITHUB_ISSUE_TOOL: `${API_BASE}/daifu/sessions/{sessionId}/tools/create-github-issue`,
    ASK_QUESTION: `${API_BASE}/daifu/sessions/{sessionId}/ask-question`,
    ANSWER_QUESTION: `${API_BASE}/daifu/sessions/{sessionId}/questions/{questionId}/answer`,
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
    SESSION_EVENTS: `${API_BASE}/realtime/sessions/{sessionId}/events`,
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
