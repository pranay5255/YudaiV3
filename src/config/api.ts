// src/config/api.ts - Centralized API configuration
// This file serves as the single source of truth for all API routes and configuration

// Base API configuration
export const API_CONFIG = {
  // Base URLs
  BASE_URL: import.meta.env.VITE_API_BASE_URL || '',
  API_PREFIX: '/api',

  // Service endpoints
  AUTH: {
    LOGIN: '/auth/api/login',
    CALLBACK: '/auth/callback',
    USER: '/auth/api/user',
    LOGOUT: '/auth/api/logout',
  },
  GITHUB: {
    REPOS: '/github/repositories',
    REPO_BRANCHES: '/github/repositories/{owner}/{repo}/branches',
    USER_REPOS: '/github/repositories',
  },
  SESSIONS: {
    BASE: '/daifu',
    DETAIL: '/daifu/{sessionId}',
    MESSAGES: '/daifu/{sessionId}/messages',
    CHAT: '/daifu/{sessionId}/chat',
    CONTEXT_CARDS: '/daifu/{sessionId}/context-cards',
    CONTEXT_CARD_DETAIL: '/daifu/{sessionId}/context-cards/{cardId}',
    FILE_DEPS_SESSION: '/daifu/{sessionId}/file-deps/session',
    EXTRACT: '/daifu/{sessionId}/extract',
    // Consolidated Issues endpoints within sessions context
    ISSUES: {
      CREATE_WITH_CONTEXT: '/daifu/{sessionId}/issues/create-with-context',
      GET_ISSUES: '/daifu/{sessionId}/issues',
      CREATE_GITHUB_ISSUE: '/daifu/{sessionId}/issues/{issueId}/create-github-issue',
      ISSUE_DETAIL: '/daifu/{sessionId}/issues/{issueId}',
      UPDATE_STATUS: '/daifu/{sessionId}/issues/{issueId}/status',
    },
    // Consolidated Solver endpoints within sessions context
    SOLVER: {
      START_SOLVE: '/daifu/{sessionId}/solve/start',
      SOLVE_SESSION_DETAIL: '/daifu/{sessionId}/solve/sessions/{solveSessionId}',
      SOLVE_SESSION_STATS: '/daifu/{sessionId}/solve/sessions/{solveSessionId}/stats',
      CANCEL_SOLVE: '/daifu/{sessionId}/solve/sessions/{solveSessionId}/cancel',
      LIST_SOLVE_SESSIONS: '/daifu/{sessionId}/solve/sessions',
      SOLVER_HEALTH: '/daifu/{sessionId}/solve/health',
    },
  },
  // ISSUES section removed - now consolidated under SESSIONS
  // SOLVER section removed - now consolidated under SESSIONS
} as const;

// Type-safe API URL builder
export const buildApiUrl = (endpoint: string, pathParams?: Record<string, string>, queryParams?: Record<string, string>): string => {
  let url = `${API_CONFIG.BASE_URL}${endpoint}`;

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
  AUTH,
  SESSIONS,
  // GITHUB,  // Removed as deprecated
  ISSUES,
  SOLVE,
};
