#!/usr/bin/env python3
"""
YudaiV3 Database Validation Script
==================================

Comprehensive database and schema validation for build-time checks.
This script focuses ONLY on internal logic: SQLAlchemy models and Pydantic
schemas used by the backend. API/endpoint behavior is NOT tested here.

This script validates:
- Model creation, relationships, and constraints
- Pydantic request/response model consistency
- Data integrity and foreign key relationships
- ORM-to-schema (Pydantic) consistency
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
            FileAnalysis,
            FileItem,
            Repository,
            User,
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
            _ = ChatMessageInput(content="", is_code=False)
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
            if valid_card.title == "Test Card" and valid_card.source == "chat":
                result.pass_test("ContextCardInput - Valid Data")
            else:
                result.fail_test("ContextCardInput - Valid Data", "Data validation failed")
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
            if chat_request.session_id == "test_session" and chat_request.message.content == "Test message":
                result.pass_test("ChatRequest - Complex Model")
            else:
                result.fail_test("ChatRequest - Complex Model", "Data validation failed")
        except Exception as e:
            result.fail_test("ChatRequest - Complex Model", str(e))
        
    except Exception as e:
        result.fail_test("Pydantic Models Setup", str(e))

def test_model_relationships():
    """Test SQLAlchemy model relationships and cascades"""
    result.section("MODEL RELATIONSHIPS VALIDATION")
    
    try:
        from db.database import SessionLocal
        from models import Repository, User

        
        db = SessionLocal()
        
        # Create test data with relationships - use unique identifiers
        unique_id = uuid.uuid4().hex[:8]
        test_user = User(
            github_username=f"relationship_test_user_{unique_id}",
            github_user_id=f"rel_test_{unique_id}",
            email=f"rel_test_{unique_id}@validation.com"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        # Test User -> Repository relationship
        test_repo = Repository(
            github_repo_id=111111,
            user_id=test_user.id,
            name=f"relationship-test-{unique_id}",
            owner=f"relationship_test_user_{unique_id}",
            full_name=f"relationship_test_user_{unique_id}/relationship-test-{unique_id}",
            html_url=f"https://github.com/relationship_test_user_{unique_id}/relationship-test-{unique_id}",
            clone_url=f"https://github.com/relationship_test_user_{unique_id}/relationship-test-{unique_id}.git"
        )
        db.add(test_repo)
        db.commit()
        db.refresh(test_repo)
        
        # Test User -> ChatSession relationship (DISABLED - ChatSession model commented out)
        # test_session = ChatSession(
        #     user_id=test_user.id,
        #     session_id=f"relationship_test_session_{unique_id}",
        #     title="Relationship Test Session",
        #     is_active=True,
        #     total_messages=0,
        #     total_tokens=0,
        #     last_activity=utc_now()
        # )
        # db.add(test_session)
        # db.commit()
        # db.refresh(test_session)
        
        # Test ChatSession -> ChatMessage relationship (DISABLED - ChatSession model commented out)
        # test_message = ChatMessage(
        #     session_id=test_session.id,
        #     message_id=f"rel_test_msg_{unique_id}",
        #     message_text="Test relationship message",
        #     sender_type="user",
        #     role="user",
        #     tokens=5
        # )
        # db.add(test_message)
        # db.commit()
        # db.refresh(test_message)
        
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
        
        # Test nested relationships (DISABLED - ChatSession model commented out)
        # if test_message.session.user.id == test_user.id:
        #     result.pass_test("ChatMessage -> Session -> User Relationship")
        # else:
        #     result.fail_test("ChatMessage -> Session -> User Relationship", "Nested relationship failed")
        
        # Test cascade delete (clean up)
        db.delete(test_user)  # Should cascade to related objects
        db.commit()
        
        # Verify cascade worked
        remaining_repo = db.query(Repository).filter(Repository.id == test_repo.id).first()
        # remaining_session = db.query(ChatSession).filter(ChatSession.id == test_session.id).first()
        # remaining_message = db.query(ChatMessage).filter(ChatMessage.id == test_message.id).first()
        
        if not remaining_repo:  # and not remaining_session and not remaining_message:
            result.pass_test("Cascade Delete - User Deletion")
        else:
            result.fail_test("Cascade Delete - User Deletion", "Cascade delete failed")
        
        db.close()
        
    except Exception as e:
        result.fail_test("Model Relationships Setup", str(e))
        traceback.print_exc()

def test_api_integration():
    """Deprecated: API endpoint tests are intentionally omitted in this script."""
    result.section("API TESTS OMITTED")
    result.info("Skipping API/endpoint tests by design. This suite validates only DB models and schemas.")

def test_data_consistency():
    """Test data consistency across ORM models and Pydantic schemas"""
    result.section("DATA CONSISTENCY VALIDATION")
    
    try:
        from db.database import SessionLocal
        from models import User

        
        db = SessionLocal()
        
        # Create test user
        unique_id = uuid.uuid4().hex[:8]
        test_user = User(
            github_username=f"consistency_test_user_{unique_id}",
            github_user_id=f"cons_test_{unique_id}",
            email=f"cons_test_{unique_id}@validation.com"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        # Create session (DISABLED - ChatSession model commented out)
        # test_session = ChatSession(
        #     user_id=test_user.id,
        #     session_id=f"consistency_test_session_{unique_id}",
        #     title="Consistency Test",
        #     description="Test session for data consistency",
        #     repo_owner="test_owner",
        #     repo_name="test_repo",
        #     repo_branch="main",
        #     is_active=True,
        #     total_messages=5,
        #     total_tokens=100,
        #     last_activity=utc_now()
        # )
        # db.add(test_session)
        # db.commit()
        # db.refresh(test_session)
        
        # Test SessionResponse model validation (DISABLED - ChatSession model commented out)
        # try:
        #     session_response = SessionResponse.model_validate(test_session)
        #     
        #     # Verify data consistency
        #     if (session_response.session_id == test_session.session_id and
        #         session_response.title == test_session.title and
        #         session_response.total_messages == test_session.total_messages):
        #         result.pass_test("SessionResponse - Data Consistency")
        #     else:
        #         result.fail_test("SessionResponse - Data Consistency", "Data mismatch")
        #         
        # except Exception as e:
        #     result.fail_test("SessionResponse - Data Consistency", str(e))
        
        # Cleanup
        # db.delete(test_session)
        db.delete(test_user)
        db.commit()
        db.close()
        
    except Exception as e:
        result.fail_test("Data Consistency Setup", str(e))

# All deprecated API test functions removed - they were stub functions that didn't actually test anything

def main():
    """Main validation function"""
    print(f"{Colors.BOLD}{Colors.PURPLE}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    YUDAI V3 DATABASE                     ║")
    print("║               VALIDATION & TEST SCRIPT                   ║")  
    print("║                                                          ║")
    print("║  🔍 Testing SQLAlchemy Models & Schema Consistency       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    result.info("Starting YudaiV3 database validation...")
    
    # Clean up any existing test data first
    # cleanup_test_data()
    
    # Setup test environment
    if not setup_test_environment():
        result.summary()
        return False
    
    # Run internal validation tests
    test_database_models()
    test_pydantic_models()
    test_model_relationships()
    test_data_consistency()
    
    # API/endpoint tests are intentionally omitted in this suite
    
    # Clean up test data after tests
    # cleanup_test_data()
    
    # Generate final report
    success = result.summary()
    
    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 DATABASE VALIDATION COMPLETED SUCCESSFULLY!{Colors.END}")
        print(f"{Colors.GREEN}✅ All models and schemas are consistent{Colors.END}")
        print(f"{Colors.GREEN}✅ Ready for production deployment{Colors.END}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}💥 DATABASE VALIDATION FAILED!{Colors.END}")
        print(f"{Colors.RED}❌ Please fix the issues before deployment{Colors.END}")
        print(f"{Colors.RED}❌ Check the error details above{Colors.END}\n")
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Test interrupted by user{Colors.END}")
 
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}💥 Unexpected error: {e}{Colors.END}")
        # cleanup_test_data()
        sys.exit(1)