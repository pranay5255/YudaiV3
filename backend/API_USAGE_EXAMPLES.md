# Unified Session-Based API Usage Examples

This document shows how to use the unified session-based APIs that ensure consistent state between frontend and backend.

## Session Management (Unified)

### 1. Create/Get Session
```python
# Backend: SessionService
session = SessionService.get_or_create_session(
    db=db,
    user_id=user.id,
    repo_owner="pranay5255",
    repo_name="YudaiV3",
    repo_branch="main",
    title="Working on React refactoring",
    description="Session for implementing unified state management"
)
```

```typescript
// Frontend: ApiService
const sessionId = await ApiService.createSession(
    "pranay5255",
    "YudaiV3", 
    "main",
    "Working on React refactoring",
    "Session for implementing unified state management"
);
```

### 2. Get Comprehensive Session Context
```python
# Backend: SessionService
context = SessionService.get_comprehensive_session_context(
    db=db,
    user_id=user.id,
    session_id=session_id
)
# Returns: SessionContextResponse with messages, context_cards, file_embeddings, user_issues, statistics
```

```typescript
// Frontend: ApiService
const context = await ApiService.getSessionContextById(sessionId);
// Returns: SessionContextResponse matching backend structure
```

## Chat Message Management

### 1. Create Chat Message
```python
# Backend: ChatService (requires existing session)
message = ChatService.create_chat_message(
    db=db,
    user_id=user.id,
    request=CreateChatMessageRequest(
        session_id=session_id,
        message_id=str(uuid.uuid4()),
        message_text="How do I implement real-time updates?",
        sender_type="user",
        role="user",
        is_code=False,
        tokens=10,
        context_cards=["card1", "card2"]
    )
)
```

```typescript
// Frontend: ApiService (enhanced chat)
const response = await ApiService.sendEnhancedChatMessage({
    session_id: sessionId,
    message: {
        content: "How do I implement real-time updates?",
        is_code: false
    },
    context_cards: ["card1", "card2"],
    file_context: ["file1", "file2"]
});
```

## Issue Management with Session Context

### 1. Create Issue with Context
```python
# Backend: IssueService
issue = IssueService.create_user_issue(
    db=db,
    user_id=user.id,
    request=CreateUserIssueRequest(
        title="Implement real-time updates",
        issue_text_raw="Need to add Server-Sent Events for real-time communication",
        conversation_id=session_id,  # Links to session
        repo_owner="pranay5255",
        repo_name="YudaiV3"
    )
)
```

```typescript
// Frontend: ApiService
const response = await ApiService.createIssueWithContext({
    title: "Implement real-time updates",
    description: "Need to add Server-Sent Events for real-time communication",
    chat_messages: sessionState.messages.map(msg => ({
        id: msg.id,
        content: msg.content,
        isCode: msg.is_code,
        timestamp: msg.timestamp
    })),
    file_context: sessionState.fileContext.map(file => ({
        id: file.id,
        name: file.name,
        type: file.type,
        tokens: file.tokens,
        category: file.Category,
        path: file.path
    })),
    repository_info: {
        owner: "pranay5255",
        name: "YudaiV3",
        branch: "main"
    },
    priority: "high"
});
```

## Real-time Updates (Frontend)

### 1. Establish SSE Connection
```typescript
// Frontend: SessionContext automatically establishes connection
const eventSource = ApiService.createSessionEventSource(sessionId);

eventSource.onmessage = (event) => {
    const update: SessionUpdateEvent = JSON.parse(event.data);
    
    switch (update.type) {
        case 'message':
            // Update messages in session state
            break;
        case 'context_card':
            // Update context cards
            break;
        case 'agent_status':
            // Update agent status
            break;
    }
};
```

## Unified State Management

### Frontend Session State (Comprehensive)
```typescript
interface SessionState {
    sessionId: string | null;
    session: SessionResponse | null;
    messages: ChatMessageAPI[];
    contextCards: ContextCard[];
    fileContext: FileItem[];
    userIssues: UserIssueResponse[];
    agentStatus: AgentStatus;
    statistics: SessionStatistics;
    connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
    // ... and more
}

// Usage in React components
const { sessionState, addContextCard, sendMessage, createIssue } = useSession();
```

### Backend Session Context (Matching)
```python
# SessionService.get_comprehensive_session_context returns:
SessionContextResponse(
    session=SessionResponse,           # Session metadata
    messages=List[ChatMessageResponse], # All messages
    context_cards=List[str],           # Context card IDs
    repository_info=Dict[str, Any],    # Repository metadata
    file_embeddings=List[FileEmbeddingResponse], # File context
    user_issues=List[UserIssueResponse], # Related issues
    statistics=Dict[str, Any]          # Session statistics
)
```

## API Endpoint Summary

### Session Endpoints
- `POST /daifu/sessions` - Create session
- `GET /daifu/sessions/{session_id}` - Get comprehensive context
- `GET /daifu/sessions` - List user sessions
- `POST /daifu/sessions/{session_id}/touch` - Update activity

### Chat Endpoints (Session-aware)
- `POST /daifu/chat/daifu` - Send message (requires session_id)
- `GET /daifu/chat/sessions/{session_id}/messages` - Get messages
- `GET /daifu/chat/sessions/{session_id}/statistics` - Get stats

### Issue Endpoints (Session-linked)
- `POST /issues/create-with-context` - Create issue with session context
- `GET /issues/` - List user issues
- `POST /issues/{issue_id}/create-github-issue` - Convert to GitHub issue

## Key Benefits

1. **Unified State**: Session serves as single source of truth
2. **Real-time Sync**: SSE keeps frontend and backend in sync
3. **Context Preservation**: All data linked to session for consistency
4. **Type Safety**: Matching interfaces between frontend and backend
5. **Scalability**: Session-based architecture supports multiple workflows