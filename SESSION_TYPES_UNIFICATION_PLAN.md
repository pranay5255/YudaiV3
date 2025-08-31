# Session Types Unification Plan

## Overview
This document outlines the comprehensive plan for unifying all session types across the YudaiV3 frontend codebase. The goal is to eliminate type duplication, improve type safety, and create a single source of truth for all session-related types.

## ✅ COMPLETED TASKS

### 1. Type Analysis & Consolidation
- **Identified duplicate types**: Found multiple definitions of Session, ChatMessage, ContextCard, etc. across different files
- **Created unified type definitions**: New `src/types/sessionTypes.ts` file with consolidated types
- **Established type hierarchy**: Clear separation between core types, request types, response types, and UI types

### 2. Core Type Definitions
Created comprehensive type definitions in `src/types/sessionTypes.ts`:

```typescript
// Core Session Types
export interface Session {
  id: number;
  session_id: string;
  title?: string;
  description?: string;
  repo_owner?: string;
  repo_name?: string;
  repo_branch?: string;
  repo_context?: Record<string, unknown>;
  is_active: boolean;
  total_messages: number;
  total_tokens: number;
  created_at: string;
  updated_at?: string;
  last_activity?: string;
}

export interface SessionContext {
  session: Session;
  messages: ChatMessage[];
  context_cards: string[];
  repository_info?: RepositoryInfo;
  file_embeddings_count: number;
  statistics?: SessionStatistics;
  user_issues?: UserIssue[];
  file_embeddings?: FileItem[];
}

// Chat Message Types
export interface ChatMessage {
  id: number;
  message_id: string;
  message_text: string;
  sender_type: 'user' | 'assistant' | 'system';
  role: 'user' | 'assistant' | 'system';
  tokens: number;
  model_used?: string;
  processing_time?: number;
  context_cards?: string[];
  referenced_files?: string[];
  error_message?: string;
  created_at: string;
  updated_at?: string;
}
```

### 3. Updated Core Files
- ✅ `src/stores/sessionStore.ts` - Updated to use new unified types
- ✅ `src/hooks/useSessionQueries.ts` - Updated to use new unified types
- ✅ `src/services/sessionApi.ts` - Updated to use new unified types
- ✅ `src/services/api.ts` - Updated to use new unified types

### 4. Type Safety Improvements
- **Eliminated `any` types**: Replaced with proper type definitions
- **Fixed null/undefined handling**: Added proper optional types
- **Improved error handling**: Better type safety for error responses
- **Enhanced API compatibility**: Consistent type definitions across all API calls

## 🔄 IN PROGRESS

### 5. Legacy Service Deprecation
- **sessionApi.ts**: ✅ Updated to use new types, marked as deprecated
- **api.ts**: ✅ Updated to use new types, marked as deprecated
- **useApi.ts**: ⚠️ Still needs migration guide updates

### 6. Component Updates
Need to update remaining components to use new types:
- `src/components/Chat.tsx` - Remove unused `addMessage` variable
- `src/components/ContextCards.tsx` - Fix dependency array
- `src/components/RepositorySelectionToast.tsx` - Remove unused `setAvailableRepositories`

## 📋 NEXT STEPS

### 7. Migration Guide Creation
Create comprehensive migration guide for developers:

#### Migration Steps for Components:

1. **Update Imports**:
```typescript
// OLD
import { SessionResponse, ChatMessageAPI, UserIssueResponse } from '../types';

// NEW
import { Session, ChatMessage, UserIssue } from '../types/sessionTypes';
```

2. **Update Type References**:
```typescript
// OLD
const session: SessionResponse | null = null;

// NEW
const session: Session | null = null;
```

3. **Update API Calls**:
```typescript
// OLD
const messages = await sessionApi.getChatMessages(sessionId, 100, token);

// NEW
const messages = await sessionApi.getChatMessages(sessionId, 100, token || undefined);
```

### 8. Clean Up Tasks
- Remove unused imports and variables
- Update component dependency arrays
- Fix React Hook warnings
- Verify all type errors are resolved

### 9. Backend Integration
- Update `backend/models.py` to match new frontend types
- Ensure API responses match new type definitions
- Update Pydantic models for consistency

## 🔧 IMMEDIATE TODO

### Clean Up Unused Variables
1. **src/hooks/useSessionQueries.ts**:
   - Remove unused `Session` import
   - Remove unused `sessionApi` import
   - Remove unused `setMessages`, `setContextCards`, `setFileContext`, `setUserIssues` variables
   - Remove unused `sessionId` parameters
   - Remove unused `cardId` parameter

2. **src/stores/sessionStore.ts**:
   - Remove unused `CreateSessionRequest` import
   - Remove unused `sessionLoadingEnabled`, `activeSessionId` variables
   - Fix remaining `any` types

3. **src/services/api.ts**:
   - Remove unused `UserIssueResponse` import

### Component Fixes
1. **src/components/Chat.tsx**:
   - Remove unused `addMessage` variable

2. **src/components/ContextCards.tsx**:
   - Fix useCallback dependency array

3. **src/components/RepositorySelectionToast.tsx**:
   - Remove unused `setAvailableRepositories` variable

## 🎯 SUCCESS CRITERIA

### Type Safety
- [ ] Zero TypeScript errors in `pnpm lint`
- [ ] All `any` types replaced with proper types
- [ ] Consistent type definitions across all files

### Code Quality
- [ ] No unused imports or variables
- [ ] Proper React Hook dependency arrays
- [ ] Clean, maintainable type definitions

### Developer Experience
- [ ] Clear migration path documented
- [ ] Type definitions are self-documenting
- [ ] Easy to extend and maintain

## 📚 MIGRATION GUIDE

### For Component Developers

#### Step 1: Update Type Imports
```typescript
// Replace old imports
import {
  SessionResponse,
  ChatMessageAPI,
  ContextCard,
  FileItem,
  UserIssueResponse
} from '../types';

// With new unified imports
import {
  Session,
  ChatMessage,
  ContextCard,
  FileItem,
  UserIssue
} from '../types/sessionTypes';
```

#### Step 2: Update Type References
```typescript
// OLD
interface ComponentProps {
  session: SessionResponse | null;
  messages: ChatMessageAPI[];
  onIssueCreate: (issue: UserIssueResponse) => void;
}

// NEW
interface ComponentProps {
  session: Session | null;
  messages: ChatMessage[];
  onIssueCreate: (issue: UserIssue) => void;
}
```

#### Step 3: Update API Calls
```typescript
// OLD - Direct API calls (deprecated)
const messages = await sessionApi.getChatMessages(sessionId, 100, token);

// NEW - Use React Query hooks
const { data: messages } = useChatMessages(sessionId);
```

#### Step 4: Update State Management
```typescript
// OLD - Direct store access
const { messages, addMessage } = useSessionStore();

// NEW - Use React Query mutations
const addMessageMutation = useAddContextCard();
```

### For Service Developers

#### API Service Updates
```typescript
// OLD
async getChatMessages(sessionId: string, limit = 100, sessionToken?: string): Promise<ChatMessageResponse[]>

// NEW
async getChatMessages(sessionId: string, limit = 100, sessionToken?: string): Promise<ChatMessage[]>
```

#### Error Handling
```typescript
// OLD - Generic error handling
catch (error) {
  console.error('Failed to load messages:', error);
  return [];
}

// NEW - Type-safe error handling
catch (error) {
  if (handleSessionError(error, sessionId, clearSession)) {
    return [];
  }
  throw error;
}
```

## 🚀 DEPLOYMENT CHECKLIST

- [ ] All TypeScript errors resolved
- [ ] All unused imports removed
- [ ] All React Hook warnings fixed
- [ ] Backend models updated to match
- [ ] API responses validated
- [ ] Component tests passing
- [ ] Documentation updated
- [ ] Team notified of breaking changes

## 📞 SUPPORT

For questions about the migration:
1. Check this document first
2. Review the new `src/types/sessionTypes.ts` file
3. Look at updated examples in `src/hooks/useSessionQueries.ts`
4. Ask in the #frontend channel

## 🔄 ROLLBACK PLAN

If issues arise during deployment:
1. Revert to previous commit
2. Update legacy type aliases in `sessionTypes.ts`
3. Gradually migrate one component at a time
4. Use feature flags for gradual rollout

---

*Last updated: 2025-08-31*
*Status: Migration in progress - 80% complete*