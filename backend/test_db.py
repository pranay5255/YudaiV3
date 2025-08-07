#!/usr/bin/env python3
"""
YudaiV3 Database Validation Script
==================================

Comprehensive database and API validation for Docker build-time checks.
Tests all SQLAlchemy models against FastAPI endpoints with colored terminal output.

This script validates:
- Model creation, relationships, and constraints
- API endpoint integration with database models
- Request/response model consistency
- Data integrity and foreign key relationships
"""

import sys
import traceback
import uuid
from datetime import datetime, timedelta
from typing import List


# Terminal colors for output formatting
class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Test result tracking
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []
        self.start_time = datetime.now()
    
    def pass_test(self, test_name: str):
        self.passed += 1
        print(f"{Colors.GREEN}✅ PASS{Colors.END} {test_name}")
    
    def fail_test(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"{Colors.RED}❌ FAIL{Colors.END} {test_name}")
        print(f"{Colors.RED}   └── {error}{Colors.END}")
    
    def info(self, message: str):
        print(f"{Colors.CYAN}ℹ️  INFO{Colors.END} {message}")
    
    def section(self, title: str):
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}🔍 {title}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    
    def summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        total = self.passed + self.failed
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.WHITE}📊 DATABASE VALIDATION SUMMARY{Colors.END}")
        print(f"{Colors.BOLD}{Colors.WHITE}{'='*60}{Colors.END}")
        
        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED{Colors.END}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED{Colors.END}")
        
        print(f"{Colors.WHITE}Total Tests: {total}{Colors.END}")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.END}")
        print(f"{Colors.YELLOW}Duration: {duration:.2f}s{Colors.END}")
        
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ FAILED TESTS:{Colors.END}")
            for i, error in enumerate(self.errors, 1):
                print(f"{Colors.RED}{i:2d}. {error}{Colors.END}")
        
        return self.failed == 0

# Global test result tracker
result = TestResult()

def setup_test_environment():
    """Set up the test environment and database connection"""
    try:
        # Import required modules
        from db.database import init_db
        
        result.info("Setting up test environment...")
        
        # Initialize database
        init_db()
        
        result.info("Database initialized successfully")
        return True
        
    except Exception as e:
        result.fail_test("Database Setup", str(e))
        return False

def test_database_models():
    """Test all SQLAlchemy models for basic CRUD operations"""
    result.section("DATABASE MODELS VALIDATION")
    
    try:
        from db.database import SessionLocal
        from models import (
            AuthToken,
            ChatMessage,
            ChatSession,
            ContextCard,
            FileAnalysis,
            FileEmbedding,
            FileItem,
            IdeaItem,
            Repository,
            User,
            UserIssue,
        )

        from utils import utc_now
        
        db = SessionLocal()
        
        # Test 1: User Model
        try:
            test_user = User(
                github_username="test_user_validation",
                github_user_id="test_id_12345",
                email="test@validation.com",
                display_name="Test User",
                avatar_url="https://example.com/avatar.jpg"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            
            # Verify user was created
            retrieved_user = db.query(User).filter(User.id == test_user.id).first()
            if retrieved_user and retrieved_user.github_username == "test_user_validation":
                result.pass_test("User Model - Create & Retrieve")
            else:
                result.fail_test("User Model - Create & Retrieve", "User data mismatch")
                
        except Exception as e:
            result.fail_test("User Model - Create & Retrieve", str(e))
        
        # Test 2: AuthToken Model with User relationship
        try:
            auth_token = AuthToken(
                user_id=test_user.id,
                access_token="test_token_12345",
                token_type="bearer",
                scope="repo user",
                expires_at=utc_now() + timedelta(hours=24),
                is_active=True
            )
            db.add(auth_token)
            db.commit()
            db.refresh(auth_token)
            
            # Test relationship
            if auth_token.user.github_username == "test_user_validation":
                result.pass_test("AuthToken Model - Create & Relationship")
            else:
                result.fail_test("AuthToken Model - Create & Relationship", "Relationship failed")
                
        except Exception as e:
            result.fail_test("AuthToken Model - Create & Relationship", str(e))
        
        # Test 3: Repository Model
        try:
            test_repo = Repository(
                github_repo_id=987654321,
                user_id=test_user.id,
                name="test-repo",
                owner="test_user_validation",
                full_name="test_user_validation/test-repo",
                repo_url="https://github.com/test_user_validation/test-repo",
                description="Test repository for validation",
                private=False,
                html_url="https://github.com/test_user_validation/test-repo",
                clone_url="https://github.com/test_user_validation/test-repo.git",
                language="Python",
                stargazers_count=1,
                forks_count=0,
                open_issues_count=0
            )
            db.add(test_repo)
            db.commit()
            db.refresh(test_repo)
            
            result.pass_test("Repository Model - Create")
            
        except Exception as e:
            result.fail_test("Repository Model - Create", str(e))
        
        # Test 4: ChatSession Model
        try:
            chat_session = ChatSession(
                user_id=test_user.id,
                session_id=f"test_session_{uuid.uuid4().hex[:8]}",
                title="Test Chat Session",
                description="Test session for validation",
                repo_owner="test_user_validation",
                repo_name="test-repo",
                repo_branch="main",
                is_active=True,
                total_messages=0,
                total_tokens=0,
                last_activity=utc_now()
            )
            db.add(chat_session)
            db.commit()
            db.refresh(chat_session)
            
            result.pass_test("ChatSession Model - Create")
            
        except Exception as e:
            result.fail_test("ChatSession Model - Create", str(e))
        
        # Test 5: ChatMessage Model with Session relationship
        try:
            chat_message = ChatMessage(
                session_id=chat_session.id,
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                message_text="Test message for validation",
                sender_type="user",
                role="user",
                is_code=False,
                tokens=10
            )
            db.add(chat_message)
            db.commit()
            db.refresh(chat_message)
            
            # Test relationship
            if chat_message.session.user_id == test_user.id:
                result.pass_test("ChatMessage Model - Create & Relationship")
            else:
                result.fail_test("ChatMessage Model - Create & Relationship", "Session relationship failed")
                
        except Exception as e:
            result.fail_test("ChatMessage Model - Create & Relationship", str(e))
        
        # Test 6: ContextCard Model
        try:
            context_card = ContextCard(
                user_id=test_user.id,
                session_id=chat_session.id,
                title="Test Context Card",
                description="Test context card for validation",
                content="This is test content for validation",
                source="chat",
                tokens=20,
                is_active=True
            )
            db.add(context_card)
            db.commit()
            db.refresh(context_card)
            
            result.pass_test("ContextCard Model - Create")
            
        except Exception as e:
            result.fail_test("ContextCard Model - Create", str(e))
        
        # Test 7: IdeaItem Model
        try:
            idea_item = IdeaItem(
                user_id=test_user.id,
                title="Test Idea",
                description="Test idea for validation",
                complexity="M",
                status="pending",
                is_active=True
            )
            db.add(idea_item)
            db.commit()
            db.refresh(idea_item)
            
            result.pass_test("IdeaItem Model - Create")
            
        except Exception as e:
            result.fail_test("IdeaItem Model - Create", str(e))
        
        # Test 8: FileItem Model
        try:
            file_item = FileItem(
                repository_id=test_repo.id,
                name="test.py",
                path="src/test.py",
                file_type="INTERNAL",
                category="Source Code",
                tokens=100,
                is_directory=False,
                content="# Test file content",
                content_size=100
            )
            db.add(file_item)
            db.commit()
            db.refresh(file_item)
            
            result.pass_test("FileItem Model - Create")
            
        except Exception as e:
            result.fail_test("FileItem Model - Create", str(e))
        
        # Test 9: FileAnalysis Model
        try:
            file_analysis = FileAnalysis(
                repository_id=test_repo.id,
                raw_data='{"files": ["test.py"]}',
                processed_data='{"analysis": "complete"}',
                total_files=1,
                total_tokens=100,
                max_file_size=1000,
                status="completed",
                processed_at=utc_now()
            )
            db.add(file_analysis)
            db.commit()
            db.refresh(file_analysis)
            
            result.pass_test("FileAnalysis Model - Create")
            
        except Exception as e:
            result.fail_test("FileAnalysis Model - Create", str(e))
        
        # Test 10: UserIssue Model
        try:
            user_issue = UserIssue(
                user_id=test_user.id,
                issue_id=f"issue_{uuid.uuid4().hex[:8]}",
                issue_text_raw="Test issue for validation",
                title="Test Issue",
                description="Test issue description",
                session_id=chat_session.session_id,
                chat_session_id=chat_session.id,
                priority="medium",
                status="pending",
                tokens_used=0
            )
            db.add(user_issue)
            db.commit()
            db.refresh(user_issue)
            
            result.pass_test("UserIssue Model - Create")
            
        except Exception as e:
            result.fail_test("UserIssue Model - Create", str(e))
        
        # Test 11: FileEmbedding Model
        try:
            file_embedding = FileEmbedding(
                session_id=chat_session.id,
                repository_id=test_repo.id,
                file_path="src/test.py",
                file_name="test.py",
                file_type="python",
                chunk_index=0,
                chunk_text="# Test file content",
                tokens=10,
                file_metadata={"size": 100, "encoding": "utf-8"}
            )
            db.add(file_embedding)
            db.commit()
            db.refresh(file_embedding)
            
            result.pass_test("FileEmbedding Model - Create")
            
        except Exception as e:
            result.fail_test("FileEmbedding Model - Create", str(e))
        
        # Test 12: Foreign Key Constraints
        try:
            # Try to create a record with invalid foreign key
            invalid_token = AuthToken(
                user_id=99999,  # Non-existent user ID
                access_token="invalid_token",
                token_type="bearer"
            )
            db.add(invalid_token)
            db.commit()
            
            # If we reach here, foreign key constraint didn't work
            result.fail_test("Foreign Key Constraints", "Invalid foreign key was allowed")
            
        except Exception:
            # This should fail due to foreign key constraint
            db.rollback()
            result.pass_test("Foreign Key Constraints - Validation")
        
        # Cleanup test data
        try:
            db.query(FileEmbedding).filter(FileEmbedding.session_id == chat_session.id).delete()
            db.query(UserIssue).filter(UserIssue.user_id == test_user.id).delete()
            db.query(FileAnalysis).filter(FileAnalysis.repository_id == test_repo.id).delete()
            db.query(FileItem).filter(FileItem.repository_id == test_repo.id).delete()
            db.query(IdeaItem).filter(IdeaItem.user_id == test_user.id).delete()
            db.query(ContextCard).filter(ContextCard.user_id == test_user.id).delete()
            db.query(ChatMessage).filter(ChatMessage.session_id == chat_session.id).delete()
            db.query(ChatSession).filter(ChatSession.id == chat_session.id).delete()
            db.query(Repository).filter(Repository.id == test_repo.id).delete()
            db.query(AuthToken).filter(AuthToken.user_id == test_user.id).delete()
            db.query(User).filter(User.id == test_user.id).delete()
            db.commit()
            
            result.pass_test("Test Data Cleanup")
            
        except Exception as e:
            result.fail_test("Test Data Cleanup", str(e))
        
        db.close()
        
    except Exception as e:
        result.fail_test("Database Models Setup", str(e))
        traceback.print_exc()

def test_pydantic_models():
    """Test Pydantic request/response models for validation"""
    result.section("PYDANTIC MODELS VALIDATION")
    
    try:
        from models import ChatMessageInput, ChatRequest, ContextCardInput
        
        # Test 1: ChatMessageInput validation
        try:
            valid_message = ChatMessageInput(content="Test message", is_code=False)
            if valid_message.content == "Test message":
                result.pass_test("ChatMessageInput - Valid Data")
            else:
                result.fail_test("ChatMessageInput - Valid Data", "Data validation failed")
        except Exception as e:
            result.fail_test("ChatMessageInput - Valid Data", str(e))
        
        # Test 2: ChatMessageInput validation with invalid data
        try:
            invalid_message = ChatMessageInput(content="", is_code=False)
            result.fail_test("ChatMessageInput - Invalid Data", "Empty content was allowed")
        except Exception:
            # This should fail validation
            result.pass_test("ChatMessageInput - Invalid Data Rejection")
        
        # Test 3: ContextCardInput validation
        try:
            valid_card = ContextCardInput(
                title="Test Card",
                description="Test description",
                content="Test content",
                source="chat"
            )
            result.pass_test("ContextCardInput - Valid Data")
        except Exception as e:
            result.fail_test("ContextCardInput - Valid Data", str(e))
        
        # Test 4: Complex request model
        try:
            chat_request = ChatRequest(
                session_id="test_session",
                message=ChatMessageInput(content="Test message", is_code=False),
                context_cards=["card1", "card2"],
                repo_owner="test_user",
                repo_name="test_repo"
            )
            result.pass_test("ChatRequest - Complex Model")
        except Exception as e:
            result.fail_test("ChatRequest - Complex Model", str(e))
        
    except Exception as e:
        result.fail_test("Pydantic Models Setup", str(e))

def test_model_relationships():
    """Test SQLAlchemy model relationships and cascades"""
    result.section("MODEL RELATIONSHIPS VALIDATION")
    
    try:
        from db.database import SessionLocal
        from models import ChatMessage, ChatSession, Repository, User

        from utils import utc_now
        
        db = SessionLocal()
        
        # Create test data with relationships
        test_user = User(
            github_username="relationship_test_user",
            github_user_id="rel_test_12345",
            email="rel_test@validation.com"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        # Test User -> Repository relationship
        test_repo = Repository(
            github_repo_id=111111,
            user_id=test_user.id,
            name="relationship-test",
            owner="relationship_test_user",
            full_name="relationship_test_user/relationship-test",
            html_url="https://github.com/relationship_test_user/relationship-test",
            clone_url="https://github.com/relationship_test_user/relationship-test.git"
        )
        db.add(test_repo)
        db.commit()
        db.refresh(test_repo)
        
        # Test User -> ChatSession relationship
        test_session = ChatSession(
            user_id=test_user.id,
            session_id="relationship_test_session",
            title="Relationship Test Session",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            last_activity=utc_now()
        )
        db.add(test_session)
        db.commit()
        db.refresh(test_session)
        
        # Test ChatSession -> ChatMessage relationship
        test_message = ChatMessage(
            session_id=test_session.id,
            message_id="rel_test_msg",
            message_text="Test relationship message",
            sender_type="user",
            role="user",
            tokens=5
        )
        db.add(test_message)
        db.commit()
        db.refresh(test_message)
        
        # Test forward relationships
        if test_repo.user.id == test_user.id:
            result.pass_test("Repository -> User Relationship")
        else:
            result.fail_test("Repository -> User Relationship", "Forward relationship failed")
        
        # Test backward relationships
        if len(test_user.repositories) > 0 and test_user.repositories[0].id == test_repo.id:
            result.pass_test("User -> Repository Relationship")
        else:
            result.fail_test("User -> Repository Relationship", "Backward relationship failed")
        
        # Test nested relationships
        if test_message.session.user.id == test_user.id:
            result.pass_test("ChatMessage -> Session -> User Relationship")
        else:
            result.fail_test("ChatMessage -> Session -> User Relationship", "Nested relationship failed")
        
        # Test cascade delete (clean up)
        db.delete(test_user)  # Should cascade to related objects
        db.commit()
        
        # Verify cascade worked
        remaining_repo = db.query(Repository).filter(Repository.id == test_repo.id).first()
        remaining_session = db.query(ChatSession).filter(ChatSession.id == test_session.id).first()
        remaining_message = db.query(ChatMessage).filter(ChatMessage.id == test_message.id).first()
        
        if not remaining_repo and not remaining_session and not remaining_message:
            result.pass_test("Cascade Delete - User Deletion")
        else:
            result.fail_test("Cascade Delete - User Deletion", "Cascade delete failed")
        
        db.close()
        
    except Exception as e:
        result.fail_test("Model Relationships Setup", str(e))
        traceback.print_exc()

def test_api_integration():
    """Test basic API endpoint integration with database models"""
    result.section("API INTEGRATION VALIDATION")
    
    try:
        from fastapi.testclient import TestClient
        from run_server import app
        
        # Create test client
        client = TestClient(app)
        
        # Test 1: Health check endpoint
        try:
            response = client.get("/health")
            if response.status_code == 200 and response.json().get("status") == "healthy":
                result.pass_test("Health Check Endpoint")
            else:
                result.fail_test("Health Check Endpoint", f"Status: {response.status_code}")
        except Exception as e:
            result.fail_test("Health Check Endpoint", str(e))
        
        # Test 2: Root endpoint
        try:
            response = client.get("/")
            if response.status_code == 200 and "YudaiV3 Backend API" in response.json().get("message", ""):
                result.pass_test("Root API Endpoint")
            else:
                result.fail_test("Root API Endpoint", f"Status: {response.status_code}")
        except Exception as e:
            result.fail_test("Root API Endpoint", str(e))
        
        # Test 3: Auth endpoints accessibility
        try:
            response = client.get("/auth/api/login")
            # Should return login URL or error (not 404)
            if response.status_code in [200, 400, 500]:  # Any valid response
                result.pass_test("Auth Endpoints Accessible")
            else:
                result.fail_test("Auth Endpoints Accessible", f"Status: {response.status_code}")
        except Exception as e:
            result.fail_test("Auth Endpoints Accessible", str(e))
        
        # Test 4: GitHub endpoints accessibility
        try:
            response = client.get("/github/repositories")
            # Should require authentication (401) or return data
            if response.status_code in [200, 401]:
                result.pass_test("GitHub Endpoints Accessible")
            else:
                result.fail_test("GitHub Endpoints Accessible", f"Status: {response.status_code}")
        except Exception as e:
            result.fail_test("GitHub Endpoints Accessible", str(e))
        
    except Exception as e:
        result.fail_test("API Integration Setup", str(e))

def test_data_consistency():
    """Test data consistency across models and API responses"""
    result.section("DATA CONSISTENCY VALIDATION")
    
    try:
        from db.database import SessionLocal
        from models import ChatSession, SessionResponse, User

        from utils import utc_now
        
        db = SessionLocal()
        
        # Create test user
        test_user = User(
            github_username="consistency_test_user",
            github_user_id="cons_test_12345",
            email="cons_test@validation.com"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        # Create session
        test_session = ChatSession(
            user_id=test_user.id,
            session_id="consistency_test_session",
            title="Consistency Test",
            description="Test session for data consistency",
            repo_owner="test_owner",
            repo_name="test_repo",
            repo_branch="main",
            is_active=True,
            total_messages=5,
            total_tokens=100,
            last_activity=utc_now()
        )
        db.add(test_session)
        db.commit()
        db.refresh(test_session)
        
        # Test SessionResponse model validation
        try:
            session_response = SessionResponse.model_validate(test_session)
            
            # Verify data consistency
            if (session_response.session_id == test_session.session_id and
                session_response.title == test_session.title and
                session_response.total_messages == test_session.total_messages):
                result.pass_test("SessionResponse - Data Consistency")
            else:
                result.fail_test("SessionResponse - Data Consistency", "Data mismatch")
                
        except Exception as e:
            result.fail_test("SessionResponse - Data Consistency", str(e))
        
        # Cleanup
        db.delete(test_session)
        db.delete(test_user)
        db.commit()
        db.close()
        
    except Exception as e:
        result.fail_test("Data Consistency Setup", str(e))

def main():
    """Main validation function"""
    print(f"{Colors.BOLD}{Colors.PURPLE}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    YUDAI V3 DATABASE                     ║")
    print("║               VALIDATION & TEST SCRIPT                   ║")  
    print("║                                                          ║")
    print("║  🔍 Testing SQLAlchemy Models & API Integration          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    result.info("Starting YudaiV3 database validation...")
    
    # Setup test environment
    if not setup_test_environment():
        result.summary()
        return False
    
    # Run all validation tests
    test_database_models()
    test_pydantic_models() 
    test_model_relationships()
    test_api_integration()
    test_data_consistency()
    
    # Generate final report
    success = result.summary()
    
    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 DATABASE VALIDATION COMPLETED SUCCESSFULLY!{Colors.END}")
        print(f"{Colors.GREEN}✅ All models and APIs are working correctly{Colors.END}")
        print(f"{Colors.GREEN}✅ Ready for production deployment{Colors.END}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}💥 DATABASE VALIDATION FAILED!{Colors.END}")
        print(f"{Colors.RED}❌ Please fix the issues before deployment{Colors.END}")
        print(f"{Colors.RED}❌ Check the error details above{Colors.END}\n")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)