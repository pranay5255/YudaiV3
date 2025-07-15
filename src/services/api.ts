// API service for communicating with the backend
const API_BASE_URL = 'http://localhost:8000';

export interface ChatMessage {
  content: string;
  is_code: boolean;
}

export interface ChatRequest {
  conversationId?: string;
  message: ChatMessage;
  contextCards?: string[];
  repoOwner?: string;
  repoName?: string;
}

export interface ChatResponse {
  reply: string;
  conversation: [string, string][];
  message_id: string;
  processing_time: number;
}

export class ApiService {
  static async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/chat/daifu`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }
} 