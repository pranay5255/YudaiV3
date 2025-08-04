/**
 * Unified State Management Types
 *
 * This file defines the core data structures for the application's state, ensuring
 * consistency between the TypeScript frontend and the Python backend. These types
 * are the "single source of truth" for what our application data looks like.
 * They are synchronized via HTTP API calls and polling.
 */

// ============================================================================
// ENUMS - Consistent across frontend and backend
// ============================================================================

export enum AgentType {
  DAIFU = "daifu",
  ARCHITECT = "architect",
  CODER = "coder",
  TESTER = "tester",
}

export enum AgentStatus {
  IDLE = "idle",
  PROCESSING = "processing",
  COMPLETED = "completed",
  ERROR = "error",
}

export enum MessageRole {
  USER = "user",
  ASSISTANT = "assistant",
  SYSTEM = "system",
}

export enum ContextCardSource {
  CHAT = "chat",
  FILE = "file",
  GITHUB = "github",
  MANUAL = "manual",
}

// Removed WebSocketMessageType - no longer needed without WebSockets


// ============================================================================
// UNIFIED STATE MODELS - These mirror the Python Pydantic models
// ============================================================================

export interface UnifiedRepository {
  owner: string;
  name: string;
  branch: string;
  full_name: string;
  html_url: string;
}

export interface UnifiedMessage {
  id: string;
  session_id: string;
  content: string;
  role: MessageRole;
  is_code: boolean;
  timestamp: string; // ISO 8601 timestamp
  tokens?: number;
  metadata?: Record<string, unknown>;
}

export interface UnifiedContextCard {
  id: string;
  session_id: string;
  title: string;
  description: string;
  content: string;
  tokens: number;
  source: ContextCardSource;
  created_at: string; // ISO 8601 timestamp
}



export interface UnifiedAgentStatus {
  type: AgentType;
  status: AgentStatus;
  current_task?: string;
  progress?: number; // 0-100
  started_at?: string; // ISO 8601 timestamp
  completed_at?: string; // ISO 8601 timestamp
  error_message?: string;
}

export interface UnifiedStatistics {
  total_messages: number;
  total_tokens: number;
  total_cost: number;
  session_duration: number; // in seconds
  agent_actions: number;
  files_processed: number;
}

/**
 * The core session state that is synchronized between the frontend and backend.
 * It should not contain any client-side-only UI state.
 */
export interface User {
  id: number;
  github_username: string;
  display_name: string;
  email: string;
  avatar_url: string;
  github_id: string;
}

export interface UnifiedSessionState {
  session_id: string | null;
  user_id: number | null;
  repository: UnifiedRepository | null;
  messages: UnifiedMessage[];
  context_cards: UnifiedContextCard[];
  agent_status: UnifiedAgentStatus;
  statistics: UnifiedStatistics;
  last_activity: string; // ISO 8601 timestamp
  is_active: boolean;
  user?: User;
}

// ============================================================================
// REMOVED WEBSOCKET TYPES - Using HTTP API only
// ============================================================================

/**
 * The data payload for a context card update, making the action explicit.
 * Kept for potential future HTTP API usage.
 */
export interface ContextCardUpdateData {
    action: 'add' | 'remove' | 'update';
    card: UnifiedContextCard;
}

// ============================================================================
// FRONTEND-ONLY TYPES - Not part of the unified state with the backend
// ============================================================================

export type TabType = 'chat' | 'file-deps' | 'context' | 'ideas';

/**
 * Manages the state of the UI tabs and their refresh triggers.
 * This is client-side state and is NOT synchronized with the backend.
 */
export interface TabState {
  activeTab: TabType;
  refreshKeys: {
    [key in TabType]: number;
  };
  tabHistory: TabType[];
}