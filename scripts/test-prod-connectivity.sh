#!/bin/bash

# Production Connectivity Test Script
# This script tests the frontend-to-backend communication in the production environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="yudai.app"
API_DOMAIN="api.yudai.app"
TIMEOUT=10

echo -e "${BLUE}🔍 Production Connectivity Test Suite${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        return 1
    fi
}

# Function to test HTTP connectivity
test_http_connectivity() {
    local url=$1
    local description=$2
    
    echo -e "${YELLOW}Testing: $description${NC}"
    echo -e "URL: $url"
    
    # Test HTTP response
    if curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url" | grep -q "200\|301\|302"; then
        print_status 0 "HTTP connectivity successful"
    else
        print_status 1 "HTTP connectivity failed"
        return 1
    fi
    
    # Test HTTPS redirect (for HTTP URLs)
    if [[ $url == http://* ]]; then
        redirect_url=$(curl -s -o /dev/null -w "%{redirect_url}" --max-time $TIMEOUT "$url")
        if [[ $redirect_url == https://* ]]; then
            print_status 0 "HTTPS redirect working"
        else
            print_status 1 "HTTPS redirect failed"
            return 1
        fi
    fi
    
    echo ""
}

# Function to test API endpoints
test_api_endpoint() {
    local base_url=$1
    local endpoint=$2
    local description=$3
    
    echo -e "${YELLOW}Testing API: $description${NC}"
    echo -e "URL: $base_url$endpoint"
    
    # Test endpoint
    response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$base_url$endpoint")
    
    if [ "$response_code" = "200" ]; then
        print_status 0 "API endpoint responding (200)"
    elif [ "$response_code" = "404" ]; then
        print_status 0 "API endpoint exists but returns 404 (expected for some endpoints)"
    elif [ "$response_code" = "401" ] || [ "$response_code" = "403" ]; then
        print_status 0 "API endpoint responding with auth required ($response_code)"
    else
        print_status 1 "API endpoint failed (HTTP $response_code)"
        return 1
    fi
    
    echo ""
}

# Function to test CORS
test_cors() {
    local url=$1
    local description=$2
    
    echo -e "${YELLOW}Testing CORS: $description${NC}"
    echo -e "URL: $url"
    
    # Test CORS preflight
    cors_response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Origin: https://$DOMAIN" \
        -H "Access-Control-Request-Method: GET" \
        -H "Access-Control-Request-Headers: Content-Type" \
        --max-time $TIMEOUT \
        -X OPTIONS "$url")
    
    if [ "$cors_response" = "204" ] || [ "$cors_response" = "200" ]; then
        print_status 0 "CORS preflight successful ($cors_response)"
    else
        print_status 1 "CORS preflight failed ($cors_response)"
        return 1
    fi
    
    echo ""
}

# Function to test SSL/TLS
test_ssl() {
    local domain=$1
    local description=$2
    
    echo -e "${YELLOW}Testing SSL/TLS: $description${NC}"
    echo -e "Domain: $domain"
    
    # Test SSL certificate
    if openssl s_client -connect "$domain:443" -servername "$domain" < /dev/null 2>/dev/null | grep -q "Verify return code: 0"; then
        print_status 0 "SSL certificate valid"
    else
        print_status 1 "SSL certificate invalid or missing"
        return 1
    fi
    
    # Test TLS version
    tls_version=$(openssl s_client -connect "$domain:443" -servername "$domain" -tls1_2 < /dev/null 2>/dev/null | grep "Protocol" | head -1)
    if echo "$tls_version" | grep -q "TLSv1.2\|TLSv1.3"; then
        print_status 0 "TLS version supported: $tls_version"
    else
        print_status 1 "TLS version not supported"
        return 1
    fi
    
    echo ""
}

# Function to test response time
test_response_time() {
    local url=$1
    local description=$2
    local max_time=2000  # 2 seconds in milliseconds
    
    echo -e "${YELLOW}Testing response time: $description${NC}"
    echo -e "URL: $url"
    
    # Get response time in milliseconds
    response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time $TIMEOUT "$url" | awk '{print $1 * 1000}')
    
    if (( $(echo "$response_time < $max_time" | bc -l) )); then
        print_status 0 "Response time acceptable (${response_time}ms)"
    else
        print_status 1 "Response time too slow (${response_time}ms > ${max_time}ms)"
        return 1
    fi
    
    echo ""
}

# Main test execution
echo -e "${BLUE}Starting connectivity tests...${NC}"
echo ""

# Test 1: Main domain frontend
test_http_connectivity "https://$DOMAIN" "Main domain frontend"

# Test 2: API subdomain
test_http_connectivity "https://$API_DOMAIN" "API subdomain"

# Test 3: HTTP to HTTPS redirect
test_http_connectivity "http://$DOMAIN" "HTTP to HTTPS redirect"

# Test 4: API endpoints via main domain proxy
test_api_endpoint "https://$DOMAIN" "/api/health" "Health check via main domain proxy"
test_api_endpoint "https://$DOMAIN" "/api/docs" "API docs via main domain proxy"

# Test 5: API endpoints via API subdomain
test_api_endpoint "https://$API_DOMAIN" "/health" "Health check via API subdomain"
test_api_endpoint "https://$API_DOMAIN" "/docs" "API docs via API subdomain"

# Test 6: CORS testing
test_cors "https://$DOMAIN/api/health" "CORS via main domain proxy"
test_cors "https://$API_DOMAIN/health" "CORS via API subdomain"

# Test 7: SSL/TLS testing
test_ssl "$DOMAIN" "Main domain SSL/TLS"
test_ssl "$API_DOMAIN" "API subdomain SSL/TLS"

# Test 8: Response time testing
test_response_time "https://$DOMAIN" "Main domain response time"
test_response_time "https://$API_DOMAIN/health" "API subdomain response time"

# Test 9: Load testing (simple)
echo -e "${YELLOW}Testing concurrent requests...${NC}"
echo -e "URL: https://$API_DOMAIN/health"

# Make 5 concurrent requests
for i in {1..5}; do
    (curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "https://$API_DOMAIN/health" > /tmp/curl_$i) &
done

# Wait for all requests to complete
wait

# Check results
all_success=true
for i in {1..5}; do
    if [ -f "/tmp/curl_$i" ]; then
        response_code=$(cat /tmp/curl_$i)
        rm /tmp/curl_$i
        if [ "$response_code" = "200" ]; then
            echo -e "${GREEN}✅ Concurrent request $i: OK (200)${NC}"
        else
            echo -e "${RED}❌ Concurrent request $i: Failed ($response_code)${NC}"
            all_success=false
        fi
    fi
done

if $all_success; then
    print_status 0 "Concurrent requests successful"
else
    print_status 1 "Some concurrent requests failed"
fi

echo ""

# Summary
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}🎉 Production Connectivity Test Complete${NC}"
echo -e "${BLUE}=====================================${NC}"

# Check if all tests passed
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All connectivity tests passed!${NC}"
    echo -e "${GREEN}Your frontend-to-backend communication is working correctly.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some connectivity tests failed.${NC}"
    echo -e "${YELLOW}Please check your nginx configuration and backend service.${NC}"
    exit 1
fi 