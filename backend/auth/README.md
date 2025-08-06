# Authentication API Documentation

## Overview

This module provides authentication services for YudaiV3 using GitHub OAuth. The authentication system uses two types of tokens:

1. **GitHub Auth Tokens** (`AuthToken`) - Stored in the database, used for GitHub API access
2. **Session Tokens** (`SessionToken`) - Used for frontend authentication

## API Endpoints

### 1. Create Session from GitHub Token

**Endpoint**: `POST /auth/api/create-session`

**Description**: Creates a session token using a valid GitHub access token. This endpoint validates the GitHub token and creates a new session token for frontend authentication.

**Request Body**:
```json
{
  "github_token": "gho_your_github_access_token_here"
}
```

**Response**:
```json
{
  "session_token": "generated_session_token_here",
  "expires_at": "2025-08-07T10:00:00Z",
  "user": {
    "id": 1,
    "github_username": "username",
    "github_user_id": "12345",
    "email": "user@example.com",
    "display_name": "User Name",
    "avatar_url": "https://avatars.githubusercontent.com/u/12345?v=4",
    "created_at": "2025-08-06T10:00:00Z",
    "last_login": "2025-08-06T10:00:00Z"
  }
}
```

**Error Responses**:
- `400 Bad Request`: Missing or empty GitHub token
- `401 Unauthorized`: Invalid or expired GitHub token
- `500 Internal Server Error`: Server error

### 2. Validate Session Token

**Endpoint**: `GET /auth/api/user?session_token=<token>`

**Description**: Validates a session token and returns user information.

**Response**:
```json
{
  "id": 1,
  "github_username": "username",
  "github_id": "12345",
  "display_name": "User Name",
  "email": "user@example.com",
  "avatar_url": "https://avatars.githubusercontent.com/u/12345?v=4"
}
```

### 3. OAuth Login

**Endpoint**: `GET /auth/api/login`

**Description**: Returns the GitHub OAuth login URL.

**Response**:
```json
{
  "login_url": "https://github.com/login/oauth/authorize?client_id=..."
}
```

## Usage Flow

1. **User initiates login**: Call `/auth/api/login` to get GitHub OAuth URL
2. **User completes OAuth**: User is redirected to GitHub and back to `/auth/callback`
3. **Create session**: Use the GitHub token to create a session via `/auth/api/create-session`
4. **Frontend authentication**: Use the session token for subsequent API calls

## Security Notes

- GitHub tokens are never exposed to the frontend
- Session tokens are used for frontend authentication
- All tokens have expiration times
- Expired tokens are automatically invalidated

## Database Schema

### AuthToken Table
- Stores GitHub OAuth access tokens
- Links to users via `user_id`
- Has expiration and active status

### SessionToken Table
- Stores frontend session tokens
- Links to users via `user_id`
- Has expiration and active status

## Error Handling

The API provides consistent error responses with appropriate HTTP status codes and descriptive error messages. All errors are logged for debugging purposes. 