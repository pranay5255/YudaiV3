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
  DAIFU: {
    CHAT: '/daifu/chat',
    SESSIONS: '/daifu',
  },
  ISSUES: {
    CREATE_WITH_CONTEXT: '/issues/from-session-enhanced',
    GET_ISSUES: '/issues',
    CREATE_GITHUB_ISSUE: '/issues/{issueId}/create-github-issue',
  },
  FILEDEPS: {
    EXTRACT: '/filedeps/extract',
  },
  SOLVER: {
    SOLVE: '/api/v1/solve',
  },
} as const;

// Type-safe API URL builder
export const buildApiUrl = (endpoint: string, params?: Record<string, string>): string => {
  let url = `${API_CONFIG.BASE_URL}${endpoint}`;

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url = url.replace(`{${key}}`, value);
    });
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
