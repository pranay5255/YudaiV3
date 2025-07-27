#!/bin/bash

# GoDaddy DNS Verification Script
# This script helps verify that your GoDaddy DNS is properly configured

set -e

echo "🔍 Verifying GoDaddy DNS Configuration..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Get Vultr server IP from user
echo -n "Enter your Vultr server IP address: "
read VULTR_IP

if [ -z "$VULTR_IP" ]; then
    print_error "Vultr IP address is required"
    exit 1
fi

print_status "Testing DNS resolution for yudai.app..."

# Test root domain
print_info "Testing root domain (yudai.app)..."
ROOT_RESULT=$(nslookup yudai.app 2>/dev/null | grep -A 1 "Name:" | tail -1 | awk '{print $2}')

if [ "$ROOT_RESULT" = "$VULTR_IP" ]; then
    print_status "✅ Root domain (yudai.app) is correctly pointing to $VULTR_IP"
else
    print_error "❌ Root domain (yudai.app) is pointing to $ROOT_RESULT, should be $VULTR_IP"
fi

# Test www subdomain
print_info "Testing www subdomain (www.yudai.app)..."
WWW_RESULT=$(nslookup www.yudai.app 2>/dev/null | grep -A 1 "Name:" | tail -1 | awk '{print $2}')

if [ "$WWW_RESULT" = "$VULTR_IP" ]; then
    print_status "✅ WWW subdomain (www.yudai.app) is correctly pointing to $VULTR_IP"
else
    print_error "❌ WWW subdomain (www.yudai.app) is pointing to $WWW_RESULT, should be $VULTR_IP"
fi

# Test API subdomain
print_info "Testing API subdomain (api.yudai.app)..."
API_RESULT=$(nslookup api.yudai.app 2>/dev/null | grep -A 1 "Name:" | tail -1 | awk '{print $2}')

if [ "$API_RESULT" = "$VULTR_IP" ] || [ "$API_RESULT" = "yudai.app." ]; then
    print_status "✅ API subdomain (api.yudai.app) is correctly configured"
else
    print_warning "⚠️  API subdomain (api.yudai.app) is pointing to $API_RESULT"
fi

# Test wildcard subdomain
print_info "Testing wildcard subdomain (test.yudai.app)..."
WILDCARD_RESULT=$(nslookup test.yudai.app 2>/dev/null | grep -A 1 "Name:" | tail -1 | awk '{print $2}')

if [ "$WILDCARD_RESULT" = "$VULTR_IP" ]; then
    print_status "✅ Wildcard subdomain (*.yudai.app) is correctly pointing to $VULTR_IP"
else
    print_warning "⚠️  Wildcard subdomain (*.yudai.app) is pointing to $WILDCARD_RESULT"
fi

# Test HTTP connectivity
print_info "Testing HTTP connectivity..."
if curl -s -o /dev/null -w "%{http_code}" http://yudai.app | grep -q "200\|301\|302"; then
    print_status "✅ HTTP connectivity to yudai.app is working"
else
    print_warning "⚠️  HTTP connectivity to yudai.app is not working"
fi

# Test HTTPS connectivity
print_info "Testing HTTPS connectivity..."
if curl -s -o /dev/null -w "%{http_code}" https://yudai.app | grep -q "200\|301\|302"; then
    print_status "✅ HTTPS connectivity to yudai.app is working"
else
    print_warning "⚠️  HTTPS connectivity to yudai.app is not working"
fi

# Check for common GoDaddy parking page IPs
print_info "Checking for GoDaddy parking page..."
if echo "$ROOT_RESULT" | grep -q "50.63.202\|50.63.203\|50.63.204"; then
    print_error "❌ Domain is still pointing to GoDaddy parking page!"
    print_error "Please update your GoDaddy DNS records to point to $VULTR_IP"
fi

# Summary
echo ""
print_info "=== DNS Verification Summary ==="
echo "Vultr Server IP: $VULTR_IP"
echo "Root Domain: $ROOT_RESULT"
echo "WWW Subdomain: $WWW_RESULT"
echo "API Subdomain: $API_RESULT"
echo "Wildcard Subdomain: $WILDCARD_RESULT"

echo ""
print_info "=== Next Steps ==="
if [ "$ROOT_RESULT" = "$VULTR_IP" ] && [ "$WWW_RESULT" = "$VULTR_IP" ]; then
    print_status "✅ DNS is properly configured! You can proceed with SSL certificate setup."
    print_info "Run: sudo certbot certonly --standalone -d yudai.app -d www.yudai.app"
else
    print_error "❌ DNS needs to be updated in GoDaddy dashboard."
    print_info "Please follow the GoDaddy DNS setup guide and update your records."
    print_info "Then run this script again to verify."
fi

echo ""
print_info "=== Troubleshooting Tips ==="
echo "1. DNS changes can take 5-30 minutes to propagate locally"
echo "2. Global propagation can take 24-48 hours"
echo "3. Use online tools like whatsmydns.net to check global propagation"
echo "4. Clear your browser cache and DNS cache if testing locally"
echo "5. Try testing from different networks/locations"