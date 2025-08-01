/**
 * Enhanced WebSocket Manager for Real-Time Updates
 * 
 * Handles:
 * - Race condition prevention through message queuing
 * - Automatic reconnection with exponential backoff
 * - Memory leak prevention with proper cleanup
 * - Optimistic updates for immediate UI feedback
 * - Message batching to reduce state update frequency
 */

import { 
  UnifiedWebSocketMessage, 
  WebSocketMessageType,
  UnifiedMessage,
  UnifiedContextCard,
  UnifiedAgentStatus,
} from '../types/unifiedState';

interface RealTimeManagerOptions {
  sessionId: string;
  token: string;
  onMessage: (data: RealTimeUpdate) => void;
  onError: (error: Error) => void;
  onConnectionStatusChange: (status: 'connected' | 'disconnected' | 'reconnecting') => void;
}

interface QueuedMessage {
  id: string;
  type: WebSocketMessageType;
  data: unknown;
  timestamp: number;
}

interface RealTimeUpdate {
  type: WebSocketMessageType;
  data: unknown;
  timestamp: number;
}

interface BatchedContextCardUpdate {
  action: 'batch';
  cards: UnifiedContextCard[];
}

/**
 * Enhanced WebSocket Manager with proper real-time updates
 */
export class RealTimeManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private messageQueue: QueuedMessage[] = [];
  private isProcessing = false;
  private lastUpdateTimestamps: Record<string, number> = {};
  private pendingUpdates = new Set<string>();
  private lastHeartbeatTime: number | null = null;
  private connectionStartTime: number | null = null;

  constructor(private options: RealTimeManagerOptions) {}

  /**
   * Establish WebSocket connection
   */
  connect(): void {
    const wsUrl = this.buildWebSocketUrl();
    console.log('🔌 Connecting to WebSocket:', wsUrl);
    
    this.ws = new WebSocket(wsUrl);
    this.options.onConnectionStatusChange('reconnecting');

    this.ws.onopen = () => {
      console.log('✅ WebSocket connected');
      this.reconnectAttempts = 0;
      this.options.onConnectionStatusChange('connected');
      this.startHeartbeat();
      this.processMessageQueue();
      this.connectionStartTime = Date.now();
    };

    this.ws.onmessage = (event) => {
      try {
        const message: UnifiedWebSocketMessage = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
        // Send error message to UI
        this.options.onMessage({
          type: WebSocketMessageType.ERROR,
          data: { message: 'Failed to parse message', error: error instanceof Error ? error.message : 'Unknown error' },
          timestamp: Date.now()
        });
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      // Convert Event to Error properly
      const errorMessage = error instanceof Error ? error.message : 'WebSocket connection error';
      this.options.onError(new Error(errorMessage));
      // Don't change connection status here, let onclose handle it
    };

    this.ws.onclose = (event) => {
      console.log('🔌 WebSocket closed:', event.code, event.reason);
      this.stopHeartbeat();
      
      // Handle different close codes
      if (event.code === 1000) {
        // Normal closure
        this.options.onConnectionStatusChange('disconnected');
      } else if (event.code === 1008) {
        // Policy violation (authentication failed)
        console.error('Authentication failed for WebSocket connection');
        this.options.onError(new Error('Authentication failed. Please log in again.'));
        this.options.onConnectionStatusChange('disconnected');
      } else if (event.code === 1011) {
        // Internal error
        console.error('Server error in WebSocket connection');
        this.options.onError(new Error('Server error. Please try again later.'));
        this.handleReconnection();
      } else {
        // Other errors, attempt reconnection
        this.handleReconnection();
      }
    };
  }

  /**
   * Disconnect WebSocket
   */
  disconnect(): void {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close(1000, 'User initiated disconnect');
      this.ws = null;
    }
    this.options.onConnectionStatusChange('disconnected');
  }

  /**
   * Send message through WebSocket with queuing support
   */
  send(message: Record<string, unknown>): void {
    const messageWithId = {
      ...message,
      id: `${Date.now()}-${Math.random()}`,
      timestamp: Date.now()
    };

    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(messageWithId));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
        this.queueMessage(messageWithId as QueuedMessage);
      }
    } else {
      console.log('⏳ WebSocket not ready, queuing message');
      this.queueMessage(messageWithId as QueuedMessage);
    }
  }

  /**
   * Build WebSocket URL with proper prefix handling
   */
  private buildWebSocketUrl(): string {
    const baseUrl = import.meta.env.VITE_API_URL || 
      (import.meta.env.DEV ? 'http://localhost:8000' : 'https://yudai.app');
    
    // Remove /api prefix if present for WebSocket connections
    const cleanBaseUrl = baseUrl.replace('/api', '');
    
    // Convert to WebSocket URL
    const wsUrl = cleanBaseUrl.replace('http', 'ws').replace('https', 'wss');
    
    return `${wsUrl}/daifu/sessions/${this.options.sessionId}/ws?token=${this.options.token}`;
  }

  /**
   * Handle incoming WebSocket messages with race condition prevention
   */
  private handleMessage(message: UnifiedWebSocketMessage): void {
    // Generate unique update ID to prevent duplicates
    const updateId = `${message.type}-${message.timestamp || Date.now()}`;
    
    // Skip if we've already processed this update recently
    if (this.pendingUpdates.has(updateId)) {
      console.log('⏭️ Skipping duplicate update:', updateId);
      return;
    }

    // Check if this update is newer than the last one for this type
    const lastUpdate = this.lastUpdateTimestamps[message.type] || 0;
    const currentTimestamp = message.timestamp ? new Date(message.timestamp).getTime() : Date.now();
    
    if (currentTimestamp < lastUpdate) {
      console.log('⏭️ Skipping outdated update:', message.type);
      return;
    }

    // Track this update
    this.pendingUpdates.add(updateId);
    this.lastUpdateTimestamps[message.type] = currentTimestamp;

    // Queue the message for processing
    this.queueMessage({
      id: updateId,
      type: message.type,
      data: message.data,
      timestamp: currentTimestamp
    });

    // Clean up update ID after a short delay
    setTimeout(() => {
      this.pendingUpdates.delete(updateId);
    }, 1000);
  }

  /**
   * Queue message for batch processing
   */
  private queueMessage(message: QueuedMessage): void {
    this.messageQueue.push(message);
    
    if (!this.isProcessing) {
      // Use microtask for immediate processing
      queueMicrotask(() => this.processMessageQueue());
    }
  }

  /**
   * Process queued messages in batches to prevent race conditions
   */
  private processMessageQueue(): void {
    if (this.messageQueue.length === 0 || this.isProcessing) return;

    this.isProcessing = true;
    
    try {
      // Get all pending messages
      const messages = [...this.messageQueue];
      this.messageQueue = [];

      // Group messages by type for batching
      const groupedMessages = this.groupMessagesByType(messages);
      
      // Process each group
      Object.entries(groupedMessages).forEach(([type, msgs]) => {
        const batchedUpdate = this.batchMessages(type as WebSocketMessageType, msgs);
        if (batchedUpdate) {
          this.options.onMessage(batchedUpdate);
        }
      });

    } catch (error) {
      console.error('Error processing message queue:', error);
    } finally {
      this.isProcessing = false;
      
      // Process any new messages that arrived during processing
      if (this.messageQueue.length > 0) {
        setTimeout(() => this.processMessageQueue(), 0);
      }
    }
  }

  /**
   * Group messages by type for batch processing
   */
  private groupMessagesByType(messages: QueuedMessage[]): Record<string, QueuedMessage[]> {
    return messages.reduce((acc, msg) => {
      const type = msg.type;
      if (!acc[type]) acc[type] = [];
      acc[type].push(msg);
      return acc;
    }, {} as Record<string, QueuedMessage[]>);
  }

  /**
   * Batch messages of the same type to prevent conflicting updates
   */
  private batchMessages(type: WebSocketMessageType, messages: QueuedMessage[]): RealTimeUpdate | null {
    if (messages.length === 0) return null;

    switch (type) {
      case WebSocketMessageType.MESSAGE: {
        // For messages, only take the latest to prevent duplicates
        const latestMessage = messages[messages.length - 1];
        return {
          type,
          data: latestMessage.data as UnifiedMessage,
          timestamp: latestMessage.timestamp
        };
      }

      case WebSocketMessageType.SESSION_UPDATE: {
        // For session updates, merge all updates with latest taking precedence
        const mergedSession = messages.reduce((latest, current) => 
          current.timestamp > latest.timestamp ? current : latest
        );
        return {
          type,
          data: mergedSession.data,
          timestamp: mergedSession.timestamp
        };
      }

      case WebSocketMessageType.CONTEXT_CARD: {
        // For context cards, batch all operations
        const batchedUpdate: BatchedContextCardUpdate = {
          action: 'batch',
          cards: messages.map(m => m.data as UnifiedContextCard)
        };
        return {
          type,
          data: batchedUpdate,
          timestamp: Math.max(...messages.map(m => m.timestamp))
        };
      }

      case WebSocketMessageType.AGENT_STATUS: {
        // For agent status, only keep the latest
        const latestStatus = messages[messages.length - 1];
        return {
          type,
          data: latestStatus.data as UnifiedAgentStatus,
          timestamp: latestStatus.timestamp
        };
      }


      case WebSocketMessageType.HEARTBEAT:
        // Heartbeat responses don't need processing
        return null;

      case WebSocketMessageType.ERROR: {
        // Process all errors
        messages.forEach(msg => {
          console.error('WebSocket error:', msg.data);
        });
        return null;
      }

      default: {
        // For unknown types, just take the latest
        const latest = messages[messages.length - 1];
        return {
          type,
          data: latest.data,
          timestamp: latest.timestamp
        };
      }
    }
  }

  /**
   * Start heartbeat to keep connection alive
   */
  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ 
          type: WebSocketMessageType.HEARTBEAT, 
          timestamp: Date.now() 
        });
        this.lastHeartbeatTime = Date.now();
      }
    }, 30000); // 30 second heartbeat
  }

  /**
   * Stop heartbeat
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * Handle reconnection with exponential backoff and user feedback
   */
  private handleReconnection(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(
        this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 
        30000
      );
      
      console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      
      // Notify UI about reconnection attempt
      this.options.onMessage({
        type: WebSocketMessageType.AGENT_STATUS,
        data: { 
          status: 'reconnecting',
          message: `Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`,
          reconnectDelay: delay
        },
        timestamp: Date.now()
      });
      
      this.options.onConnectionStatusChange('reconnecting');
      
      setTimeout(() => {
        console.log(`🔄 Attempting reconnection...`);
        this.connect();
      }, delay);
    } else {
      console.error('❌ Max reconnection attempts reached');
      this.options.onError(new Error('WebSocket connection failed permanently. Please refresh the page.'));
      this.options.onConnectionStatusChange('disconnected');
      
      // Notify UI about permanent failure
      this.options.onMessage({
        type: WebSocketMessageType.ERROR,
        data: { 
          message: 'Connection failed permanently. Please refresh the page.',
          permanent: true
        },
        timestamp: Date.now()
      });
    }
  }

  /**
   * Get current connection status
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get reconnection attempt count
   */
  get reconnectionAttempts(): number {
    return this.reconnectAttempts;
  }

  /**
   * Get connection health status
   */
  getConnectionHealth(): {
    isConnected: boolean;
    reconnectAttempts: number;
    maxReconnectAttempts: number;
    lastHeartbeat: number | null;
    connectionAge: number | null;
  } {
    return {
      isConnected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.maxReconnectAttempts,
      lastHeartbeat: this.lastHeartbeatTime || null,
      connectionAge: this.connectionStartTime ? Date.now() - this.connectionStartTime : null
    };
  }
}