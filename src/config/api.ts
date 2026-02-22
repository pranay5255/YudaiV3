// src/config/api.ts - Ultra-minimal Contract One API Configuration

// Contract One: All API calls through /api/* umbrella
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim();

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
    SOLVER: {
      START: `${API_BASE}/daifu/sessions/{sessionId}/solve/start`,
      STATUS: `${API_BASE}/daifu/sessions/{sessionId}/solve/status/{solveSessionId}`,
      CANCEL: `${API_BASE}/daifu/sessions/{sessionId}/solve/cancel/{solveSessionId}`,
      STREAM: `${API_BASE}/daifu/sessions/{sessionId}/solve/stream/{solveId}/{runId}`,
    },
  },
  CONTROLLER: {
    SANDBOXES: `${API_BASE}/controller/sandboxes`,
    SANDBOX_DETAIL: `${API_BASE}/controller/sandboxes/{sandboxId}`,
    RESOLVE_TUNNEL: `${API_BASE}/controller/sandboxes/{sandboxId}/resolve-tunnel`,
    HEARTBEAT: `${API_BASE}/controller/sandboxes/{sandboxId}/heartbeat`,
    CLEANUP: `${API_BASE}/controller/sandboxes/cleanup`,
    RUNTIME_ENSURE: `${API_BASE}/controller/sessions/{sessionId}/runtime`,
    RUNTIME_DETAIL: `${API_BASE}/controller/sessions/{sessionId}/runtime`,
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
