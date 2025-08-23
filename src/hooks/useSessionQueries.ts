/**
 * React Query hooks for session management
 * Handles server state and caching for sessions, messages, context cards, and file dependencies
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from './useApi';
import { useSessionStore } from '../stores/sessionStore';
import { 
  ChatMessageAPI, 
  ContextCard, 
  FileItem,
  CreateSessionMutationData,
  AddMessageMutationData,
  AddContextCardMutationData,
  RemoveContextCardMutationData,
  MessageMutationContext,
  ContextCardMutationContext,
  SelectedRepository,
} from '../types';
import type {
  ChatMessageResponse,
  ContextCardResponse,
  CreateChatMessageRequest,
  SessionResponse
} from '../types/api';

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
  const api = useApi();
  const { setMessages, sessionToken } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.session(sessionId),
    queryFn: async () => {
      const context = await api.getSessionContext(sessionId);
      
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
    },
    enabled: !!sessionId && !!sessionToken,
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Chat message queries
export const useChatMessages = (sessionId: string) => {
  const api = useApi();
  const { setMessages, sessionToken } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.messages(sessionId),
    queryFn: async (): Promise<ChatMessageAPI[]> => {
      const messages = await api.getChatMessages(sessionId, 100);
      
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
    },
    enabled: !!sessionId && !!sessionToken,
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useAddMessage = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { addMessage } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ sessionId, message }: AddMessageMutationData) => {
      // Transform ChatMessageAPI to CreateChatMessageRequest
      const createRequest: CreateChatMessageRequest = {
        session_id: sessionId,
        message_id: message.message_id,
        message_text: message.message_text,
        sender_type: message.sender_type,
        role: message.role,
        is_code: false, // Default value
        tokens: message.tokens,
        model_used: message.model_used,
        processing_time: message.processing_time,
        context_cards: message.context_cards || [],
        referenced_files: message.referenced_files || [],
        error_message: message.error_message
      };
      
      return await api.addChatMessage(sessionId, createRequest);
    },
    onMutate: async ({ sessionId, message }): Promise<MessageMutationContext> => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: QueryKeys.messages(sessionId) });
      
      // Snapshot the previous value
      const previousMessages = queryClient.getQueryData<ChatMessageAPI[]>(QueryKeys.messages(sessionId)) || [];
      
      // Optimistically update the cache
      const optimisticMessage: ChatMessageAPI = {
        id: Date.now(),
        message_id: message.message_id || Date.now().toString(),
        message_text: message.message_text,
        sender_type: message.sender_type,
        role: message.role,
        tokens: message.tokens || 0,
        created_at: new Date().toISOString(),
      };
      
      queryClient.setQueryData(QueryKeys.messages(sessionId), (old: ChatMessageAPI[] = []) => [
        ...old,
        optimisticMessage,
      ]);
      
      // Update Zustand store optimistically
      addMessage(optimisticMessage);
      
      return { previousMessages, optimisticMessage };
    },
    onError: (_err: Error, { sessionId }: AddMessageMutationData, context?: MessageMutationContext) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousMessages) {
        queryClient.setQueryData(QueryKeys.messages(sessionId), context.previousMessages);
      }
    },
    onSettled: (_data: ChatMessageResponse | undefined, _error: Error | null, { sessionId }: AddMessageMutationData) => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: QueryKeys.messages(sessionId) });
    },
  });
};



// Context card queries
export const useContextCards = (sessionId: string) => {
  const api = useApi();
  const { setContextCards, sessionToken } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.contextCards(sessionId),
    queryFn: async (): Promise<ContextCard[]> => {
      const cards = await api.getContextCards(sessionId);
      
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
    },
    enabled: !!sessionId && !!sessionToken,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

export const useAddContextCard = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { addContextCard } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ sessionId, card }: AddContextCardMutationData) => {
      return await api.addContextCard(sessionId, card);
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
  const api = useApi();
  const queryClient = useQueryClient();
  const { removeContextCard } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ sessionId, cardId }: RemoveContextCardMutationData) => {
      return await api.deleteContextCard(sessionId, parseInt(cardId));
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
  const api = useApi();
  const { setFileContext, sessionToken } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.fileDependencies(sessionId),
    queryFn: async (): Promise<FileItem[]> => {
      const deps = await api.getFileDependenciesSession(sessionId);
      
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
    },
    enabled: !!sessionId && !!sessionToken,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};



// Session management mutations
export const useCreateSession = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { setActiveSession } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ repoOwner, repoName, repoBranch = 'main' }: CreateSessionMutationData) => {
      return await api.createSession({
        repo_owner: repoOwner,
        repo_name: repoName,
        repo_branch: repoBranch,
        title: `Chat - ${repoOwner}/${repoName}`,
      });
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
  const { createSessionForRepository } = useSessionStore();
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (repository: SelectedRepository) => {
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



