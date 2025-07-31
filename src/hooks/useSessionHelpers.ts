import { useCallback } from 'react';
import { useSession } from './useSession';
import { ApiService } from '../services/api';
import { useAuth } from './useAuth';
import { 
  AgentType,
  UnifiedContextCard,
  UnifiedFileEmbedding,
} from '../types/unifiedState';

/**
 * Custom hook for managing session actions.
 * This abstracts away the API calls and state updates, providing clean
 * functions for components to use.
 */
export const useSessionHelpers = () => {
  const { sessionState, setActiveSessionId } = useSession();
  const { isAuthenticated } = useAuth();

  const createSession = useCallback(async (
    repoOwner: string,
    repoName: string,
    repoBranch: string = 'main'
  ) => {
    if (!isAuthenticated) {
      throw new Error('User must be authenticated to create a session');
    }
    const session: { session_id?: string, id?: string } = await ApiService.createSession(repoOwner, repoName, repoBranch);
    const sessionId = session.session_id || session.id;
    if (sessionId) {
      setActiveSessionId(sessionId);
    } else {
        throw new Error("Failed to create session or get a session ID");
    }
    return sessionId;
  }, [isAuthenticated, setActiveSessionId]);

  const sendMessage = useCallback(async (content: string, isCode: boolean = false) => {
    if (!sessionState.session_id) throw new Error('No active session');
    
    // Use the v2 endpoint, which will handle broadcasting via WebSocket
    await ApiService.sendEnhancedChatMessage({
      session_id: sessionState.session_id,
      message: { content, is_code: isCode },
      context_cards: sessionState.context_cards.map((c: UnifiedContextCard) => c.id),
      file_context: sessionState.file_embeddings.map((f: UnifiedFileEmbedding) => f.id.toString())
    });

  }, [sessionState.session_id, sessionState.context_cards, sessionState.file_embeddings]);

  const addContextCard = useCallback(async (card: Omit<UnifiedContextCard, 'id' | 'session_id' | 'created_at'>) => {
    if (!sessionState.session_id) throw new Error('No active session');
    // In a real implementation, this would call an API endpoint
    // The backend would then broadcast the update.
    console.log('addContextCard (local simulation):', card);
  }, [sessionState.session_id]);
  
  const removeContextCard = useCallback(async (cardId: string) => {
      if (!sessionState.session_id) throw new Error('No active session');
      // In a real implementation, this would call an API endpoint
      console.log('removeContextCard (local simulation):', cardId);
  }, [sessionState.session_id]);

  const addFileContext = useCallback(async (file: UnifiedFileEmbedding) => {
    if (!sessionState.session_id) throw new Error('No active session');
    // In a real implementation, this would call an API endpoint
    console.log('addFileContext (local simulation):', file);
  }, [sessionState.session_id]);

  const removeFileContext = useCallback(async (fileId: number) => {
      if (!sessionState.session_id) throw new Error('No active session');
      // In a real implementation, this would call an API endpoint
      console.log('removeFileContext (local simulation):', fileId);
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
    addFileContext,
    removeFileContext,
    startAgent,
  };
};
