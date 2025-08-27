/**
 * React Query hooks for session management
 * Handles server state and caching for sessions, messages, context cards, and file dependencies
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSessionStore } from '../stores/sessionStore';
import {
  ChatMessageAPI,
  ContextCard,
  FileItem,
  CreateSessionMutationData,
  AddContextCardMutationData,
  RemoveContextCardMutationData,
  ContextCardMutationContext,
  SelectedRepository,
} from '../types';
import {
  sessionApi,
  type ChatMessageResponse,
  type ContextCardResponse,
  type SessionResponse,
} from '../services/sessionApi';

// Helper function to check if error is a session not found error
const isSessionNotFoundError = (error: unknown): boolean => {
  if (error instanceof Error) {
    return error.message.includes('Session not found') ||
           error.message.includes('404') ||
           error.message.includes('Not Found');
  }
  return false;
};

// Helper function to handle session errors by clearing invalid session
const handleSessionError = (error: unknown, sessionId: string, clearSession: () => void) => {
  if (isSessionNotFoundError(error)) {
    console.warn(`[useSessionQueries] Session ${sessionId} not found, clearing invalid session`);
    clearSession();
    return true; // Indicates session was cleared
  }
  return false; // Other type of error
};

// Exponential backoff retry configuration
const getRetryDelay = (attemptIndex: number): number => {
  // Base delay of 1 second, exponentially increasing: 1s, 2s, 4s
  return Math.min(1000 * Math.pow(2, attemptIndex), 8000);
};

// Custom retry function with exponential backoff
const retryWithBackoff = (failureCount: number, error: unknown) => {
  // Don't retry session not found errors
  if (isSessionNotFoundError(error)) {
    return false;
  }
  
  // Don't retry authentication errors
  if (error instanceof Error && error.message.includes('401')) {
    return false;
  }
  
  // Retry up to 3 times for other errors (network issues, server errors, etc.)
  return failureCount < 3;
};

// Query keys for consistent cache management
export const QueryKeys = {
  sessions: ['sessions'] as const,
  session: (sessionId: string) => ['session', sessionId] as const,
  messages: (sessionId: string) => ['messages', sessionId] as const,
  contextCards: (sessionId: string) => ['context-cards', sessionId] as const,
  fileDependencies: (sessionId: string) => ['file-deps', sessionId] as const,
  repositories: ['repositories'] as const,
};



export const useSession = (sessionId: string) => {
  const { setMessages, sessionToken, clearSession } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.session(sessionId),
    queryFn: async () => {
      try {
        const context = await sessionApi.getSessionContext(sessionId, sessionToken || undefined);
        
        // Transform messages to frontend format
        const transformedMessages: ChatMessageAPI[] = context.messages?.map((msg: ChatMessageResponse) => ({
          id: msg.id,
          message_id: msg.message_id,
          message_text: msg.message_text,
          sender_type: msg.sender_type as 'user' | 'assistant' | 'system',
          role: msg.role as 'user' | 'assistant' | 'system',
          tokens: msg.tokens,
          model_used: msg.model_used,
          processing_time: msg.processing_time,
          context_cards: msg.context_cards,
          referenced_files: msg.referenced_files,
          error_message: msg.error_message,
          created_at: msg.created_at,
          updated_at: msg.updated_at,
        })) || [];
        
        // Update Zustand store with transformed data
        setMessages(transformedMessages);
        
        return context;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty state to prevent further queries
          return { messages: [], context_cards: [], file_dependencies: [] };
        }
        throw error; // Re-throw non-session errors
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Chat message queries
export const useChatMessages = (sessionId: string) => {
  const { setMessages, sessionToken, clearSession } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.messages(sessionId),
    queryFn: async (): Promise<ChatMessageAPI[]> => {
      try {
        const messages = await sessionApi.getChatMessages(sessionId, 100, sessionToken || undefined);
        
        // Transform messages to frontend format
        const transformedMessages: ChatMessageAPI[] = messages.map((msg: ChatMessageResponse) => ({
          id: msg.id,
          message_id: msg.message_id,
          message_text: msg.message_text,
          sender_type: msg.sender_type as 'user' | 'assistant' | 'system',
          role: msg.role as 'user' | 'assistant' | 'system',
          tokens: msg.tokens,
          model_used: msg.model_used,
          processing_time: msg.processing_time,
          context_cards: msg.context_cards,
          referenced_files: msg.referenced_files,
          error_message: msg.error_message,
          created_at: msg.created_at,
          updated_at: msg.updated_at,
        }));
        
        // Update Zustand store
        setMessages(transformedMessages);
        
        return transformedMessages;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty messages
          return [];
        }
        throw error; // Re-throw non-session errors
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
};




// Context card queries
export const useContextCards = (sessionId: string) => {
  const { setContextCards, sessionToken, clearSession } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.contextCards(sessionId),
    queryFn: async (): Promise<ContextCard[]> => {
      try {
        const cards = await sessionApi.getContextCards(sessionId, sessionToken || undefined);
        
        // Transform and update Zustand store
        const transformedCards: ContextCard[] = cards.map(card => ({
          id: card.id.toString(),
          title: card.title,
          description: card.description,
          tokens: card.tokens,
          source: card.source as 'chat' | 'file-deps' | 'upload',
        }));
        
        setContextCards(transformedCards);
        
        return transformedCards;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty context cards
          return [];
        }
        throw error; // Re-throw non-session errors
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

export const useAddContextCard = () => {
  const queryClient = useQueryClient();
  const { addContextCard, sessionToken } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ sessionId, card }: AddContextCardMutationData) => {
      return await sessionApi.addContextCard(sessionId, card, sessionToken || undefined);
    },
    onMutate: async ({ sessionId, card }): Promise<ContextCardMutationContext> => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: QueryKeys.contextCards(sessionId) });
      
      // Snapshot the previous value
      const previousCards = queryClient.getQueryData<ContextCard[]>(QueryKeys.contextCards(sessionId)) || [];
      
      // Optimistically update the cache
      const optimisticCard: ContextCard = {
        id: Date.now().toString(),
        title: card.title,
        description: card.description,
        tokens: card.tokens,
        source: card.source,
      };
      
      queryClient.setQueryData(QueryKeys.contextCards(sessionId), (old: ContextCard[] = []) => [
        ...old,
        optimisticCard,
      ]);
      
      // Update Zustand store optimistically
      addContextCard(optimisticCard);
      
      return { previousCards, optimisticCard };
    },
    onError: (_err: Error, { sessionId }: AddContextCardMutationData, context?: ContextCardMutationContext) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousCards) {
        queryClient.setQueryData(QueryKeys.contextCards(sessionId), context.previousCards);
      }
    },
    onSuccess: (data: ContextCardResponse, { sessionId }: AddContextCardMutationData) => {
      // Transform the response and update stores with real data
      const newCard: ContextCard = {
        id: data.id.toString(),
        title: data.title,
        description: data.description,
        tokens: data.tokens,
        source: data.source as 'chat' | 'file-deps' | 'upload',
      };
      
      // Update cache with real data
      queryClient.setQueryData(QueryKeys.contextCards(sessionId), (old: ContextCard[] = []) => {
        // Replace optimistic entry with real data
        return old.map(card => 
          card.id === data.id.toString() ? newCard : card
        ).filter((card, index, self) => 
          self.findIndex(c => c.title === card.title && c.description === card.description) === index
        );
      });
      
      // Update Zustand store with real data
      addContextCard(newCard);
    },
    onSettled: (_data: ContextCardResponse | undefined, _error: Error | null, { sessionId }: AddContextCardMutationData) => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: QueryKeys.contextCards(sessionId) });
    },
  });
};

export const useRemoveContextCard = () => {
  const queryClient = useQueryClient();
  const { removeContextCard, sessionToken } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ sessionId, cardId }: RemoveContextCardMutationData) => {
      return await sessionApi.deleteContextCard(sessionId, parseInt(cardId), sessionToken || undefined);
    },
    onMutate: async ({ sessionId, cardId }): Promise<ContextCardMutationContext> => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: QueryKeys.contextCards(sessionId) });
      
      // Snapshot the previous value
      const previousCards = queryClient.getQueryData<ContextCard[]>(QueryKeys.contextCards(sessionId)) || [];
      
      // Optimistically update the cache
      queryClient.setQueryData(QueryKeys.contextCards(sessionId), (old: ContextCard[] = []) =>
        old.filter(card => card.id !== cardId)
      );
      
      // Update Zustand store optimistically
      removeContextCard(cardId);
      
      return { previousCards };
    },
    onError: (_err: Error, { sessionId }: RemoveContextCardMutationData, context?: ContextCardMutationContext) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousCards) {
        queryClient.setQueryData(QueryKeys.contextCards(sessionId), context.previousCards);
      }
    },
    onSettled: (_data: { success: boolean; message: string } | undefined, _error: Error | null, { sessionId }: RemoveContextCardMutationData) => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: QueryKeys.contextCards(sessionId) });
    },
  });
};

// File dependency queries
export const useFileDependencies = (sessionId: string) => {
  const { setFileContext, sessionToken, clearSession } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.fileDependencies(sessionId),
    queryFn: async (): Promise<FileItem[]> => {
      try {
        const deps = await sessionApi.getFileDependenciesSession(sessionId, sessionToken || undefined);
        
        // Transform and update Zustand store
        const transformedFiles: FileItem[] = deps.map(dep => ({
          id: dep.id.toString(),
          name: dep.file_name,
          path: dep.file_path,
          type: 'INTERNAL' as const,
          tokens: dep.tokens,
          category: dep.file_type,
          created_at: dep.created_at,
        }));
        
        setFileContext(transformedFiles);
        
        return transformedFiles;
      } catch (error) {
        if (handleSessionError(error, sessionId, clearSession)) {
          // Session was cleared, return empty file dependencies
          return [];
        }
        throw error; // Re-throw non-session errors
      }
    },
    enabled: !!sessionId && !!sessionToken,
    retry: retryWithBackoff,
    retryDelay: getRetryDelay,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};



// Session management mutations
export const useCreateSession = () => {
  const queryClient = useQueryClient();
  const { setActiveSession, sessionToken } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ repoOwner, repoName, repoBranch = 'main' }: CreateSessionMutationData) => {
      return await sessionApi.createSession(
        {
          repo_owner: repoOwner,
          repo_name: repoName,
          repo_branch: repoBranch,
          title: `Chat - ${repoOwner}/${repoName}`,
        },
        sessionToken || undefined,
      );
    },
    onSuccess: (data: SessionResponse) => {
      // Update Zustand store
      setActiveSession(data.session_id);
      
      // Invalidate sessions list
      queryClient.invalidateQueries({ queryKey: QueryKeys.sessions });
    },
  });
};

// New hook for creating session from repository selection
export const useCreateSessionFromRepository = () => {
  const { createSessionForRepository, sessionLoadingEnabled, setSessionLoadingEnabled } = useSessionStore();
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (repository: SelectedRepository) => {
      // Only load session if enabled, otherwise always create new
      if (!sessionLoadingEnabled) {
        setSessionLoadingEnabled(false);
      }
      return await createSessionForRepository(repository);
    },
    onSuccess: (sessionId: string | null) => {
      if (sessionId) {
        // Invalidate sessions list
        queryClient.invalidateQueries({ queryKey: QueryKeys.sessions });
      }
    },
  });
};

// New hook for ensuring session exists
export const useEnsureSessionExists = () => {
  const { ensureSessionExists } = useSessionStore();
  
  return useMutation({
    mutationFn: async (sessionId: string) => {
      return await ensureSessionExists(sessionId);
    },
  });
};



