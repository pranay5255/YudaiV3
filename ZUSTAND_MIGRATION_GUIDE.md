# Zustand Migration Guide

## 🎯 Migration Strategy: Context → Zustand + React Query

This guide outlines the step-by-step migration from the current Context-based state management to Zustand + React Query architecture.

## 📋 Migration Checklist

### ✅ Phase 1: Foundation (COMPLETED)
- [x] Create Zustand store (`src/stores/sessionStore.ts`)
- [x] Create React Query hooks (`src/hooks/useSessionQueries.ts`)
- [x] Update documentation (`zustand-query-unifier.md`)

### ✅ Phase 2: Component Migration (COMPLETED)
- [x] Update `src/App.tsx` to use Zustand store
- [x] Update React Query hooks with proper TypeScript types
- [x] Implement optimistic updates for all mutations
- [x] Add comprehensive type safety with mutation context types
- [x] Update components to use new architecture

### 🔄 Phase 3: Cleanup (IN PROGRESS)
- [x] Enhanced type definitions in `src/types.ts`
- [x] Proper TypeScript integration for all hooks
- [ ] Remove `src/contexts/SessionProvider.tsx` (legacy support maintained)
- [ ] Update `src/hooks/useSessionState.ts` (or remove if unnecessary)
- [ ] Remove `src/types/fileDependencies.ts` (consolidated into main types)
- [ ] Clean up unused imports and dependencies

## 🔄 Step-by-Step Migration

### Step 1: Update App.tsx

**Before (Context-based):**
```typescript
// Current implementation
const { sessionId, contextCards, fileContext } = useSession();
const { setSelectedRepository, hasSelectedRepository } = useRepository();
```

**After (Zustand + React Query):**
```typescript
// New implementation
import { useSessionStore } from './stores/sessionStore';
import { useSession, useContextCards, useFileDependencies } from './hooks/useSessionQueries';

const { 
  activeSessionId, 
  selectedRepository, 
  setSelectedRepository,
  activeTab,
  setActiveTab,
  sidebarCollapsed,
  setSidebarCollapsed 
} = useSessionStore();

const { data: sessionData } = useSession(activeSessionId || '');
const { data: contextCards = [] } = useContextCards(activeSessionId || '');
const { data: fileContext = [] } = useFileDependencies(activeSessionId || '');
```

### Step 2: Update Chat.tsx

**Before:**
```typescript
const { sessionId, createSession, addChatMessage, messages: sessionMessages, contextCards, fileContext } = useSession();
const { addContextCard } = useContextCardManagement();
```

**After:**
```typescript
import { useSessionStore } from '../stores/sessionStore';
import { 
  useCreateSession, 
  useAddMessage, 
  useChatMessages,
  useAddContextCard 
} from '../hooks/useSessionQueries';

const { activeSessionId, sessionData } = useSessionStore();
const { data: messages = [] } = useChatMessages(activeSessionId || '');
const createSessionMutation = useCreateSession();
const addMessageMutation = useAddMessage();
const addContextCardMutation = useAddContextCard();
```

### Step 3: Update FileDependencies.tsx

**Before:**
```typescript
const sessionState = useSessionState();
const { loadFileDependencies: loadFileDeps, extractFileDependenciesForSession } = useFileDependencyManagement();
const { addContextCard } = useContextCardManagement();
```

**After:**
```typescript
import { useSessionStore } from '../stores/sessionStore';
import { useFileDependencies, useAddFileDependency, useAddContextCard } from '../hooks/useSessionQueries';

const { activeSessionId } = useSessionStore();
const { data: fileContext = [], isLoading } = useFileDependencies(activeSessionId || '');
const addFileDependencyMutation = useAddFileDependency();
const addContextCardMutation = useAddContextCard();
```

## 📦 Package Dependencies

### Required Packages
```json
{
  "dependencies": {
    "zustand": "^4.4.1",
    "@tanstack/react-query": "^4.29.0",
    "@tanstack/react-query-devtools": "^4.29.0"
  }
}
```

### Query Client Setup
Update `src/main.tsx`:
```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <YourApp />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

## 🔍 Testing Strategy

### 1. Component Testing
```typescript
// Test with Zustand store
import { renderWithStore } from './test-utils';

test('Chat component with Zustand', () => {
  const { store } = renderWithStore(<Chat />);
  
  // Test store interactions
  expect(store.getState().sessionData.messages).toEqual([]);
});
```

### 2. React Query Testing
```typescript
// Test with Query Client
import { renderWithQueryClient } from './test-utils';

test('Chat component with React Query', async () => {
  const { queryClient } = renderWithQueryClient(<Chat />);
  
  // Test query behavior
  await waitFor(() => {
    expect(queryClient.getQueryData(['messages', 'session-1'])).toBeDefined();
  });
});
```

## 🐛 Common Migration Issues

### Issue 1: Zustand Persistence
**Problem**: Store resets on refresh
**Solution**: Use `persist` middleware with correct configuration

### Issue 2: React Query Cache Invalidation
**Problem**: Stale data after mutations
**Solution**: Proper `invalidateQueries` and `optimisticUpdates`

### Issue 3: Type Safety
**Problem**: TypeScript errors with new hooks
**Solution**: Update type definitions and ensure proper imports

## 🔧 Development Tools

### Zustand DevTools
```typescript
// Already configured in sessionStore.ts
export const useSessionStore = create<SessionState>()(
  devtools(
    // ... store configuration
    {
      name: 'session-store',
    }
  )
);
```

### React Query DevTools
```typescript
// Add to main app
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

<ReactQueryDevtools initialIsOpen={false} />
```

## 📈 Performance Benefits

### Before (Context)
- ❌ Unnecessary re-renders on unrelated state changes
- ❌ Manual cache management
- ❌ No optimistic updates
- ❌ Complex state synchronization

### After (Zustand + React Query)
- ✅ Selective subscriptions (only re-render when needed)
- ✅ Automatic cache management and invalidation
- ✅ Built-in optimistic updates
- ✅ Clear separation of local vs server state

## ✅ Enhanced Type Implementation

### New Types Added to `src/types.ts`

#### Mutation Data Types
```typescript
// Session mutation types
export interface CreateSessionMutationData {
  repoOwner: string;
  repoName: string;
  repoBranch?: string;
}

export interface AddMessageMutationData {
  sessionId: string;
  message: ChatMessageAPI;
}

export interface AddContextCardMutationData {
  sessionId: string;
  card: {
    title: string;
    description: string;
    source: 'chat' | 'file-deps' | 'upload';
    tokens: number;
    content?: string;
  };
}
```

#### Context Types for Optimistic Updates
```typescript
export interface MessageMutationContext {
  previousMessages: ChatMessageAPI[];
  optimisticMessage: ChatMessageAPI;
}

export interface ContextCardMutationContext {
  previousCards: ContextCard[];
  optimisticCard?: ContextCard;
}
```

### Updated useSessionQueries.ts Features

1. **Full Type Safety**: All mutations and queries now use proper TypeScript types
2. **Optimistic Updates**: Immediate UI feedback with rollback on errors
3. **Proper Error Handling**: Typed error contexts and error recovery
4. **Cache Management**: Strategic invalidation and type-safe cache updates

## 🚀 Next Steps

1. ✅ **Enhanced Type System**: Complete TypeScript coverage implemented
2. ✅ **Optimistic Updates**: All mutations support optimistic updates
3. ✅ **Type-Safe Mutations**: All mutation data types properly defined
4. **Component Migration**: Update remaining legacy components to use new hooks
5. **Performance Optimization**: Fine-tune caching and update strategies
6. **Advanced Features**: Implement infinite queries, background updates, etc.

## 📚 Resources

- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Migration Best Practices](https://tanstack.com/query/latest/docs/react/guides/migrating-to-react-query-4)

