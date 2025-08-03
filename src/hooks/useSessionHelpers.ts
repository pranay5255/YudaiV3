import { useCallback } from 'react';
import { useSession } from './useSession';
import { ApiService } from '../services/api';
import { useAuth } from './useAuth';
import { 
  AgentType,
  UnifiedContextCard,
} from '../types/unifiedState';
import { logger } from '../utils/logger';
/**
 * Custom hook for managing session actions.
 * This abstracts away the API calls and state updates, providing clean
 * functions for components to use.
 */
export const useSessionHelpers = () => {
  const { sessionState, setActiveSessionId, sendOptimisticUpdate, sendRealtimeMessage } = useSession();
  const { isAuthenticated } = useAuth();

  // TODO: REPLACE - Replace console.log with proper logging
  const createSession = useCallback(async (
    repoOwner: string,
    repoName: string,
    repoBranch: string = 'main'
  ) => {
    if (!isAuthenticated) {
      throw new Error('User must be authenticated to create a session');
    }
    
    logger.info('Creating session for:', { repoOwner, repoName, repoBranch });
    
    try {
      const session: { session_id?: string, id?: string } = await ApiService.createSession(repoOwner, repoName, repoBranch);
      logger.info('Session creation response:', session);
      
      const sessionId = session.session_id || session.id;
      if (sessionId) {
        logger.info('Setting active session ID:', sessionId);
        setActiveSessionId(sessionId);
        return sessionId;
      } else {
        logger.error('No session ID in response:', session);
        throw new Error("Failed to create session or get a session ID");
      }
    } catch (error) {
      logger.error('Session creation failed:', error);
      throw error;
    }
  }, [isAuthenticated, setActiveSessionId]);

  const sendMessage = useCallback(async (content: string, isCode: boolean = false) => {
    if (!sessionState.session_id) throw new Error('No active session');
    
    // First, send optimistic update for immediate UI feedback
    sendOptimisticUpdate('SEND_MESSAGE', { content, is_code: isCode });
    
    try {
      // Send through real-time WebSocket for immediate broadcasting
      sendRealtimeMessage({
        type: 'SEND_MESSAGE',
        data: {
          session_id: sessionState.session_id,
          content,
          is_code: isCode,
          context_cards: sessionState.context_cards.map((c: UnifiedContextCard) => c.id)
        }
      });
    } catch (error) {
      console.error('Failed to send real-time message:', error);
      
      // Fallback to HTTP API if WebSocket fails
      await ApiService.sendEnhancedChatMessage({
        session_id: sessionState.session_id,
        message: { content, is_code: isCode },
        context_cards: sessionState.context_cards.map((c: UnifiedContextCard) => c.id)
      });
    }
  }, [sessionState.session_id, sessionState.context_cards, sendOptimisticUpdate, sendRealtimeMessage]);

  // TODO: IMPLEMENT - Proper API methods for context cards
  const addContextCard = useCallback(async (card: Omit<UnifiedContextCard, 'id' | 'session_id' | 'created_at'>) => {
    if (!sessionState.session_id) throw new Error('No active session');
    
    // TODO: IMPLEMENT - Call actual API endpoint
    try {
      const response = await ApiService.addContextCard({
        session_id: sessionState.session_id,
        title: card.title,
        description: card.description,
        content: card.content,
        tokens: card.tokens,
        source: card.source
      });
      
      // Send real-time update
      sendRealtimeMessage({
        type: 'CONTEXT_CARD',
        data: { action: 'add', card: response }
      });
    } catch (error) {
      console.error('Failed to add context card:', error);
      throw error;
    }
  }, [sessionState.session_id, sendRealtimeMessage]);
  
  const removeContextCard = useCallback(async (cardId: string) => {
      if (!sessionState.session_id) throw new Error('No active session');
      // In a real implementation, this would call an API endpoint
      console.log('removeContextCard (local simulation):', cardId);
  }, [sessionState.session_id]);



  const startAgent = useCallback(async (agentType: AgentType) => {
      if (!sessionState.session_id) throw new Error('No active session');
      // This should be an API call that then broadcasts a state update
      console.log('startAgent (local simulation):', agentType);
  },[sessionState.session_id]);


  // ... other helper functions like loadSession, clearSession etc.

  return {
    createSession,
    sendMessage,
    addContextCard,
    removeContextCard,
    startAgent,
  };
};
