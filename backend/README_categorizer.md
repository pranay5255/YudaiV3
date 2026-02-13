# GitHub Issue Categorization System

A comprehensive AI-powered system for automatically categorizing GitHub issues into specific categories and generating appropriate context for LLM processing.

## Overview

This system implements an internal logic to categorize GitHub issues into 12 different categories, each with specialized system prompts, context graphs, and preprocessing pipelines. The categorization enables targeted context retrieval and optimized LLM responses for different types of issues.

## Supported Categories

The system categorizes issues into the following categories:

### 1. Bug Fix (`bug_fix`)
- **Purpose**: Issues related to fixing software bugs and errors
- **Keywords**: bug, fix, error, crash, exception, traceback
- **Context**: Error logs, stack traces, recent commits, failing tests
- **System Prompts**: Debug mode, error analysis, fix validation

### 2. Test Innovation (`test_innovation`) 
- **Purpose**: Issues related to testing framework improvements and innovations
- **Keywords**: test innovation, testing framework, test automation
- **Context**: Testing infrastructure, framework configurations
- **System Prompts**: Testing expert, framework selection, test architecture

### 3. Test Coverage (`test_coverage`)
- **Purpose**: Issues related to adding tests and improving coverage
- **Keywords**: test coverage, add tests, unit test, integration test
- **Context**: Coverage reports, uncovered code paths, test files
- **System Prompts**: Test writing, coverage analysis, quality assurance

### 4. CI/CD - GitHub Actions (`cicd_github_actions`)
- **Purpose**: Issues related to GitHub Actions workflows and automation
- **Keywords**: github actions, workflow, ci/cd, pipeline, automation
- **Context**: Workflow files, build processes, deployment pipelines
- **System Prompts**: CI/CD expert, workflow design, automation

### 5. CI/CD - Docker (`cicd_docker`)
- **Purpose**: Issues related to Docker containerization
- **Keywords**: docker, container, dockerfile, containerization
- **Context**: Dockerfile, docker-compose, container configurations
- **System Prompts**: Docker expert, containerization, deployment optimization

### 6. Refactor (`refactor`)
- **Purpose**: Issues related to code refactoring and improvements
- **Keywords**: refactor, cleanup, optimize, restructure, improve
- **Context**: Code quality metrics, technical debt analysis
- **System Prompts**: Refactoring expert, code quality, architecture improvement

### 7. Feature Scaffolding (`feature_scaffolding`)
- **Purpose**: Issues related to scaffolding and boilerplate generation
- **Keywords**: scaffold, boilerplate, template, generator, setup
- **Context**: Project structure, templates, configuration files
- **System Prompts**: Scaffolding expert, architecture design, boilerplate generation

### 8. Documentation Update (`docs_update`)
- **Purpose**: Issues related to updating existing documentation
- **Keywords**: docs update, documentation update, readme update
- **Context**: Existing documentation files, outdated content
- **System Prompts**: Documentation writer, technical writer, docs review

### 9. Documentation Create (`docs_create`)
- **Purpose**: Issues related to creating new documentation
- **Keywords**: docs create, create documentation, add documentation
- **Context**: Undocumented features, API endpoints, user journeys
- **System Prompts**: Documentation creator, API docs, user guide

### 10. Data Models - Pydantic (`data_models_pydantic`)
- **Purpose**: Issues related to Pydantic data models and validation
- **Keywords**: pydantic, data model, schema, validation
- **Context**: Model definitions, validation rules, serialization
- **System Prompts**: Pydantic expert, data modeling, validation design

### 11. Database Models - SQLAlchemy (`db_models_sqlalchemy`)
- **Purpose**: Issues related to SQLAlchemy ORM models
- **Keywords**: sqlalchemy, db model, database model, orm
- **Context**: Database schema, model relationships, migrations
- **System Prompts**: SQLAlchemy expert, database design, ORM optimization

### 12. PostgreSQL Database (`postgres_db`)
- **Purpose**: Issues related to PostgreSQL database operations
- **Keywords**: postgres, postgresql, database, sql, query
- **Context**: Database configuration, performance, queries
- **System Prompts**: Postgres expert, database admin, performance tuning

## Architecture

### Core Components

1. **`issue_categorizer.py`**
   - Main categorization engine
   - Keyword-based classification algorithm
   - Context graph generation
   - Confidence scoring system

2. **`system_prompt_templates.py`**
   - Specialized system prompt templates for each category
   - Combined prompt generation for multi-category issues
   - Preprocessing instruction generation

3. **`github_issue_processor.py`**
   - Main orchestrator for the entire pipeline
   - Bulk processing capabilities
   - Statistics and analytics
   - Export/import functionality

4. **`api_endpoints.py`**
   - FastAPI REST API endpoints
   - Real-time categorization service
   - Integration-ready endpoints

### Context Graph Structure

Each category has an associated context graph that defines:

- **Relevant Files**: Specific files that should be prioritized for context retrieval
- **Relevant Directories**: Directories containing relevant code/configuration
- **GitHub Labels**: Recommended labels for the category
- **Dependencies**: Key dependencies and libraries related to the category
- **System Prompts**: Specialized prompt templates for the category
- **Preprocessing Steps**: Specific actions to take before LLM processing

### Classification Algorithm

The system uses a multi-factor keyword-based classification approach:

1. **Title Analysis** (3x weight): Keywords found in issue title
2. **Body Analysis** (1.5x weight): Keywords found in issue description
3. **Label Analysis** (5x weight): Keywords matching existing GitHub labels

Confidence scores are normalized and filtered with a minimum threshold of 0.1.

## Usage

### Python API

```python
from github_issue_processor import GitHubIssueProcessor

# Initialize processor
processor = GitHubIssueProcessor()

# Process a single issue
issue_data = {
    "id": 12345,
    "number": 42,
    "title": "Bug: FastAPI endpoint returning 500 error",
    "body": "Error description with stack trace...",
    "labels": [{"name": "bug"}, {"name": "backend"}]
}

result = processor.process_issue(issue_data)
print(f"Categories: {result.categories}")
print(f"System Prompt: {result.system_prompt[:100]}...")
```

### REST API

Start the FastAPI server:

```bash
cd backend
python3 api_endpoints.py
```

API Endpoints:

- `POST /categorize` - Categorize a single issue
- `POST /categorize/bulk` - Categorize multiple issues
- `GET /categories` - Get available categories
- `GET /statistics` - Get processing statistics
- `POST /preprocessing-pipeline` - Get preprocessing pipeline for categories
- `GET /system-prompt/{category}` - Get system prompt for specific category

### Example REST API Usage

```bash
# Categorize a single issue
curl -X POST "http://localhost:8000/categorize" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 12345,
    "number": 42,
    "title": "Bug: FastAPI endpoint returning 500 error",
    "body": "Error description...",
    "labels": [{"name": "bug"}]
  }'
```

## Response Format

The system returns comprehensive categorization results:

```json
{
  "issue_id": "12345",
  "issue_number": 42,
  "title": "Bug: FastAPI endpoint returning 500 error",
  "categories": ["bug_fix", "postgres_db"],
  "confidence_scores": {
    "bug_fix": 0.85,
    "postgres_db": 0.42
  },
  "context_graph": {
    "categories": ["bug_fix", "postgres_db"],
    "relevant_files": ["backend/models.py", "backend/run_server.py"],
    "relevant_directories": ["backend/", "tests/"],
    "dependencies": ["fastapi", "sqlalchemy", "pytest"],
    "system_prompts": ["debug_mode_prompt", "error_analysis_prompt"],
    "preprocessing_steps": ["extract_error_logs", "identify_failing_tests"]
  },
  "system_prompt": "You are an expert debugging assistant...",
  "preprocessing_instructions": [
    "Extract and analyze error logs and stack traces",
    "Gather reproduction steps and environment details"
  ],
  "recommended_actions": [
    "Gather error logs and reproduction steps",
    "Run existing tests to identify failures"
  ],
  "processing_timestamp": "2024-01-15T10:30:00"
}
```

## Integration Workflow

### 1. GitHub Webhook Integration

```python
# Webhook handler example
@app.post("/webhook/github")
async def github_webhook(request: Request):
    payload = await request.json()
    
    if payload.get("action") == "opened":
        issue = payload.get("issue")
        result = processor.process_issue(issue)
        
        # Use categorization results for:
        # - File context retrieval
        # - System prompt selection
        # - Preprocessing pipeline execution
        # - GitHub API context fetching
```

### 2. Context Retrieval Pipeline

Based on categorization results, implement targeted context retrieval:

```python
def retrieve_context(result: ProcessingResult):
    context = {}
    
    # File retrieval based on context graph
    for file_path in result.context_graph["relevant_files"]:
        context["files"][file_path] = read_file(file_path)
    
    # GitHub API calls based on categories
    if "bug_fix" in result.categories:
        context["recent_commits"] = fetch_recent_commits()
        context["related_issues"] = fetch_related_issues()
    
    if "test_coverage" in result.categories:
        context["coverage_report"] = generate_coverage_report()
    
    return context
```

### 3. LLM Integration

Use the specialized system prompts for optimal LLM responses:

```python
def process_with_llm(result: ProcessingResult, context: dict):
    messages = [
        {"role": "system", "content": result.system_prompt},
        {"role": "user", "content": f"Issue: {result.title}\n\nContext: {context}"}
    ]
    
    # Send to LLM with category-optimized prompt
    response = llm_client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )
    
    return response
```

## Performance and Scalability

### Benchmarks

- **Single Issue Processing**: ~50-100ms
- **Bulk Processing (100 issues)**: ~5-8 seconds
- **Memory Usage**: ~10-15MB for categorizer
- **API Response Time**: ~100-200ms per request

### Optimization Features

- **Keyword Caching**: Pre-computed keyword mappings for fast lookup
- **Batch Processing**: Efficient bulk processing with error handling
- **Lazy Loading**: Context graphs loaded on-demand
- **Configurable Thresholds**: Adjustable confidence thresholds

## Configuration

### Customizing Categories

Add new categories by extending the `IssueCategory` enum and updating:

1. Keyword mappings in `_initialize_keywords()`
2. Context graphs in `_initialize_context_graphs()`
3. System prompt templates in `_initialize_prompt_templates()`

### Adjusting Classification

Modify classification weights in `classify_issue()`:

```python
# Current weights
title_matches * 3.0      # Title keywords
body_matches * 1.5       # Body keywords  
label_matches * 5.0      # Label keywords
```

### Environment Variables

```bash
# Optional configuration
CATEGORIZER_LOG_LEVEL=INFO
CATEGORIZER_CONFIDENCE_THRESHOLD=0.1
CATEGORIZER_MAX_CATEGORIES=5
```

## Testing

Run the test suite:

```bash
cd backend
python3 -m pytest tests/
```

Test coverage includes:
- Keyword matching accuracy
- Category assignment correctness
- System prompt generation
- API endpoint functionality
- Bulk processing performance

## Monitoring and Analytics

### Built-in Statistics

```python
# Get processing statistics
stats = processor.get_category_statistics()
print(f"Total issues processed: {stats['total_issues']}")
print(f"Most common category: {stats['most_common_category']}")
```

### Export Capabilities

```python
# Export results for analysis
processor.export_processing_results("results.json")
```

## Contributing

### Adding New Categories

1. Add to `IssueCategory` enum
2. Define keywords in `_initialize_keywords()`
3. Create context graph in `_initialize_context_graphs()`
4. Add system prompt template
5. Update tests and documentation

### Improving Classification

1. Analyze misclassification patterns
2. Add/refine keywords
3. Adjust weights and thresholds
4. Add new classification features

## License

This categorization system is part of the YudaiV3 project and follows the same licensing terms.

---

For detailed API documentation, visit `/docs` when running the FastAPI server.