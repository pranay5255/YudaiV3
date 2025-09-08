// src/config/api.ts - Centralized API configuration
// This file serves as the single source of truth for all API routes and configuration

// Base API configuration
export const API_CONFIG = {
  // Base URLs - ensure proper handling of empty strings
  BASE_URL: (import.meta.env.VITE_API_BASE_URL || '').trim(),
  API_PREFIX: '/api',

  // Service endpoints
  AUTH: {
    LOGIN: '/auth/api/login',
    CALLBACK: '/auth/callback',
    USER: '/auth/api/user',
    LOGOUT: '/auth/api/logout',
  },
  GITHUB: {
    // Ported under DAIFU router
    REPOS: '/daifu/github/repositories',
    REPO_BRANCHES: '/daifu/github/repositories/{owner}/{repo}/branches',
    USER_REPOS: '/daifu/github/repositories',
  },
  SESSIONS: {
    BASE: '/daifu/sessions',
    DETAIL: '/daifu/sessions/{sessionId}',
    MESSAGES: '/daifu/sessions/{sessionId}/messages',
    CHAT: '/daifu/sessions/{sessionId}/chat',
    CONTEXT_CARDS: '/daifu/sessions/{sessionId}/context-cards',
    CONTEXT_CARD_DETAIL: '/daifu/sessions/{sessionId}/context-cards/{cardId}',
    FILE_DEPS_SESSION: '/daifu/sessions/{sessionId}/file-deps/session',
    EXTRACT: '/daifu/sessions/{sessionId}/extract',
    // Consolidated Issues endpoints within sessions context
    ISSUES: {
      CREATE_WITH_CONTEXT: '/daifu/sessions/{sessionId}/issues/create-with-context',
      GET_ISSUES: '/daifu/sessions/{sessionId}/issues',
      CREATE_GITHUB_ISSUE: '/daifu/sessions/{sessionId}/issues/{issueId}/create-github-issue',
      ISSUE_DETAIL: '/daifu/sessions/{sessionId}/issues/{issueId}',
      UPDATE_STATUS: '/daifu/sessions/{sessionId}/issues/{issueId}/status',
    },
    // Consolidated Solver endpoints within sessions context
    SOLVER: {
      START_SOLVE: '/daifu/sessions/{sessionId}/solve/start',
      SOLVE_SESSION_DETAIL: '/daifu/sessions/{sessionId}/solve/sessions/{solveSessionId}',
      SOLVE_SESSION_STATS: '/daifu/sessions/{sessionId}/solve/sessions/{solveSessionId}/stats',
      CANCEL_SOLVE: '/daifu/sessions/{sessionId}/solve/sessions/{solveSessionId}/cancel',
      LIST_SOLVE_SESSIONS: '/daifu/sessions/{sessionId}/solve/sessions',
      SOLVER_HEALTH: '/daifu/sessions/{sessionId}/solve/health',
    },
  },
  // ISSUES section removed - now consolidated under SESSIONS
  // SOLVER section removed - now consolidated under SESSIONS
} as const;

// Improved URL builder
export const buildApiUrl = (endpoint: string, pathParams?: Record<string, string>, queryParams?: Record<string, string>): string => {
  // Ensure endpoint starts with /
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  let url = `${API_CONFIG.BASE_URL}${normalizedEndpoint}`;

  // Replace path parameters
  if (pathParams) {
    Object.entries(pathParams).forEach(([key, value]) => {
      url = url.replace(`{${key}}`, value);
    });
  }

  // Add query parameters
  if (queryParams) {
    const queryString = new URLSearchParams(queryParams).toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  return url;
};

// API request configuration
export const API_REQUEST_CONFIG = {
  DEFAULT_HEADERS: {
    'Content-Type': 'application/json',
  },
  TIMEOUT: 30000, // 30 seconds
} as const;

// CORS and security configuration for development
export const CORS_CONFIG = {
  ALLOWED_ORIGINS: [
    'http://localhost:3000',
    'http://localhost:5173',
    'https://yudai.app',
    'https://www.yudai.app',
  ],
} as const;

export const API = {
  AUTH: API_CONFIG.AUTH,
  SESSIONS: API_CONFIG.SESSIONS,
  // GITHUB,  // Removed as deprecated
  ISSUES: API_CONFIG.SESSIONS.ISSUES,
  SOLVER: API_CONFIG.SESSIONS.SOLVER,
};
