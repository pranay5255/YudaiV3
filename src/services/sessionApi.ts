import type {
  CreateSessionDaifuRequest,
  SessionResponse,
  SessionContextResponse,
  CreateChatMessageRequest,
  ChatMessageResponse,
  ContextCardResponse,
  CreateContextCardRequest,
  CreateFileEmbeddingRequest,
  FileEmbeddingResponse,
  ExtractFileDependenciesResponse,
  ExtractFileDependenciesRequest,
} from '../types/api';

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
  async createSession(request: CreateSessionDaifuRequest, sessionToken?: string): Promise<SessionResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return handleResponse<SessionResponse>(response);
  },

  async getSessionContext(sessionId: string, sessionToken?: string): Promise<SessionContextResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<SessionContextResponse>(response);
  },

  async getUserSessions(sessionToken?: string): Promise<SessionResponse[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<SessionResponse[]>(response);
  },

  async updateSession(sessionId: string, updates: Partial<SessionResponse>, sessionToken?: string): Promise<SessionResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'PUT',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(updates),
    });
    return handleResponse<SessionResponse>(response);
  },

  async deleteSession(sessionId: string, sessionToken?: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<{ success: boolean; message: string }>(response);
  },

  // Chat messages
  async addChatMessage(sessionId: string, request: CreateChatMessageRequest, sessionToken?: string): Promise<ChatMessageResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return handleResponse<ChatMessageResponse>(response);
  },

  async getChatMessages(sessionId: string, limit = 100, sessionToken?: string): Promise<ChatMessageResponse[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages?limit=${limit}`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<ChatMessageResponse[]>(response);
  },

  async updateChatMessage(
    sessionId: string,
    messageId: string,
    updates: Partial<ChatMessageResponse>,
    sessionToken?: string
  ): Promise<ChatMessageResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages/${messageId}`, {
      method: 'PUT',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(updates),
    });
    return handleResponse<ChatMessageResponse>(response);
  },

  async deleteChatMessage(sessionId: string, messageId: string, sessionToken?: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages/${messageId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<{ success: boolean; message: string }>(response);
  },

  // Context cards
  async addContextCard(sessionId: string, request: CreateContextCardRequest, sessionToken?: string): Promise<ContextCardResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return handleResponse<ContextCardResponse>(response);
  },

  async getContextCards(sessionId: string, sessionToken?: string): Promise<ContextCardResponse[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<ContextCardResponse[]>(response);
  },

  async deleteContextCard(sessionId: string, cardId: number, sessionToken?: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards/${cardId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<{ success: boolean; message: string }>(response);
  },

  // File dependencies
  async addFileDependency(sessionId: string, request: CreateFileEmbeddingRequest, sessionToken?: string): Promise<FileEmbeddingResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/file-deps`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return handleResponse<FileEmbeddingResponse>(response);
  },

  async getFileDependenciesSession(sessionId: string, sessionToken?: string): Promise<FileEmbeddingResponse[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/file-deps/session`, {
      method: 'GET',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<FileEmbeddingResponse[]>(response);
  },

  async extractFileDependenciesForSession(sessionId: string, repoUrl: string, sessionToken?: string): Promise<ExtractFileDependenciesResponse> {
    const response = await fetch(`${API_BASE_URL}/filedeps/sessions/${sessionId}/extract`, {
      method: 'POST',
      headers: getAuthHeaders(sessionToken),
      body: JSON.stringify({ repo_url: repoUrl } as ExtractFileDependenciesRequest),
    });
    return handleResponse<ExtractFileDependenciesResponse>(response);
  },

  async deleteFileDependency(sessionId: string, fileId: number, sessionToken?: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/file-deps/${fileId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(sessionToken),
    });
    return handleResponse<{ success: boolean; message: string }>(response);
  },
};

export type {
  SessionResponse,
  SessionContextResponse,
  ChatMessageResponse,
  ContextCardResponse,
  FileEmbeddingResponse,
  CreateChatMessageRequest,
  CreateContextCardRequest,
  CreateFileEmbeddingRequest,
};

export default sessionApi;

