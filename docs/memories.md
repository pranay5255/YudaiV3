# Integration Plan: Context Services into session_routes.py

## Overview
This document outlines the steps to integrate the refactored context services (`ChatContext`, `FactsAndMemoriesService` with yudai-grep) into `session_routes.py`.

---


## Integration Tasks for session_routes.py

### Task 1: Update Chat Endpoint to Use ChatContext
**File**: `backend/daifuUserAgent/session_routes.py`  
**Endpoint**: `POST /sessions/{session_id}/chat`

**Changes**:
```python
@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat_in_session(...):
    # ... existing validation ...
    
    # Add repository context using ChatContext
    from context.chat_context import ChatContext
    
    chat_context = ChatContext(
        db=db,
        user_id=current_user.id,
        repo_owner=db_session.repo_owner,
        repo_name=db_session.repo_name,
        session_obj=db_session,
        session_id=session_id,
    )
    
    # Ensure context is available
    repo_context = await chat_context.ensure_github_context()
    
    # Get formatted context string for LLM
    context_string = await chat_context.get_best_context_string()
    
    # Pass context_string to ChatOps (may need to update ChatOps signature)
    chat_response = await chat_ops.process_chat_message(
        session_id=session_id,
        user_id=current_user.id,
        message_text=request.message.message_text,
        context_cards=request.context_cards or [],
        repository=repository_info,
        repo_context_string=context_string,  # NEW: Pass context string
    )
```

**Steps**:
1. Import `ChatContext` at the top of the file
2. Create `ChatContext` instance in chat endpoint
3. Call `ensure_github_context()` to fetch/cache context
4. Call `get_best_context_string()` to get formatted string
5. Pass context string to `ChatOps.process_chat_message()` (may need to update ChatOps)

---

### Task 2: Integrate ChatContext in Session Creation
**File**: `backend/daifuUserAgent/session_routes.py`  
**Endpoint**: `POST /sessions`

**Changes**:
```python
@router.post("/sessions", response_model=SessionResponse)
async def create_session(...):
    # ... create db_session ...
    
    # Pre-initialize context if indexing is enabled
    if request.index_codebase:
        from context.chat_context import ChatContext
        
        chat_context = ChatContext(
            db=db,
            user_id=current_user.id,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            session_obj=db_session,
            session_id=session_id,
        )
        
        # Optionally pre-fetch context in background (non-blocking)
        asyncio.create_task(chat_context.ensure_github_context())
```

**Steps**:
1. Add ChatContext initialization after session creation
2. Optionally pre-fetch context in background task (non-blocking)
3. This ensures cache is warm for first chat message

---

### Task 3: Update Background Indexing to Use Enhanced FactsAndMemoriesService
**File**: `backend/daifuUserAgent/session_routes.py`  
**Function**: `_index_repository_for_session_background()`

**Current State**: Already uses `FactsAndMemoriesService` but doesn't leverage yudai-grep features

**Changes**:
```python
async def _index_repository_for_session_background(...):
    # ... existing code ...
    
    if generate_facts_memories:
        try:
            logger.info(f"[Index] Generating Facts & Memories with yudai-grep for session {session_uuid}")
            
            # Get conversation history for yudai-grep query extraction
            conversation = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == chat_session.id)
                .order_by(ChatMessage.created_at.asc())
                .all()
            )
            conversation_payload = [
                {
                    "author": message.sender_type,
                    "text": message.message_text,
                }
                for message in conversation
            ]

            # Use enhanced FactsAndMemoriesService (now includes yudai-grep)
            facts_service = FactsAndMemoriesService()
            result = await facts_service.generate(
                snapshot=snapshot,
                conversation=conversation_payload,
                max_messages=min(len(conversation_payload), 10),
            )

            # Store enhanced facts & memories (includes yudai-grep analysis)
            repo_context = chat_session.repo_context or {}
            repo_context["facts_and_memories"] = {
                "facts": result.facts,
                "memories": result.memories,
                "highlights": result.highlights,
                "generated_at": utc_now().isoformat(),
                # NEW: Store yudai-grep insights
                "yudai_grep_analysis": {
                    "key_files": [...],  # From repo_analysis
                    "key_folders": [...],
                    "predictions": [...],
                },
            }
            chat_session.repo_context = repo_context
            db.commit()
            logger.info(f"[Index] Facts & Memories with yudai-grep stored for session {session_uuid}")
        except Exception as fam_error:
            logger.warning(f"[Index] Facts & Memories generation failed: {fam_error}")
            db.rollback()
```

**Steps**:
1. No changes needed - FactsAndMemoriesService already enhanced
2. Optional: Store yudai-grep analysis results in repo_context for future use
3. Log yudai-grep integration status

---

### Task 4: Implement Top-K Probability-Based File Ranking with yudai-grep
**File**: `backend/context/facts_and_memories.py`  
**Class**: `FactsAndMemoriesService`

**Concept**: Enhance `_analyze_repository_structure()` to use top-k predictions with probability thresholds instead of only top-1 predictions. This provides better file ranking and filtering for facts generation.

**Current Limitation**: Only uses `argmax` (top-1) prediction, ignoring valuable probability distributions and alternative high-confidence matches.

**Changes**:
```python
def _analyze_repository_structure(
    self, 
    snapshot: RepositorySnapshot, 
    queries: Optional[List[str]] = None,
    top_k_paths: int = 5,
    min_path_prob: float = 0.1,
    top_k_tools: int = 3
) -> Dict[str, Any]:
    """Enhanced analysis using top-k predictions with probability filtering."""
    grep_model = self._get_grep_model()
    if not grep_model:
        return {"key_files": [], "key_folders": [], "predictions": []}

    # Extract queries from conversation or use default repository analysis queries
    if not queries:
        queries = [
            "What are the main entry points and configuration files?",
            "Where is the core business logic implemented?",
            "What are the key test files and documentation?",
        ]

    # Get probability distributions for all queries
    ranked_files: Dict[str, float] = {}  # path -> max_probability
    ranked_folders: Dict[str, float] = {}  # folder -> max_probability
    all_predictions = []

    for query in queries:
        try:
            prediction = predict_action(grep_model, query)
            
            # Extract top-k paths with probabilities
            path_probs = prediction.path_probs
            top_path_indices = torch.topk(
                path_probs, 
                k=min(top_k_paths, len(path_probs))
            ).indices
            
            for idx in top_path_indices:
                prob = float(path_probs[idx])
                if prob >= min_path_prob:
                    path = grep_model.idx_to_label.get(idx.item(), "")
                    if path:
                        # Track max probability per path across all queries
                        ranked_files[path] = max(ranked_files.get(path, 0), prob)
                        # Update folder probabilities
                        path_obj = Path(path)
                        for parent in path_obj.parents:
                            if str(parent) != ".":
                                ranked_folders[str(parent)] = max(
                                    ranked_folders.get(str(parent), 0), prob
                                )
            
            # Extract top-k tools with probabilities
            tool_probs = prediction.tool_probs
            top_tool_indices = torch.topk(
                tool_probs, 
                k=min(top_k_tools, len(tool_probs))
            ).indices
            
            # Build prediction result with top-k paths
            top_paths = []
            for idx in top_path_indices:
                prob = float(path_probs[idx])
                if prob >= min_path_prob:
                    path = grep_model.idx_to_label.get(idx.item(), "")
                    top_tool_idx = torch.argmax(tool_probs).item()
                    recommended_tool = grep_model.idx_to_tool.get(top_tool_idx, "")
                    top_paths.append({
                        "path": path,
                        "prob": prob,
                        "tool": recommended_tool
                    })
            
            all_predictions.append({
                "query": query,
                "top_paths": top_paths,
                "recommended_tool": grep_model.idx_to_tool.get(
                    torch.argmax(tool_probs).item(), ""
                )
            })
        except Exception as e:
            logger.debug(f"Yudai-grep prediction failed for query '{query}': {e}")

    # Sort by probability (descending)
    sorted_files = sorted(ranked_files.items(), key=lambda x: x[1], reverse=True)
    sorted_folders = sorted(ranked_folders.items(), key=lambda x: x[1], reverse=True)

    # Also analyze directory structure from snapshot files
    dir_structure = RepositorySnapshotService.build_directory_index(snapshot.files)

    return {
        "key_files": [path for path, prob in sorted_files[:20]],
        "key_folders": [folder for folder, prob in sorted_folders[:15]],
        "predictions": all_predictions,
        "file_confidence_scores": dict(sorted_files[:20]),
        "directory_structure": self._summarize_directory_structure(dir_structure),
    }
```

**Update `_build_prompt()` to use confidence scores**:
```python
def _build_prompt(
    self,
    snapshot: RepositorySnapshot,
    conversation: Optional[Sequence[Dict[str, Any]]],
    max_messages: int,
    repo_analysis: Optional[Dict[str, Any]] = None,
) -> str:
    # ... existing code ...
    
    if repo_analysis:
        key_files = repo_analysis.get("key_files", [])
        file_scores = repo_analysis.get("file_confidence_scores", {})
        key_folders = repo_analysis.get("key_folders", [])
        predictions = repo_analysis.get("predictions", [])
        dir_structure = repo_analysis.get("directory_structure", "")

        grep_analysis = f"""
## Yudai-Grep Analysis (Intelligent File/Folder Detection)
### Key Files Identified (with confidence scores):
{chr(10).join(f"- {f} (confidence: {file_scores.get(f, 0):.2f})" for f in key_files[:10]) if key_files else "- No key files identified"}

### Key Folders Identified:
{chr(10).join(f"- {f}" for f in key_folders[:10]) if key_folders else "- No key folders identified"}

### Query-Based Predictions (Top-K):
{chr(10).join(f"- Query: {p['query']} → Tool: {p['recommended_tool']}" + chr(10) + chr(10).join(f"  • {path['path']} ({path['prob']:.2f})" for path in p.get('top_paths', [])[:3]) for p in predictions[:5]) if predictions else "- No predictions available"}

### Directory Structure:
{dir_structure[:800] if dir_structure else "Not available"}
"""
    # ... rest of prompt building ...
```

**Steps**:
1. Update `_analyze_repository_structure()` method signature to accept `top_k_paths`, `min_path_prob`, `top_k_tools` parameters
2. Replace single `predict_action()` call with top-k extraction logic using `torch.topk()`
3. Build probability-ranked dictionaries for files and folders across all queries
4. Sort files/folders by max probability (descending)
5. Update return dict to include `file_confidence_scores` for use in prompt building
6. Update `_build_prompt()` to display confidence scores and top-k paths per query
7. Update `generate()` method call to pass optional parameters if needed
8. Test with various query sets to verify ranking works correctly

**Benefits**:
- Surfaces multiple relevant files per query (not just top-1)
- Uses confidence scores for better file prioritization
- Filters low-confidence predictions automatically
- Tool predictions inform file processing strategy
- Better facts generation with ranked file context

---

## Dependencies

### Required
- `ChatContext` from `context.chat_context`
- `FactsAndMemoriesService` from `context.facts_and_memories`
- `RepositorySnapshotService` from `context.facts_and_memories`

### Optional
- Yudai-grep model (falls back gracefully if unavailable)
- PyTorch (for yudai-grep model loading)
