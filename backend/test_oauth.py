#!/usr/bin/env python3
"""
GitHub OAuth Configuration Test Script

This script helps diagnose GitHub OAuth configuration issues.
Run this script to check your OAuth setup and generate test URLs.
"""

import os
import sys

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth.github_oauth import (
    FALLBACK_REDIRECT_URIS,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_REDIRECT_URI,
    generate_oauth_state,
    get_github_oauth_url,
    validate_github_config,
)


def test_oauth_config():
    """Test GitHub OAuth configuration"""
    print("=== GitHub OAuth Configuration Test ===\n")

    # Check environment variables
    print("Environment Variables:")
    print(f"GITHUB_CLIENT_ID: {'✓ Set' if GITHUB_CLIENT_ID else '✗ Not set'}")
    print(f"GITHUB_CLIENT_SECRET: {'✓ Set' if GITHUB_CLIENT_SECRET else '✗ Not set'}")
    print(f"GITHUB_REDIRECT_URI: {GITHUB_REDIRECT_URI or 'Not set (using default)'}")
    print()

    # Check configuration
    try:
        validate_github_config()
        print("✓ Configuration validation passed")
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return False

    # Generate test URL
    try:
        state = generate_oauth_state()
        auth_url = get_github_oauth_url(state)
        print("\n✓ Generated OAuth URL successfully")
        print(f"State: {state}")
        print(f"URL: {auth_url}")
        print()

        # Show all possible redirect URIs
        print("Possible Redirect URIs (configure these in your GitHub OAuth app):")
        for i, uri in enumerate(FALLBACK_REDIRECT_URIS, 1):
            print(f"{i}. {uri}")
        print()

        return True

    except Exception as e:
        print(f"✗ Failed to generate OAuth URL: {e}")
        return False


def show_github_oauth_setup_instructions():
    """Show instructions for setting up GitHub OAuth"""
    print("=== GitHub OAuth App Setup Instructions ===\n")
    print("1. Go to GitHub Settings > Developer settings > OAuth Apps")
    print("2. Click 'New OAuth App'")
    print("3. Fill in the following details:")
    print("   - Application name: Yudai (or your preferred name)")
    print("   - Homepage URL: https://yudai.app")
    print("   - Authorization callback URL: https://yudai.app/auth/callback")
    print("4. Click 'Register application'")
    print("5. Copy the Client ID and Client Secret")
    print("6. Set the environment variables:")
    print("   export GITHUB_CLIENT_ID='your_client_id'")
    print("   export GITHUB_CLIENT_SECRET='your_client_secret'")
    print("   export GITHUB_REDIRECT_URI='https://yudai.app/auth/callback'")
    print()


if __name__ == "__main__":
    success = test_oauth_config()

    if not success:
        print("\n" + "=" * 50)
        show_github_oauth_setup_instructions()
    else:
        print("✓ OAuth configuration looks good!")
        print("\nIf you're still getting 404 errors:")
        print("1. Make sure your GitHub OAuth app is properly configured")
        print("2. Check that the redirect URI matches exactly")
        print("3. Ensure the OAuth app is not disabled")
        print("4. Try the test URL above to see if it works")
