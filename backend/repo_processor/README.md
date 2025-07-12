# File Dependencies API

A FastAPI server that extracts repository file dependencies using GitIngest and transforms them into a hierarchical structure for the FileDependencies component.

## Overview

The File Dependencies API provides endpoints to analyze GitHub repositories and extract file dependency information. It uses GitIngest to scrape repository data and categorizes files based on their type and purpose.

## Features

- **Repository Analysis**: Extract file structure from any public GitHub repository
- **File Categorization**: Automatically categorize files by type (Source Code, Documentation, Configuration, etc.)
- **Token Estimation**: Estimate token counts for files based on content size and file type
- **Hierarchical Structure**: Return files organized in a tree structure with directories and nested files
- **CORS Support**: Configured for frontend integration

## API Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "file-dependencies-api"
}
```

### Extract File Dependencies
```http
POST /extract
```

**Request Body:**
```json
{
  "repo_url": "https://github.com/username/repository",
  "max_file_size": 1000000
}
```

**Parameters:**
- `repo_url` (required): GitHub repository URL
- `max_file_size` (optional): Maximum file size in bytes to process (default: no limit)

**Response:**
```json
{
  "id": "root",
  "name": "repository-name",
  "type": "INTERNAL",
  "tokens": 15420,
  "Category": "Source Code",
  "isDirectory": true,
  "children": [
    {
      "id": "dir_src",
      "name": "src",
      "type": "INTERNAL",
      "tokens": 0,
      "Category": "Source Code",
      "isDirectory": true,
      "children": [
        {
          "id": "file_0",
          "name": "main.py",
          "type": "INTERNAL",
          "tokens": 1250,
          "Category": "Source Code",
          "isDirectory": false,
          "children": null,
          "expanded": false
        }
      ],
      "expanded": false
    }
  ],
  "expanded": true
}
```

## Usage Examples

### Python Example

```python
import requests
import json

# API base URL
base_url = "http://localhost:8000"

# Extract file dependencies from a repository
def extract_dependencies(repo_url: str, max_file_size: int = None):
    url = f"{base_url}/extract"
    
    payload = {
        "repo_url": repo_url,
        "max_file_size": max_file_size
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

# Example usage
repo_data = extract_dependencies(
    repo_url="https://github.com/GetSoloTech/solo-server.git",
    max_file_size=1000000
)

if repo_data:
    print(f"Repository: {repo_data['name']}")
    print(f"Total tokens: {repo_data['tokens']}")
    print(f"Files found: {len(repo_data['children'])}")
```

### JavaScript/TypeScript Example

```javascript
// Extract file dependencies
async function extractDependencies(repoUrl, maxFileSize = null) {
    const url = 'http://localhost:8000/extract';
    
    const payload = {
        repo_url: repoUrl,
        max_file_size: maxFileSize
    };
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            return await response.json();
        } else {
            console.error(`Error: ${response.status}`);
            const errorText = await response.text();
            console.error(errorText);
            return null;
        }
    } catch (error) {
        console.error('Network error:', error);
        return null;
    }
}

// Example usage
const repoData = await extractDependencies(
    'https://github.com/vuejs/vue',
    500000
);

if (repoData) {
    console.log(`Repository: ${repoData.name}`);
    console.log(`Total tokens: ${repoData.tokens}`);
    console.log(`Files found: ${repoData.children.length}`);
}
```

### cURL Example

```bash
# Extract file dependencies
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/nodejs/node",
    "max_file_size": 1000000
  }'
```

## File Categories

The API automatically categorizes files into the following categories:

- **Source Code**: `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.cpp`, `.c`, `.java`, etc.
- **Documentation**: `.md`, `.txt`, `.rst`, etc.
- **Configuration**: `.json`, `.yaml`, `.yml`, `.toml`, `.ini`, etc.
- **Styles**: `.css`, `.scss`, `.sass`, `.less`, etc.
- **Assets**: Images, fonts, and other static files
- **Build Files**: `.lock`, `.log`, build artifacts
- **Uncategorized**: Files that don't match known patterns

## Token Estimation

The API estimates token counts for files using file-type-specific ratios:

- **Code files** (`.py`, `.js`, `.ts`, etc.): ~4 characters per token
- **Markdown/Text** (`.md`, `.txt`): ~3 characters per token
- **JSON**: ~5 characters per token
- **YAML**: ~3 characters per token

## Running the Server

### Prerequisites

1. Install dependencies:
```bash
pip install fastapi uvicorn
```

2. Ensure the required modules are available:
   - `models.py` (contains data models)
   - `scraper_script.py` (contains GitIngest integration)

### Start the Server

```bash
# From the backend directory
python repo_processor/filedeps.py
```

Or using uvicorn directly:
```bash
uvicorn repo_processor.filedeps:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at `http://localhost:8000`

### Development

For development with auto-reload:
```bash
uvicorn repo_processor.filedeps:app --reload --port 8000
```

## Error Handling

The API returns appropriate HTTP status codes:

- `200`: Success
- `400`: Bad request (invalid repository URL, extraction failed)
- `500`: Internal server error

Error responses include details about what went wrong:

```json
{
  "detail": "Failed to extract data: Repository not found or inaccessible"
}
```

## CORS Configuration

The API is configured to allow requests from common development servers:
- `http://localhost:3000` (React dev server)
- `http://localhost:5173` (Vite dev server)

## Dependencies

- FastAPI
- Pydantic (for data validation)
- GitIngest (for repository extraction)
- uvicorn (ASGI server)

## File Structure

```
repo_processor/
├── __init__.py
├── filedeps.py          # Main API server
├── scraper_script.py    # GitIngest integration
├── treeDescriptions[LLMcall].py  # Tree processing utilities
└── README.md           # This file
```

## Contributing

When modifying the API:

1. Update the data models in `models.py` if needed
2. Test with various repository types
3. Update this README with any new endpoints or changes
4. Ensure CORS settings match your frontend requirements 