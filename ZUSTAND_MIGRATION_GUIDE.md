# Zustand Migration Guide

## 🎯 Migration Strategy: Context → Zustand + React Query

This guide outlines the step-by-step migration from the current Context-based state management to Zustand + React Query architecture.

## 📋 Migration Checklist

### ✅ Phase 1: Foundation (COMPLETED)
- [x] Create Zustand store (`src/stores/sessionStore.ts`)
- [x] Create React Query hooks (`src/hooks/useSessionQueries.ts`)
- [x] Update documentation (`zustand-query-unifier.md`)

### 🔄 Phase 2: Component Migration (IN PROGRESS)
- [ ] Update `src/App.tsx` to use Zustand store
- [ ] Update `src/components/Chat.tsx` to use React Query hooks
- [ ] Update `src/components/FileDependencies.tsx` to use new state
- [ ] Update `src/components/ContextCards.tsx` to use new state
- [ ] Update other components to use new architecture

### 🔄 Phase 3: Cleanup (PENDING)
- [ ] Remove `src/contexts/SessionProvider.tsx`
- [ ] Update `src/hooks/useSessionState.ts` (or remove if unnecessary)
- [ ] Remove `src/types/fileDependencies.ts`
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

## 🚀 Next Steps

1. **Complete Component Migration**: Update all components to use new architecture
2. **Remove Legacy Code**: Clean up Context-based code
3. **Add Missing Backend APIs**: Implement required backend endpoints
4. **Optimize Performance**: Fine-tune caching and update strategies
5. **Add Advanced Features**: Implement advanced React Query features like infinite queries, background updates, etc.

## 📚 Resources

- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Migration Best Practices](https://tanstack.com/query/latest/docs/react/guides/migrating-to-react-query-4)

