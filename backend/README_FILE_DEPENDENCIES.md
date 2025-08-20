# File Dependencies and Chunking System

This document describes the implementation of file dependencies extraction and chunking system for YudaiV3.

## Overview

The file dependencies system provides:
1. **File Chunking**: Intelligent chunking of file content for embeddings
2. **Session Integration**: File dependencies tied to chat sessions
3. **Database Storage**: Persistent storage of file embeddings and metadata
4. **API Integration**: RESTful endpoints for file dependency management

## Architecture

### Core Components

#### 1. FileChunker (`utils/chunking.py`)
- **Purpose**: Chunks file content into smaller pieces for embeddings
- **Features**:
  - Simple, unified chunking strategy for all file types
  - Configurable chunk size and overlap
  - Token estimation for different content types
  - Word-boundary and punctuation-aware chunking

#### 2. Database Models (`models.py`)
- **FileEmbedding**: Stores file chunks with metadata
- **FileItem**: Stores file tree structure
- **ChatSession**: Enhanced with file dependency context

#### 3. API Endpoints

##### File Dependencies (`repo_processorGitIngest/filedeps.py`)
- `POST /filedeps/extract` - Extract file dependencies from repository
- `POST /filedeps/sessions/{session_id}/extract` - Extract for specific session

##### Session Components (`stateManagement/session_components_CRUD.py`)
- `GET /daifu/sessions/{session_id}/file-dependencies/session` - Get session file dependencies
- `POST /daifu/sessions/{session_id}/file-dependencies` - Add file dependency
- `DELETE /daifu/sessions/{session_id}/file-dependencies/{file_id}` - Delete file dependency

## Usage Examples

### 1. Extract File Dependencies for a Session

```python
# Backend API call
POST /filedeps/sessions/{session_id}/extract
{
    "repo_url": "https://github.com/user/repo"
}
```

### 2. Get File Dependencies for a Session

```python
# Backend API call
GET /daifu/sessions/{session_id}/file-dependencies/session
```

### 3. Frontend Integration

```typescript
// Extract file dependencies for a session
const dependencies = await ApiService.extractFileDependenciesForSession(
    sessionId,
    repoUrl,
    sessionToken
);

// Get file dependencies for a session
const fileDependencies = await ApiService.getFileDependenciesSession(
    sessionId,
    sessionToken
);
```

## File Chunking Strategy

### Unified Approach
- Simple, consistent chunking for all file types
- Word-boundary and punctuation-aware splitting
- Configurable chunk size and overlap
- Preserves natural text boundaries (spaces, newlines, punctuation)
- Efficient and maintainable implementation

## Database Schema

### FileEmbedding Table
```sql
CREATE TABLE file_embeddings (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id),
    repository_id INTEGER REFERENCES repositories(id),
    file_path VARCHAR(1000) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    chunk_index INTEGER DEFAULT 0,
    chunk_text TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    file_metadata JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

### FileItem Table
```sql
CREATE TABLE file_items (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id),
    name VARCHAR(500) NOT NULL,
    path VARCHAR(1000) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    category VARCHAR(100) NOT NULL,
    tokens INTEGER DEFAULT 0,
    is_directory BOOLEAN DEFAULT FALSE,
    parent_id INTEGER REFERENCES file_items(id),
    content_size INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

## Configuration

### Chunking Parameters
- **max_chunk_size**: Maximum characters per chunk (default: 1000)
- **overlap**: Character overlap between chunks (default: 100)

### Token Estimation
- **Code files**: ~4 characters per token
- **Natural language**: ~3 characters per token
- **Mixed content**: Intelligent detection

## Integration with Frontend

### FileDependencies.tsx Component
The frontend component now supports:
- Session-based file dependency loading
- Real-time file dependency updates
- Integration with context management
- Token counting and statistics

### SessionProvider.tsx
Enhanced with:
- File dependency management methods
- Session context with file embeddings
- Automatic file dependency loading

## Testing

Run the test suite:
```bash
cd backend
uv run python test_file_dependencies.py
```

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/filedeps/extract` | Extract file dependencies from repository |
| POST | `/filedeps/sessions/{session_id}/extract` | Extract for specific session |
| GET | `/daifu/sessions/{session_id}/file-dependencies/session` | Get session file dependencies |
| POST | `/daifu/sessions/{session_id}/file-dependencies` | Add file dependency |
| DELETE | `/daifu/sessions/{session_id}/file-dependencies/{file_id}` | Delete file dependency |

## Future Enhancements

1. **Semantic Search**: Implement vector search using embeddings
2. **Real-time Updates**: WebSocket integration for live updates
3. **Batch Processing**: Handle large repositories efficiently
4. **Caching**: Redis integration for performance
5. **Analytics**: File dependency usage statistics

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure utils package is properly structured
2. **Database Errors**: Check PostgreSQL connection and schema
3. **Chunking Issues**: Verify file content encoding
4. **Session Errors**: Ensure session exists and user has access

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

When adding new file types:
1. Add chunking strategy to `FileChunker` class
2. Update token estimation logic
3. Add tests for new file type
4. Update documentation

## Dependencies

- FastAPI
- SQLAlchemy
- PostgreSQL
- Python 3.8+
- uv (package manager)
