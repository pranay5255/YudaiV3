# Integration Tests for YudaiV3 Backend

This directory contains comprehensive integration tests for the YudaiV3 backend, focusing on GitHub OAuth authentication and API integration.

## Test Structure

```
tests/
├── __init__.py                     # Test package initialization
├── conftest.py                     # Pytest configuration and fixtures
├── test_github_auth_integration.py # GitHub OAuth authentication tests
├── test_github_api_integration.py  # GitHub API functionality tests
├── test_daifu_integration.py       # DAifu chat integration tests
└── README.md                       # This file
```

## Test Coverage

### 1. GitHub Authentication Tests (`test_github_auth_integration.py`)

**TestGitHubAuthIntegration**
- ✅ Authentication configuration endpoint
- ✅ Authentication status (authenticated/unauthenticated)
- ✅ OAuth login initiation and redirect
- ✅ OAuth callback handling (success/failure)
- ✅ User profile management
- ✅ Logout functionality
- ✅ Token expiration handling
- ✅ Invalid token handling
- ✅ Multiple active tokens support
- ✅ User information updates on re-login

**TestTokenManagement**
- ✅ Token creation and storage
- ✅ Token deactivation
- ✅ Token expiration logic
- ✅ Database relationships

**TestUserManagement**
- ✅ User creation and uniqueness
- ✅ User-token relationships
- ✅ User-repository relationships

### 2. GitHub API Tests (`test_github_api_integration.py`)

**TestGitHubAPIIntegration**
- ✅ Repository listing with authentication
- ✅ Repository details retrieval
- ✅ Issue management (list/create)
- ✅ Pull request listing
- ✅ Commit history retrieval
- ✅ Repository search functionality
- ✅ Parameter handling (state, branch, sort)

**TestGitHubAPIAuthentication**
- ✅ API instance creation with valid tokens
- ✅ Error handling for missing/expired tokens
- ✅ Token validation logic

**TestGitHubAPIErrorHandling**
- ✅ API error responses
- ✅ Repository not found errors
- ✅ Permission denied errors
- ✅ Rate limiting simulation

**TestRepositoryDataIntegration**
- ✅ Repository extraction with authentication
- ✅ Repository listing from database
- ✅ File listing functionality

**TestGitHubAPIPerformance**
- ✅ Concurrent API calls
- ✅ Rate limiting simulation
- ✅ Performance under load

**TestGitHubAPIValidation**
- ✅ Input validation
- ✅ Invalid parameter handling
- ✅ Error response formatting

### 3. DAifu Integration Tests (`test_daifu_integration.py`)

**TestDaifuChatIntegration**
- ✅ Basic chat functionality
- ✅ Authentication context integration
- ✅ Conversation history management
- ✅ Code message handling
- ✅ Context cards support
- ✅ Error handling (missing API key, timeouts)

**TestDaifuPromptIntegration**
- ✅ GitHub context inclusion in prompts
- ✅ Conversation history in prompts
- ✅ Prompt building logic

**TestDaifuAuthenticationIntegration**
- ✅ Authenticated user chat
- ✅ Unauthenticated user chat
- ✅ Repository context integration

**TestDaifuValidation**
- ✅ Input validation
- ✅ Message content validation
- ✅ Conversation ID handling

**TestDaifuPerformance**
- ✅ Concurrent conversations
- ✅ Memory usage with multiple conversations

## Database Setup

The tests use dummy data fixtures that create:

### Users Table
```python
User(
    github_username="testuser",
    github_user_id="123456",
    email="testuser@example.com",
    display_name="Test User",
    avatar_url="https://avatars.githubusercontent.com/u/123456?v=4"
)
```

### Auth Tokens Table
```python
AuthToken(
    user_id=1,
    access_token="gho_test_token_123456789",
    token_type="bearer",
    scope="repo user email",
    expires_at=datetime.utcnow() + timedelta(hours=8),
    is_active=True
)
```

### Repositories Table
```python
Repository(
    user_id=1,
    repo_url="https://github.com/testuser/test-repo",
    repo_name="test-repo",
    repo_owner="testuser",
    total_files=10,
    total_tokens=5000,
    status="completed"
)
```

### File Items Table
```python
FileItem(
    repository_id=1,
    name="main.py",
    path="src/main.py",
    file_type="INTERNAL",
    category="Source Code",
    tokens=1000,
    is_directory=False
)
```

## Running Tests

### Prerequisites

1. Install test dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure you're in the backend directory:
```bash
cd backend
```

### Running All Tests

```bash
# Using the test runner (recommended)
python run_tests.py -v

# Using pytest directly
python -m pytest tests/ -v
```

### Running Specific Test Categories

```bash
# Authentication tests only
python run_tests.py --auth -v

# GitHub API tests only
python run_tests.py --github -v

# DAifu integration tests only
python run_tests.py --daifu -v
```

### Running Specific Test Patterns

```bash
# Run tests matching a pattern
python run_tests.py -k "test_oauth" -v

# Run specific test class
python run_tests.py -k "TestGitHubAuthIntegration" -v

# Run specific test method
python run_tests.py -k "test_login_redirect" -v
```

### Test Environment Setup

```bash
# Set up test environment only
python run_tests.py --setup-only
```

## Test Configuration

### Environment Variables

The tests use these environment variables:

```bash
GITHUB_CLIENT_ID=test_client_id
GITHUB_CLIENT_SECRET=test_client_secret
GITHUB_REDIRECT_URI=http://localhost:3000/auth/callback
OPENROUTER_API_KEY=test_openrouter_key
DATABASE_URL=sqlite:///./test.db
DB_ECHO=false
```

### Test Database

- Uses SQLite in-memory database for fast testing
- Database is created/destroyed for each test
- Dummy data is inserted via fixtures
- No persistent data between tests

## Mocking Strategy

### GitHub API Mocking

```python
@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses"""
    mock_api = MagicMock()
    mock_api.repos.list_for_authenticated_user.return_value = [...]
    return mock_api
```

### OAuth Flow Mocking

```python
@patch('requests.post')
@patch('requests.get')
def test_oauth_callback_success(self, mock_get, mock_post, ...):
    # Mock token exchange
    mock_post.return_value.json.return_value = {"access_token": "..."}
    # Mock user info
    mock_get.return_value.json.return_value = {"id": 123, "login": "testuser"}
```

### DAifu API Mocking

```python
@patch('requests.post')
def test_daifu_chat_basic(self, mock_post, ...):
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}]
    }
```

## Integration Points Tested

### 1. Authentication Flow
- GitHub OAuth initiation → Backend state generation
- GitHub callback → Token exchange → User creation
- Token validation → API access → Database queries

### 2. API Integration
- Authentication → GitHub API calls → Response processing
- Database queries → User context → API responses
- Error handling → Graceful degradation

### 3. Chat Integration
- Authentication → User context → Prompt building
- Repository data → Context injection → LLM calls
- Conversation history → Memory management

## Test Data Flow

```
1. Test Setup
   ├── Create test database
   ├── Insert dummy users
   ├── Insert dummy tokens
   └── Insert dummy repositories

2. Test Execution
   ├── Mock external APIs
   ├── Make HTTP requests
   ├── Verify responses
   └── Check database state

3. Test Cleanup
   ├── Clear database
   ├── Reset mocks
   └── Clean up files
```

## Debugging Tests

### Verbose Output

```bash
python run_tests.py -v
```

### Specific Test Debugging

```bash
# Run single test with maximum verbosity
python -m pytest tests/test_github_auth_integration.py::TestGitHubAuthIntegration::test_login_redirect -v -s
```

### Database Inspection

```python
# Add this to any test to inspect database state
print(f"Users: {test_db.query(User).all()}")
print(f"Tokens: {test_db.query(AuthToken).all()}")
```

### Mock Inspection

```python
# Check if mock was called correctly
print(f"Mock called: {mock_api.repos.list_for_authenticated_user.called}")
print(f"Call args: {mock_api.repos.list_for_authenticated_user.call_args}")
```

## Continuous Integration

These tests are designed to run in CI/CD environments:

- No external dependencies (all mocked)
- Fast execution (in-memory database)
- Comprehensive coverage
- Clear pass/fail indicators

### CI Configuration Example

```yaml
# .github/workflows/test.yml
name: Backend Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r backend/requirements.txt
      - run: cd backend && python run_tests.py -v
```

## Contributing

When adding new tests:

1. Follow the existing test structure
2. Use descriptive test names
3. Add appropriate fixtures
4. Mock external dependencies
5. Test both success and failure cases
6. Update this documentation

## Common Issues

### Database Errors
- Ensure test database is cleaned up between tests
- Check that fixtures are properly configured
- Verify SQLAlchemy relationships

### Mock Failures
- Ensure mocks are properly configured
- Check that patch decorators are in correct order
- Verify mock return values match expected format

### Authentication Errors
- Check that test tokens are properly configured
- Verify that auth headers are correctly formatted
- Ensure user fixtures are properly created

This comprehensive test suite ensures that the GitHub OAuth authentication and API integration works correctly across all scenarios and edge cases. 