# Plan: Context-Enriched GitHub Issue Creation (Daifu Handoff)

## Goal
When creating a GitHub issue from a chat/Daifu handoff, automatically gather and summarize three key context areas. These will be used to populate a prompt template for the Architect Agent.

## Step-by-Step Plan

### Step 1: Gather Conversation and File Dependency Context (No Change)
1.  **Conversation Context**:
    *   **Reuse**: Use `ChatService.get_chat_messages` to fetch the full chat history.
    *   **Action**: This will provide the conversation context.

2.  **File Dependencies Context**:
    *   **Reuse**: Use the file dependency API (`/extract` endpoint in `filedeps.py`).
    *   **Action**: This provides the hierarchical file structure and token counts.

### Step 2: Code-Aware Context Generation (Combined Step)
1.  **Code-Aware Analysis**:
    *   **Adopt**: Implement the workflow from `code_inspector_agent.ipynb` to create a `Code-Aware Context` string.
    *   **Action**: This process will involve:
        *   Indexing the relevant codebase.
        *   Using semantic search to find relevant code sections based on the conversation context.
        *   Analyzing the top N files to identify:
            *   **Internal calls**: Key functions, classes, and their relationships.
            *   **External libraries**: Dependencies imported and used within the code.
    *   **Output**: A single, consolidated string containing a summary of the codebase's structure, key components, and dependencies relevant to the task.

### Step 3: Architect Agent Prompt Generation
1.  **Define Prompt Template**:
    *   **Action**: Create a template in `backend/daifuUserAgent/architectAgent/promptTemplate.py`. This template will be a string with placeholders for the three context areas.
    *   **Example Structure**:
        ```python
        ARCHITECT_PROMPT_TEMPLATE = """
        System Prompt: {system_prompt}

        Conversation Context:
        {conversation_context}

        File Dependencies Context:
        {file_dependencies_context}

        Code-Aware Context:
        {code_aware_context}
        """
        ```

2.  **Compose Final Prompt**:
    *   **Action**: In a service layer (likely extending `issue_service.py`), populate the `ARCHITECT_PROMPT_TEMPLATE` with the context strings gathered in the previous steps.
    *   **System Prompt**: The `{system_prompt}` placeholder should be filled with a prompt modeled after `backend/daifuUserAgent/architectAgent/exampleSystemPrompt.txt`, providing the agent with its identity, capabilities, and rules.

---

## Summary of Changes
- Steps 2 and 3 from the old plan are now a single "Code-Aware Context Generation" step, using the `code_inspector_agent.ipynb` methodology.
- The output of each step is a string destined for a formal prompt template.
- A new `promptTemplate.py` file will define the structure for the final agent prompt.
- The final output is a well-structured prompt ready for the Architect Agent, rather than just a GitHub issue body.

This revised plan is minimal, leverages existing and new patterns effectively, and aligns with your request to use the code inspector and a formal prompt templating structure.
