// DEPRECATED: This service is being phased out in favor of unified sessionStore + useSessionQueries
// All session operations should now go through the session context via Zustand store
//
// Migration Guide:
// - Session creation: Use useCreateSession() or useCreateSessionFromRepository()
// - Session context: Use useSession() hook
// - Messages: Use useChatMessages() hook
// - Context cards: Use useContextCards() and related mutations
// - File dependencies: Use useFileDependencies() hook
// - All other operations: Use appropriate hooks from useSessionQueries.ts

import type {
  CreateSessionRequest,
  Session,
  SessionContext,
  ChatMessage,
  ContextCard,
  CreateContextCardRequest,
  FileItem,
  ExtractFileDependenciesResponse,
  ExtractFileDependenciesRequest,
} from '../types/sessionTypes';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const getAuthHeaders = (sessionToken?: string): HeadersInit => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = sessionToken || localStorage.getItem('session_token') || undefined;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    let errorMessage = `HTTP error! status: ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      // ignore parse errors
    }
    throw new Error(errorMessage);
  }
  return response.json() as Promise<T>;
};

export const sessionApi = {
  // Session management
  async createSession(request: CreateSessionRequest, sessionToken?: string): Promise<Session> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return handleResponse<Session>(response);
  },

  async getSessionContext(sessionId: string, sessionToken?: string): Promise<SessionContext> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<SessionContext>(response);
  },







  async getChatMessages(sessionId: string, limit = 100, sessionToken?: string): Promise<ChatMessage[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages?limit=${limit}`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<ChatMessage[]>(response);
  },





  // Context cards
  async addContextCard(sessionId: string, request: CreateContextCardRequest, sessionToken?: string): Promise<ContextCard> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return handleResponse<ContextCard>(response);
  },

  async getContextCards(sessionId: string, sessionToken?: string): Promise<ContextCard[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<ContextCard[]>(response);
  },

  async deleteContextCard(sessionId: string, cardId: number, sessionToken?: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards/${cardId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<{ success: boolean; message: string }>(response);
  },

  // File dependencies


  async getFileDependenciesSession(sessionId: string, sessionToken?: string): Promise<FileItem[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/file-deps/session`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<FileItem[]>(response);
  },

  async extractFileDependenciesForSession(sessionId: string, repoUrl: string, sessionToken?: string): Promise<ExtractFileDependenciesResponse> {
    const response = await fetch(`${API_BASE_URL}/filedeps/sessions/${sessionId}/extract`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify({ repo_url: repoUrl } as ExtractFileDependenciesRequest),
    });
    return handleResponse<ExtractFileDependenciesResponse>(response);
  },


};

export type {
  Session,
  SessionContext,
  ChatMessage,
  ContextCard,
  FileItem,
  CreateContextCardRequest,
};

export default sessionApi;

