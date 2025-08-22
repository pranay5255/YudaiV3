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
  SessionResponse,
  SessionContextResponse 
} from '../types';

// Query keys for consistent cache management
export const QueryKeys = {
  sessions: ['sessions'] as const,
  session: (sessionId: string) => ['session', sessionId] as const,
  messages: (sessionId: string) => ['messages', sessionId] as const,
  contextCards: (sessionId: string) => ['context-cards', sessionId] as const,
  fileDependencies: (sessionId: string) => ['file-deps', sessionId] as const,
  repositories: ['repositories'] as const,
};

// Session queries
export const useSessions = () => {
  const api = useApi();
  
  return useQuery({
    queryKey: QueryKeys.sessions,
    queryFn: () => api.getUserSessions?.() || Promise.resolve([]),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  });
};

export const useSession = (sessionId: string) => {
  const api = useApi();
  const { setMessages, setContextCards, setFileContext } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.session(sessionId),
    queryFn: async (): Promise<SessionContextResponse> => {
      const context = await api.getSessionContext(sessionId);
      
      // Update Zustand store with fetched data
      if (context.messages) {
        setMessages(context.messages);
      }
      
      return context;
    },
    enabled: !!sessionId,
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Chat message queries
export const useChatMessages = (sessionId: string) => {
  const api = useApi();
  const { setMessages } = useSessionStore();
  
  return useQuery({
    queryKey: QueryKeys.messages(sessionId),
    queryFn: async (): Promise<ChatMessageAPI[]> => {
      const messages = await api.getChatMessages(sessionId);
      
      // Update Zustand store
      setMessages(messages);
      
      return messages;
    },
    enabled: !!sessionId,
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useAddMessage = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { addMessage } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ sessionId, message }: { sessionId: string; message: any }) => {
      return await api.addChatMessage(sessionId, message);
    },
    onMutate: async ({ sessionId, message }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: QueryKeys.messages(sessionId) });
      
      // Snapshot the previous value
      const previousMessages = queryClient.getQueryData(QueryKeys.messages(sessionId));
      
      // Optimistically update the cache
      const optimisticMessage: ChatMessageAPI = {
        id: Date.now(),
        message_id: message.message_id || Date.now().toString(),
        message_text: message.content,
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
    onError: (err, { sessionId }, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousMessages) {
        queryClient.setQueryData(QueryKeys.messages(sessionId), context.previousMessages);
      }
    },
    onSettled: (data, error, { sessionId }) => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: QueryKeys.messages(sessionId) });
    },
  });
};

export const useUpdateMessage = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { updateMessage } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ 
      sessionId, 
      messageId, 
      updates 
    }: { 
      sessionId: string; 
      messageId: string; 
      updates: Partial<ChatMessageAPI> 
    }) => {
      return await api.updateChatMessage?.(sessionId, messageId, updates);
    },
    onSuccess: (data, { sessionId, messageId, updates }) => {
      // Update the cache
      queryClient.setQueryData(QueryKeys.messages(sessionId), (old: ChatMessageAPI[] = []) =>
        old.map(msg => msg.message_id === messageId ? { ...msg, ...updates } : msg)
      );
      
      // Update Zustand store
      updateMessage(messageId, updates);
    },
  });
};

// Context card queries
export const useContextCards = (sessionId: string) => {
  const api = useApi();
  const { setContextCards } = useSessionStore();
  
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
    enabled: !!sessionId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

export const useAddContextCard = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { addContextCard } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ 
      sessionId, 
      card 
    }: { 
      sessionId: string; 
      card: {
        title: string;
        description: string;
        source: 'chat' | 'file-deps' | 'upload';
        tokens: number;
        content?: string;
      }
    }) => {
      return await api.addContextCard(sessionId, card);
    },
    onSuccess: (data, { sessionId }) => {
      // Transform the response and update stores
      const newCard: ContextCard = {
        id: data.id.toString(),
        title: data.title,
        description: data.description,
        tokens: data.tokens,
        source: data.source as 'chat' | 'file-deps' | 'upload',
      };
      
      // Update Zustand store
      addContextCard(newCard);
      
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: QueryKeys.contextCards(sessionId) });
    },
  });
};

// File dependency queries
export const useFileDependencies = (sessionId: string) => {
  const api = useApi();
  const { setFileContext } = useSessionStore();
  
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
    enabled: !!sessionId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useAddFileDependency = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { addFileItem } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ 
      sessionId, 
      fileDependency 
    }: { 
      sessionId: string; 
      fileDependency: {
        file_path: string;
        file_name: string;
        file_type: string;
        chunk_index: number;
        tokens: number;
        file_metadata?: Record<string, unknown>;
      }
    }) => {
      return await api.addFileDependency(sessionId, fileDependency);
    },
    onSuccess: (data, { sessionId }) => {
      // Transform the response and update stores
      const newFile: FileItem = {
        id: data.id.toString(),
        name: data.file_name,
        path: data.file_path,
        type: 'INTERNAL' as const,
        tokens: data.tokens,
        category: data.file_type,
        created_at: data.created_at,
      };
      
      // Update Zustand store
      addFileItem(newFile);
      
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: QueryKeys.fileDependencies(sessionId) });
    },
  });
};

// Session management mutations
export const useCreateSession = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { setActiveSession, clearSession } = useSessionStore();
  
  return useMutation({
    mutationFn: async ({ 
      repoOwner, 
      repoName, 
      repoBranch = 'main' 
    }: { 
      repoOwner: string; 
      repoName: string; 
      repoBranch?: string 
    }) => {
      return await api.createSession({
        repo_owner: repoOwner,
        repo_name: repoName,
        repo_branch: repoBranch,
        title: `Chat - ${repoOwner}/${repoName}`,
      });
    },
    onSuccess: (data) => {
      // Update Zustand store
      setActiveSession(data.session_id);
      
      // Invalidate sessions list
      queryClient.invalidateQueries({ queryKey: QueryKeys.sessions });
    },
  });
};

export const useDeleteSession = () => {
  const api = useApi();
  const queryClient = useQueryClient();
  const { clearSession } = useSessionStore();
  
  return useMutation({
    mutationFn: async (sessionId: string) => {
      return await api.deleteSession?.(sessionId);
    },
    onSuccess: (data, sessionId) => {
      // Clear Zustand store if this was the active session
      clearSession();
      
      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: QueryKeys.sessions });
      queryClient.removeQueries({ queryKey: QueryKeys.session(sessionId) });
      queryClient.removeQueries({ queryKey: QueryKeys.messages(sessionId) });
      queryClient.removeQueries({ queryKey: QueryKeys.contextCards(sessionId) });
      queryClient.removeQueries({ queryKey: QueryKeys.fileDependencies(sessionId) });
    },
  });
};

