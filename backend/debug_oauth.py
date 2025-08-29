#!/usr/bin/env python3
"""
Debug script for GitHub OAuth configuration
Run this to check your OAuth setup
"""

import os

from auth.github_oauth import get_github_oauth_url, validate_github_config


def debug_oauth_config():
    """Debug the current OAuth configuration"""
    print("🔍 GitHub OAuth Configuration Debug")
    print("=" * 50)

    # Check environment variables
    print("\n📋 Environment Variables:")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI")
    frontend_url = os.getenv("FRONTEND_BASE_URL")

    print(f"CLIENT_ID: {'✅ Set' if client_id else '❌ Not set'}")
    print(f"CLIENT_SECRET: {'✅ Set' if client_secret else '❌ Not set'}")
    print(f"GITHUB_REDIRECT_URI: {redirect_uri or '❌ Not set (using default)'}")
    print(f"FRONTEND_BASE_URL: {frontend_url or '❌ Not set (using default)'}")

    if client_id:
        print(f"Client ID (first 8 chars): {client_id[:8]}...")

    # Test OAuth URL generation
    print("\n🔗 OAuth URL Generation:")
    try:
        validate_github_config()
        oauth_url = get_github_oauth_url()
        print("✅ OAuth URL generated successfully")
        print(f"URL: {oauth_url}")

        # Extract and display key components
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(oauth_url)
        params = parse_qs(parsed.query)

        print(f"Client ID in URL: {params.get('client_id', ['❌ Missing'])[0][:8]}...")
        print(f"Redirect URI in URL: {params.get('redirect_uri', ['❌ Missing'])[0]}")
        print(f"Scope in URL: {params.get('scope', ['❌ Missing'])[0]}")

    except Exception as e:
        print(f"❌ OAuth URL generation failed: {e}")

    # Provide recommendations
    print("\n💡 Recommendations:")
    if not redirect_uri:
        print("⚠️  GITHUB_REDIRECT_URI not set - ensure it matches your GitHub OAuth app exactly")
    if not client_id or not client_secret:
        print("⚠️  GitHub OAuth credentials not configured")

    print("\n🔧 To fix redirect URI issues:")
    print("1. Go to your GitHub OAuth app settings")
    print("2. Ensure 'Authorization callback URL' matches exactly:")
    print(f"   Expected: {redirect_uri or 'https://yudai.app/auth/callback'}")
    print("3. Make sure there are no trailing slashes or protocol mismatches")

if __name__ == "__main__":
    debug_oauth_config()
