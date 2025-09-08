// src/config/api.ts - Centralized API configuration for YudaiV3 Hybrid Architecture
// This file serves as the single source of truth for all API routes and configuration
// 
// ARCHITECTURE: Hybrid - Standalone + Session-integrated endpoints
// - Standalone routes: Direct frontend access (e.g., repository selection)  
// - Session-integrated routes: Contextual operations within sessions

/**
 * YudaiV3 API Configuration
 * 
 * Architecture Overview:
 * - Authentication: GitHub OAuth and user management
 * - GitHub (Standalone): Direct repository operations for setup/selection
 * - GitHub (Session-integrated): Repository operations within session context
 * - Sessions: Unified session management with embedded functionality
 * 
 * Route Duplication Strategy:
 * GitHub endpoints exist in both contexts intentionally:
 * 1. /github/* - For initial setup and repository selection
 * 2. /daifu/github/* - For session-contextual operations
 */

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

  // Standalone GitHub API (for repository selection and initial setup)
  GITHUB: {
    REPOS: '/github/repositories',
    REPO_BRANCHES: '/github/repositories/{owner}/{repo}/branches',
    USER_REPOS: '/github/repositories',
  },

  // Session-integrated GitHub API (for contextual operations within sessions)
  GITHUB_SESSION: {
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
    STATS: '/daifu/sessions/{sessionId}/stats',
    EXPORT: '/daifu/sessions/{sessionId}/export',
    IMPORT: '/daifu/sessions/import',

    // Session-scoped Issues endpoints
    ISSUES: {
      CREATE_WITH_CONTEXT: '/daifu/sessions/{sessionId}/issues/create-with-context',
      LIST: '/daifu/sessions/{sessionId}/issues',
      DETAIL: '/daifu/sessions/{sessionId}/issues/{issueId}',
      UPDATE_STATUS: '/daifu/sessions/{sessionId}/issues/{issueId}/status',
      CREATE_GITHUB_ISSUE: '/daifu/sessions/{sessionId}/issues/{issueId}/create-github-issue',
    },

    // Session-scoped AI Solver endpoints
    SOLVER: {
      START: '/daifu/sessions/{sessionId}/solve/start',
      SESSION_DETAIL: '/daifu/sessions/{sessionId}/solve/sessions/{solveSessionId}',
      SESSION_STATS: '/daifu/sessions/{sessionId}/solve/sessions/{solveSessionId}/stats',
      CANCEL: '/daifu/sessions/{sessionId}/solve/sessions/{solveSessionId}/cancel',
      LIST_SESSIONS: '/daifu/sessions/{sessionId}/solve/sessions',
      HEALTH: '/daifu/sessions/{sessionId}/solve/health',
    },
  },

  // System endpoints
  SYSTEM: {
    ROOT: '/',
    HEALTH: '/health',
    STATS: '/stats',
    DOCS: '/docs',
    REDOC: '/redoc',
  },

  // Deprecated endpoints (for reference and migration)
  DEPRECATED: {
    ISSUES: {
      BASE: '/issues',
      CREATE_WITH_CONTEXT: '/issues/from-session-enhanced',
      CREATE_GITHUB_ISSUE: '/issues/{issueId}/create-github-issue',
      MIGRATION_NOTE: 'Migrated to /daifu/sessions/{sessionId}/issues/*'
    },
    AI_SOLVER: {
      BASE: '/api/v1',
      SOLVE: '/api/v1/solve',
      MIGRATION_NOTE: 'Migrated to /daifu/sessions/{sessionId}/solve/*'
    }
  }
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

/**
 * Endpoint Usage Guidelines:
 * 
 * 1. Use GITHUB for initial repository selection and setup
 * 2. Use GITHUB_SESSION for repository operations within existing sessions
 * 3. Use SESSIONS for all session-related operations
 * 4. Avoid DEPRECATED endpoints - they exist only for reference
 * 
 * Example Usage:
 * - Repository selection page: API.GITHUB.REPOS
 * - Within chat session: API.GITHUB_SESSION.REPOS  
 * - Session management: API.SESSIONS.BASE
 * - Issue creation in session: API.SESSIONS.ISSUES.CREATE_WITH_CONTEXT
 */

export const API = {
  AUTH: API_CONFIG.AUTH,
  GITHUB: API_CONFIG.GITHUB,           // Standalone GitHub operations
  GITHUB_SESSION: API_CONFIG.GITHUB_SESSION,  // Session-integrated GitHub operations
  SESSIONS: API_CONFIG.SESSIONS,
  SYSTEM: API_CONFIG.SYSTEM,
  
  // Convenience aliases for common operations
  ISSUES: API_CONFIG.SESSIONS.ISSUES,
  SOLVER: API_CONFIG.SESSIONS.SOLVER,
} as const;

/**
 * Router Usage Statistics Types
 */
export interface RouterUsageStats {
  authentication: { count: number; percentage: number };
  github: { count: number; percentage: number };
  sessions: { count: number; percentage: number };
}

export interface EndpointStats {
  endpoint: string;
  requests: number;
  usage_percentage: number;
  avg_response_time_seconds: number;
  error_rate_percentage: number;
  total_errors: number;
}

export interface ApiUsageResponse {
  total_requests: number;
  endpoints: EndpointStats[];
  timestamp: number;
}

export interface ApiRootResponse {
  message: string;
  version: string;
  architecture: string;
  usage_statistics: {
    total_requests: number;
    router_usage: RouterUsageStats;
  };
  services: {
    authentication: {
      prefix: string;
      description: string;
      status: string;
      endpoints: string[];
    };
    github: {
      prefix: string;
      description: string;
      status: string;
      note: string;
      endpoints: string[];
    };
    sessions: {
      prefix: string;
      description: string;
      status: string;
      features: string[];
      key_endpoints: string[];
    };
  };
  deprecated_services: {
    issues: {
      prefix: string;
      status: string;
      migration_path: string;
      description: string;
    };
    'ai-solver': {
      prefix: string;
      status: string;
      migration_path: string;
      description: string;
    };
  };
  route_duplication_strategy: {
    github_routes: {
      standalone: string;
      session_integrated: string;
      rationale: string;
    };
  };
  documentation: {
    swagger: string;
    redoc: string;
    usage_stats: string;
    health: string;
  };
  consolidation_status: string;
}
