# PR: Unify Backend Data Models and Integrate Database

This pull request introduces a comprehensive refactoring of the backend to unify data models, integrate the PostgreSQL database for data persistence, and enhance the DAifu agent with authentication and live context.

## Summary

The primary goal of this work was to move from a transient, dictionary-based data flow to a robust, type-safe, and persistent architecture. We have successfully centralized all data models (Pydantic and SQLAlchemy), refactored the entire GitHub API layer to be database-aware, and integrated the authentication flow into the DAifu agent. This lays a solid and scalable foundation for future development.

## Key Changes

### 1. Unified Data Models (`backend/models.py`)
- **Centralized Pydantic Models**: All API request/response models, including `UserProfile`, `AuthResponse`, and new models for the GitHub API (`GitHubRepo`, `GitHubIssue`, etc.), are now defined in `models.py`. This provides a single source of truth for our application's data structures.
- **Extended SQLAlchemy Models**: The database schema has been significantly enhanced. The `Repository` table is updated to store rich metadata from GitHub, and new tables for `Issue`, `PullRequest`, and `Commit` have been added to persist this data.

### 2. Database Integration and Persistence (`backend/github/github_api.py`)
- **"Fetch, Save, Return" Logic**: All functions that call the GitHub API now follow an "upsert" (update or insert) pattern. Fresh data is fetched from GitHub, saved to our database, and then returned to the client. This ensures our application data is both persistent and up-to-date.
- **Automated DB Initialization**: The database schema is now created automatically when the backend application starts up, handled by an `on_startup` event in `backend/repo_processor/filedeps.py`.

### 3. DAifu Agent Enhancement (`backend/daifu/`)
- **Secured Endpoint**: The `/chat/daifu` endpoint is now a protected route that requires user authentication.
- **Live Context Injection**: The agent can now receive a repository context (`owner` and `name`). When provided, it fetches live data from GitHub—including repository details, issues, and commits—and injects this rich context directly into its prompt, enabling it to generate far more intelligent and relevant responses.

### 4. Temporary Disabling of `/extract` Endpoint
- The `/extract` endpoint, responsible for file dependency analysis, has been temporarily disabled. The database model refactoring broke its existing implementation, and it requires a dedicated effort to reintegrate.

---

## Next Steps: Fixing the `/extract` API

The `/extract` endpoint is incompatible with our new `Repository` model, which is now designed to store GitHub metadata, not file analysis results.

To fix this, we need to:
1.  **Create a New Database Model**: Introduce a new SQLAlchemy model in `models.py`, such as `FileAnalysis`, to store the results from the `GitIngest` process (file trees, tokens, categories, etc.).
2.  **Establish a Relationship**: Link this new `FileAnalysis` model to the `Repository` table with a one-to-one or one-to-many relationship.
3.  **Refactor the Endpoint**: Rewrite the logic inside the `/extract` function in `filedeps.py` to populate this new `FileAnalysis` table instead of the old `Repository` model.

---

## Proposed GitHub Issues

Here are the three most critical issues to create for the next phase of development:

### 1. Issue: Implement Frontend Authentication Flow
- **Title**: `feat(frontend): Implement GitHub OAuth Login and Token Management`
- **Description**: The backend now fully supports GitHub OAuth2, but the frontend has no user-facing implementation. This task involves creating an `AuthService` to handle API calls, building a `Login` component, and integrating token management (including authenticated requests and logout functionality) into the main application. This is the highest priority task to make the application testable.

### 2. Issue: Refactor and Re-enable File Dependency Analysis
- **Title**: `refactor(backend): Re-enable /extract Endpoint with New DB Model`
- **Description**: The `/extract` endpoint for file dependency analysis is currently disabled due to database model changes. This task involves creating a new SQLAlchemy model (`FileAnalysis`) to store `GitIngest` results and refactoring the endpoint to populate this new table. This will restore a key feature of the application.

### 3. Issue: Enhance DAifu Agent with File Content Context
- **Title**: `feat(ai): Allow DAifu Agent to Access File Content`
- **Description**: The DAifu agent can access repository metadata, but not the content of individual files. This task involves updating the `get_github_context` function to allow it to fetch the content of specific files from our `file_items` table. This will enable the agent to answer code-specific questions and provide much more granular and useful suggestions.
