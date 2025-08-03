#!/usr/bin/env python3
"""
Test script for GitHub App authentication

This script tests the GitHub App authentication setup without requiring
a full server setup.
"""

import asyncio
import os
import sys
from pathlib import Path

from auth.github_oauth import (
    GitHubAppError,
    generate_jwt,
    generate_oauth_state,
    get_github_app_oauth_url,
    validate_github_app_config,
)

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


try:
    from dotenv import load_dotenv
    
    # Try to load .env from multiple locations
    env_files = [
        backend_dir / ".env",
        backend_dir.parent / ".env",
        backend_dir / ".env.local",
        backend_dir.parent / ".env.local",
    ]
    
    loaded = False
    for env_file in env_files:
        if env_file.exists():
            print(f"📁 Loading environment from: {env_file}")
            load_dotenv(env_file)
            loaded = True
            break
    
    if not loaded:
        print("⚠️  No .env file found. Make sure you have created one with the required variables.")
        
except ImportError:
    print("⚠️  python-dotenv not installed. Install it with: pip install python-dotenv")


def test_configuration():
    """Test that all required configuration is present"""
    print("🔧 Testing GitHub App configuration...")
    
    try:
        validate_github_app_config()
        print("✅ Configuration validation passed")
        return True
    except GitHubAppError as e:
        print(f"❌ Configuration validation failed: {e}")
        return False


def test_jwt_generation():
    """Test JWT generation"""
    print("\n🔐 Testing JWT generation...")
    
    try:
        jwt_token = generate_jwt()
        print(f"✅ JWT generated successfully: {jwt_token[:50]}...")
        return True
    except GitHubAppError as e:
        print(f"❌ JWT generation failed: {e}")
        return False


def test_oauth_url_generation():
    """Test OAuth URL generation"""
    print("\n🔗 Testing OAuth URL generation...")
    
    try:
        state = generate_oauth_state()
        oauth_url = get_github_app_oauth_url(state)
        print(f"✅ OAuth URL generated: {oauth_url}")
        return True
    except GitHubAppError as e:
        print(f"❌ OAuth URL generation failed: {e}")
        return False


def test_environment_variables():
    """Test that all required environment variables are set"""
    print("\n🌍 Testing environment variables...")
    
    required_vars = [
        "GITHUB_APP_ID",
        "GITHUB_APP_CLIENT_ID", 
        "GITHUB_APP_CLIENT_SECRET",
        "GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_PRIVATE_KEY_PATH"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * len(value)} (hidden)")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("\n✅ All environment variables are set")
        return True


def test_private_key_file():
    """Test that the private key file exists"""
    print("\n🔑 Testing private key file...")
    
    key_path = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "private-key.pem")
    
    if os.path.exists(key_path):
        print(f"✅ Private key file exists: {key_path}")
        
        # Check if it's readable
        try:
            with open(key_path, 'r') as f:
                content = f.read()
                if content.startswith('-----BEGIN RSA PRIVATE KEY-----'):
                    print("✅ Private key file format appears correct")
                    return True
                else:
                    print("❌ Private key file format appears incorrect")
                    return False
        except Exception as e:
            print(f"❌ Cannot read private key file: {e}")
            return False
    else:
        print(f"❌ Private key file not found: {key_path}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Starting GitHub App authentication tests...\n")
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Private Key File", test_private_key_file),
        ("Configuration Validation", test_configuration),
        ("JWT Generation", test_jwt_generation),
        ("OAuth URL Generation", test_oauth_url_generation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! GitHub App authentication is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 