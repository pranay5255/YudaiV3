#!/usr/bin/env python3
"""
Test runner for YudaiV3 backend integration tests

This script sets up the test environment and runs the integration tests
for GitHub authentication and API functionality.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def setup_test_environment():
    """Set up test environment variables"""
    test_env = {
        "GITHUB_CLIENT_ID": "test_client_id",
        "GITHUB_CLIENT_SECRET": "test_client_secret", 
        "GITHUB_REDIRECT_URI": "http://localhost:3000/auth/callback",
        "OPENROUTER_API_KEY": "test_openrouter_key",
        "DATABASE_URL": "sqlite:///./test.db",
        "DB_ECHO": "false"
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    print("✓ Test environment variables set")

def cleanup_test_database():
    """Clean up test database files"""
    test_db_files = ["test.db", "test.db-journal", "test.db-wal"]
    
    for db_file in test_db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"✓ Removed {db_file}")

def run_tests(test_pattern=None, verbose=False):
    """Run the integration tests"""
    
    # Set up test environment
    setup_test_environment()
    
    # Clean up any existing test database
    cleanup_test_database()
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if test_pattern:
        cmd.extend(["-k", test_pattern])
    
    # Add test directory
    cmd.append("tests/")
    
    # Add coverage if available
    try:
        import coverage
        cmd.extend(["--cov=.", "--cov-report=term-missing"])
    except ImportError:
        print("ℹ Coverage not available (install with: pip install coverage)")
    
    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("=" * 60)
        print("✓ All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print("=" * 60)
        print(f"✗ Tests failed with exit code {e.returncode}")
        return False
    finally:
        # Clean up test database
        cleanup_test_database()

def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run YudaiV3 backend integration tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-k", "--pattern", help="Test pattern to match")
    parser.add_argument("--auth", action="store_true", help="Run only authentication tests")
    parser.add_argument("--github", action="store_true", help="Run only GitHub API tests")
    parser.add_argument("--daifu", action="store_true", help="Run only DAifu integration tests")
    parser.add_argument("--setup-only", action="store_true", help="Only set up test environment")
    
    args = parser.parse_args()
    
    if args.setup_only:
        setup_test_environment()
        print("Test environment set up. You can now run tests manually with:")
        print("python -m pytest tests/ -v")
        return
    
    # Determine test pattern
    test_pattern = args.pattern
    if args.auth:
        test_pattern = "test_github_auth"
    elif args.github:
        test_pattern = "test_github_api"
    elif args.daifu:
        test_pattern = "test_daifu"
    
    # Run tests
    success = run_tests(test_pattern, args.verbose)
    
    if success:
        print("\n🎉 All integration tests passed!")
        print("\nNext steps:")
        print("1. Set up your GitHub OAuth app")
        print("2. Configure environment variables")
        print("3. Run the backend server")
        print("4. Test the authentication flow")
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 