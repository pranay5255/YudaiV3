import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { SelectedRepository, TabType, ContextCard, FileItem, ChatMessageAPI } from '../types';

// Enhanced types for the session store
interface SessionState {
  // Core session state
  activeSessionId: string | null;
  isLoading: boolean;
  error: string | null;
  
  // Repository state
  selectedRepository: SelectedRepository | null;
  availableRepositories: any[];
  isLoadingRepositories: boolean;
  repositoryError: string | null;
  
  // UI state
  activeTab: TabType;
  sidebarCollapsed: boolean;
  
  // Session data (local cache)
  sessionData: {
    messages: ChatMessageAPI[];
    contextCards: ContextCard[];
    fileContext: FileItem[];
    totalTokens: number;
    lastUpdated: Date | null;
  };
  
  // Actions
  setActiveSession: (sessionId: string) => void;
  clearSession: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSelectedRepository: (repository: SelectedRepository | null) => void;
  setAvailableRepositories: (repositories: any[]) => void;
  setRepositoryLoading: (loading: boolean) => void;
  setRepositoryError: (error: string | null) => void;
  setActiveTab: (tab: TabType) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  
  // Session data actions
  addMessage: (message: ChatMessageAPI) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessageAPI>) => void;
  removeMessage: (messageId: string) => void;
  setMessages: (messages: ChatMessageAPI[]) => void;
  
  addContextCard: (card: ContextCard) => void;
  removeContextCard: (cardId: string) => void;
  setContextCards: (cards: ContextCard[]) => void;
  
  addFileItem: (file: FileItem) => void;
  removeFileItem: (fileId: string) => void;
  setFileContext: (files: FileItem[]) => void;
  
  updateSessionData: (data: Partial<SessionState['sessionData']>) => void;
}

// Create the session store with persistence
export const useSessionStore = create<SessionState>()(
  devtools(
    persist(
      (set) => ({
        // Initial state
        activeSessionId: null,
        isLoading: false,
        error: null,
        
        // Repository state
        selectedRepository: null,
        availableRepositories: [],
        isLoadingRepositories: false,
        repositoryError: null,
        
        // UI state
        activeTab: 'chat',
        sidebarCollapsed: false,
        
        // Session data
        sessionData: {
          messages: [],
          contextCards: [],
          fileContext: [],
          totalTokens: 0,
          lastUpdated: null,
        },
        
        // Core actions
        setActiveSession: (sessionId: string) =>
          set({ activeSessionId: sessionId, error: null }),
        
        clearSession: () =>
          set({ 
            activeSessionId: null, 
            error: null,
            sessionData: {
              messages: [],
              contextCards: [],
              fileContext: [],
              totalTokens: 0,
              lastUpdated: null,
            }
          }),
        
        setLoading: (loading: boolean) =>
          set({ isLoading: loading }),
        
        setError: (error: string | null) =>
          set({ error }),
        
        // Repository actions
        setSelectedRepository: (repository: SelectedRepository | null) =>
          set({ selectedRepository: repository, repositoryError: null }),
        
        setAvailableRepositories: (repositories: any[]) =>
          set({ availableRepositories: repositories }),
        
        setRepositoryLoading: (loading: boolean) =>
          set({ isLoadingRepositories: loading }),
        
        setRepositoryError: (error: string | null) =>
          set({ repositoryError: error }),
        
        // UI actions
        setActiveTab: (tab: TabType) =>
          set({ activeTab: tab }),
        
        setSidebarCollapsed: (collapsed: boolean) =>
          set({ sidebarCollapsed: collapsed }),
        
        // Message actions
        addMessage: (message: ChatMessageAPI) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages: [...state.sessionData.messages, message],
              totalTokens: state.sessionData.totalTokens + (message.tokens || 0),
              lastUpdated: new Date(),
            }
          })),
        
        updateMessage: (messageId: string, updates: Partial<ChatMessageAPI>) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages: state.sessionData.messages.map(msg => 
                msg.message_id === messageId ? { ...msg, ...updates } : msg
              ),
              lastUpdated: new Date(),
            }
          })),
        
        removeMessage: (messageId: string) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages: state.sessionData.messages.filter(msg => msg.message_id !== messageId),
              lastUpdated: new Date(),
            }
          })),
        
        setMessages: (messages: ChatMessageAPI[]) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              messages,
              totalTokens: messages.reduce((sum, msg) => sum + (msg.tokens || 0), 0),
              lastUpdated: new Date(),
            }
          })),
        
        // Context card actions
        addContextCard: (card: ContextCard) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              contextCards: [...state.sessionData.contextCards, card],
              totalTokens: state.sessionData.totalTokens + card.tokens,
              lastUpdated: new Date(),
            }
          })),
        
        removeContextCard: (cardId: string) =>
          set((state) => {
            const removedCard = state.sessionData.contextCards.find(c => c.id === cardId);
            return {
              sessionData: {
                ...state.sessionData,
                contextCards: state.sessionData.contextCards.filter(c => c.id !== cardId),
                totalTokens: state.sessionData.totalTokens - (removedCard?.tokens || 0),
                lastUpdated: new Date(),
              }
            };
          }),
        
        setContextCards: (cards: ContextCard[]) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              contextCards: cards,
              lastUpdated: new Date(),
            }
          })),
        
        // File context actions
        addFileItem: (file: FileItem) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              fileContext: [...state.sessionData.fileContext, file],
              totalTokens: state.sessionData.totalTokens + file.tokens,
              lastUpdated: new Date(),
            }
          })),
        
        removeFileItem: (fileId: string) =>
          set((state) => {
            const removedFile = state.sessionData.fileContext.find(f => f.id === fileId);
            return {
              sessionData: {
                ...state.sessionData,
                fileContext: state.sessionData.fileContext.filter(f => f.id !== fileId),
                totalTokens: state.sessionData.totalTokens - (removedFile?.tokens || 0),
                lastUpdated: new Date(),
              }
            };
          }),
        
        setFileContext: (files: FileItem[]) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              fileContext: files,
              lastUpdated: new Date(),
            }
          })),
        
        updateSessionData: (data: Partial<SessionState['sessionData']>) =>
          set((state) => ({
            sessionData: {
              ...state.sessionData,
              ...data,
              lastUpdated: new Date(),
            }
          })),
      }),
      {
        name: 'session-storage',
        // Only persist certain parts of the state
        partialize: (state) => ({
          activeSessionId: state.activeSessionId,
          selectedRepository: state.selectedRepository,
          activeTab: state.activeTab,
          sidebarCollapsed: state.sidebarCollapsed,
        }),
      }
    ),
    {
      name: 'session-store',
    }
  )
);

// Example usage with React Query (commented out for now)
/*
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Session queries
export const useSessions = () => {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: () => fetchSessions(),
  });
};

export const useSession = (sessionId: string) => {
  return useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => fetchSession(sessionId),
    enabled: !!sessionId,
  });
};

// Chat message queries
export const useChatMessages = (sessionId: string) => {
  return useQuery({
    queryKey: ['messages', sessionId],
    queryFn: () => fetchMessages(sessionId),
    enabled: !!sessionId,
  });
};

export const useAddMessage = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: addMessage,
    onSuccess: (data, variables) => {
      // Invalidate and refetch messages
      queryClient.invalidateQueries({ queryKey: ['messages', variables.sessionId] });
      
      // Optimistically update the cache
      queryClient.setQueryData(['messages', variables.sessionId], (old: any) => {
        return old ? [...old, data] : [data];
      });
    },
  });
};

// Context card queries
export const useContextCards = (sessionId: string) => {
  return useQuery({
    queryKey: ['context-cards', sessionId],
    queryFn: () => fetchContextCards(sessionId),
    enabled: !!sessionId,
  });
};

export const useAddContextCard = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: addContextCard,
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['context-cards', variables.sessionId] });
    },
  });
};

// File dependency queries
export const useFileDependencies = (sessionId: string) => {
  return useQuery({
    queryKey: ['file-deps', sessionId],
    queryFn: () => fetchFileDependencies(sessionId),
    enabled: !!sessionId,
  });
};

export const useAddFileDependency = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: addFileDependency,
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['file-deps', variables.sessionId] });
    },
  });
};
*/

