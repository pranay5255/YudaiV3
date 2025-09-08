#!/bin/bash
# Production Debugging Script for YudaiV3
# This script helps diagnose issues with the production deployment

set -e

echo "🔍 YudaiV3 Production Debug Script"
echo "=================================="

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo "❌ .env.prod file not found!"
    echo "   Please create .env.prod from .env.prod.template"
    echo "   Copy .env.prod.template to .env.prod and fill in the values"
    exit 1
else
    echo "✅ .env.prod file exists"
fi

# Check required environment variables
echo ""
echo "🔍 Checking required environment variables..."

REQUIRED_VARS=(
    "GITHUB_APP_CLIENT_ID"
    "GITHUB_APP_CLIENT_SECRET"
    "GITHUB_APP_ID"
    "POSTGRES_PASSWORD"
    "SECRET_KEY"
    "JWT_SECRET"
)

MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env.prod; then
        MISSING_VARS+=("$var")
        echo "❌ $var is missing from .env.prod"
    else
        echo "✅ $var is set"
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo ""
    echo "❌ Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Please add these variables to .env.prod"
    exit 1
fi

echo ""
echo "✅ All required environment variables are set"

# Check GitHub App private key
GITHUB_KEY_PATH=$(grep "^GITHUB_APP_PRIVATE_KEY_PATH=" .env.prod | cut -d'=' -f2)
if [ -n "$GITHUB_KEY_PATH" ] && [ "$GITHUB_KEY_PATH" != "/app/yudaiv3.2025-09-07.private-key.pem" ]; then
    echo ""
    echo "⚠️  Custom GitHub private key path detected: $GITHUB_KEY_PATH"
    if [ ! -f "$GITHUB_KEY_PATH" ]; then
        echo "❌ GitHub private key file not found at: $GITHUB_KEY_PATH"
        exit 1
    else
        echo "✅ GitHub private key file exists"
    fi
fi

echo ""
echo "🎉 Pre-flight checks passed!"
echo ""
echo "Next steps:"
echo "1. Ensure GitHub App is configured with correct callback URL: https://yudai.app/auth/callback"
echo "2. Run: docker-compose -f docker-compose.prod.yml up -d"
echo "3. Check logs: docker-compose -f docker-compose.prod.yml logs -f backend"
echo "4. Test login: curl -X GET 'https://yudai.app/auth/api/login'"
