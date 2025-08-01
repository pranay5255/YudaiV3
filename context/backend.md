# YudaiV3 Backend Architecture

This document provides a comprehensive overview of the YudaiV3 backend architecture, its services, and data flow.

## Core Technologies
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Authentication**: GitHub OAuth2
- **Real-time Communication**: WebSockets
- **AI Integration**: DAifu Agent

## Service-Oriented Architecture
The backend is organized into distinct services, each responsible for a specific domain:

- **Auth Service**: Manages user authentication, token management, and profile retrieval. It handles the entire GitHub OAuth flow.
- **GitHub Service**: Interacts with the GitHub API to manage repositories, issues, pull requests, and other GitHub-related data.
- **DaifuUserAgent Service**: The core of the AI functionality, this service manages chat sessions, real-time communication via WebSockets, and integrates with the DAifu agent.
- **IssueChatServices**: This service is responsible for managing user-generated issues, tracking their state, and linking them to chat conversations and GitHub issues.
- **RepoProcessorGitIngest Service**: Handles the processing of Git repositories, including file dependency analysis and structure extraction.

## Data Flow and State Management

### User Authentication
1.  The user initiates the login process, and the `auth` service redirects them to GitHub for authentication.
2.  Upon successful authentication, GitHub issues a callback to the backend, which is handled by the `auth` service.
3.  The service exchanges the authorization code for an access token, creates or updates the user in the database, and stores the token.
4.  The access token is then sent to the frontend to be used for authenticated requests.

### Chat and Session Management
1.  When a user starts a new chat, the `daifuUserAgent` service creates a new session in the database.
2.  Real-time communication is established via a WebSocket connection, managed by the `UnifiedWebSocketManager`.
3.  As messages are exchanged, they are persisted in the `chat_messages` table and broadcast to the client in real-time.
4.  The DAifu agent processes user messages, and its responses are also managed through this service.

### GitHub Integration
1.  Authenticated users can access their GitHub repositories through the `github` service.
2.  This service fetches repository data, issues, and other information from the GitHub API, using the user's stored access token.
3.  It also handles the creation and management of GitHub issues, which are linked to user-generated issues in the database.

## Real-time Communication
- **WebSockets**: The backend uses WebSockets for real-time communication, primarily for chat functionality. The `UnifiedWebSocketManager` class is responsible for managing connections, broadcasting messages, and handling different message types.
- **State Synchronization**: The WebSocket implementation is designed to keep the frontend and backend in sync, with a defined set of message types for different state changes.

## Error Handling and Security
- **Error Handling**: The backend has a standardized approach to error handling, with custom exception handlers that return appropriate HTTP status codes and error messages.
- **Security**: Authentication is enforced on all protected endpoints, and the application uses JWT for secure communication. CORS is configured to restrict access to the frontend application.

## Database and Migrations
- **Database**: The application uses a PostgreSQL database with SQLAlchemy as the ORM. The schema is defined in `backend/models.py`.
- **Migrations**: Database migrations are handled by a script that initializes and updates the database schema based on the defined models.