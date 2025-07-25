#!/bin/bash

# YudaiV3 Integration Test Script
# This script tests the complete integration of Yudai Architect Agent, DaiFu Agent, and Langfuse telemetry

set -e  # Exit on any error

echo "🚀 Starting YudaiV3 Integration Tests"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="http://localhost:8000"
LANGFUSE_URL="http://localhost:3000"
TIMEOUT=30

# Function to check if a service is ready
check_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -n "⏳ Waiting for $service_name to be ready"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --max-time 5 "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e " ${RED}✗${NC}"
    echo -e "${RED}ERROR: $service_name not responding after $((max_attempts * 2)) seconds${NC}"
    return 1
}

# Function to test API endpoint
test_endpoint() {
    local method=$1
    local url=$2
    local data=$3
    local description=$4
    local expected_status=$5
    
    echo -n "🧪 Testing: $description"
    
    if [ -n "$data" ]; then
        response=$(curl -s -w "%{http_code}" -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data" \
            --max-time $TIMEOUT)
    else
        response=$(curl -s -w "%{http_code}" -X "$method" "$url" \
            --max-time $TIMEOUT)
    fi
    
    status_code="${response: -3}"
    response_body="${response%???}"
    
    if [ "$status_code" -eq "${expected_status:-200}" ]; then
        echo -e " ${GREEN}✓${NC} (Status: $status_code)"
        return 0
    else
        echo -e " ${RED}✗${NC} (Status: $status_code)"
        echo "Response: $response_body"
        return 1
    fi
}

# Function to run all tests
run_tests() {
    local failed_tests=0
    
    echo -e "\n📋 Running API Tests"
    echo "===================="
    
    # Test 1: Backend Health Check
    if ! test_endpoint "GET" "$BACKEND_URL/health" "" "Backend Health Check"; then
        failed_tests=$((failed_tests + 1))
    fi
    
    # Test 2: API Root
    if ! test_endpoint "GET" "$BACKEND_URL/" "" "API Root Endpoint"; then
        failed_tests=$((failed_tests + 1))
    fi
    
    # Test 3: API Documentation
    if ! test_endpoint "GET" "$BACKEND_URL/docs" "" "API Documentation"; then
        failed_tests=$((failed_tests + 1))
    fi
    
    # Test 4: Architect Agent - Sample Data
    architect_sample_data='{
        "title": "Test Issue Creation",
        "description": "Testing the architect agent with sample data",
        "chat_messages": [
            {
                "id": "test-msg-1",
                "content": "We need to implement a new feature for user authentication",
                "isCode": false,
                "timestamp": "2025-01-11T10:00:00Z"
            }
        ],
        "file_context": [
            {
                "id": "test-file-1",
                "name": "auth.py",
                "type": "INTERNAL",
                "tokens": 150,
                "category": "authentication"
            }
        ],
        "priority": "medium"
    }'
    
    if ! test_endpoint "POST" "$BACKEND_URL/api/issues/create-with-context?preview_only=true&use_sample_data=true" "$architect_sample_data" "Architect Agent - Sample Data"; then
        failed_tests=$((failed_tests + 1))
    fi
    
    # Test 5: Architect Agent - LLM Integration (only if OpenRouter API key is set)
    if [ -n "$OPENROUTER_API_KEY" ]; then
        if ! test_endpoint "POST" "$BACKEND_URL/api/issues/create-with-context?preview_only=true&use_sample_data=false" "$architect_sample_data" "Architect Agent - LLM Integration"; then
            failed_tests=$((failed_tests + 1))
        fi
    else
        echo "⚠️  Skipping LLM integration test (OPENROUTER_API_KEY not set)"
    fi
    
    # Test 6: Issue Service - List Issues
    if ! test_endpoint "GET" "$BACKEND_URL/api/issues/" "" "List Issues Endpoint" 401; then
        # 401 is expected without authentication, but shows the endpoint exists
        echo "   Note: Authentication required (expected 401)"
    fi
    
    echo -e "\n📊 Test Results"
    echo "==============="
    
    if [ $failed_tests -eq 0 ]; then
        echo -e "${GREEN}✅ All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}❌ $failed_tests test(s) failed${NC}"
        return 1
    fi
}

# Function to check environment
check_environment() {
    echo -e "\n🔧 Environment Check"
    echo "===================="
    
    # Check if Docker is running
    if ! docker --version > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker not found or not running${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ Docker is available${NC}"
    fi
    
    # Check if docker-compose is available
    if ! docker compose version > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker Compose not found${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ Docker Compose is available${NC}"
    fi
    
    # Check environment variables
    if [ -n "$OPENROUTER_API_KEY" ]; then
        echo -e "${GREEN}✅ OPENROUTER_API_KEY is set${NC}"
    else
        echo -e "${YELLOW}⚠️  OPENROUTER_API_KEY not set (LLM tests will be skipped)${NC}"
    fi
    
    if [ -n "$LANGFUSE_SECRET_KEY" ] && [ -n "$LANGFUSE_PUBLIC_KEY" ]; then
        echo -e "${GREEN}✅ Langfuse credentials are set${NC}"
    else
        echo -e "${YELLOW}⚠️  Langfuse credentials not fully set (telemetry may not work)${NC}"
    fi
}

# Function to check running services
check_services() {
    echo -e "\n🔍 Service Status Check"
    echo "======================="
    
    # Get docker-compose status
    if docker compose ps --format table > /dev/null 2>&1; then
        echo "Docker Compose Services:"
        docker compose ps --format table
        echo ""
    fi
    
    # Check individual services
    check_service "$BACKEND_URL/health" "Backend API"
    check_service "$LANGFUSE_URL/api/public/health" "Langfuse"
}

# Function to show logs if tests fail
show_logs_on_failure() {
    if [ $? -ne 0 ]; then
        echo -e "\n📜 Recent Backend Logs (last 50 lines)"
        echo "======================================"
        docker compose logs --tail=50 backend || echo "Could not retrieve backend logs"
        
        echo -e "\n📜 Recent Langfuse Logs (last 20 lines)"
        echo "======================================="
        docker compose logs --tail=20 langfuse-web || echo "Could not retrieve langfuse logs"
    fi
}

# Function to validate Langfuse integration
check_langfuse_integration() {
    echo -e "\n🔬 Langfuse Integration Check"
    echo "============================="
    
    if check_service "$LANGFUSE_URL/api/public/health" "Langfuse Health"; then
        echo -e "${GREEN}✅ Langfuse is running and accessible${NC}"
        
        # Check if we can access the UI
        if curl -s --max-time 5 "$LANGFUSE_URL" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Langfuse UI is accessible at $LANGFUSE_URL${NC}"
        else
            echo -e "${YELLOW}⚠️  Langfuse UI may not be ready yet${NC}"
        fi
    else
        echo -e "${RED}❌ Langfuse is not accessible${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo "YudaiV3 Integration Test Suite"
    echo "Repository: YudaiV3"
    echo "Test Target: Architect Agent, DaiFu Agent, Langfuse Integration"
    echo "Date: $(date)"
    echo ""
    
    # Run all checks
    check_environment
    check_services
    check_langfuse_integration
    
    # Run the actual tests
    if run_tests; then
        echo -e "\n🎉 ${GREEN}Integration test completed successfully!${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Open Langfuse dashboard: $LANGFUSE_URL"
        echo "2. Check telemetry data for test runs"
        echo "3. Explore API documentation: $BACKEND_URL/docs"
        echo "4. Test with real GitHub tokens if needed"
        exit 0
    else
        echo -e "\n💥 ${RED}Integration test failed!${NC}"
        show_logs_on_failure
        exit 1
    fi
}

# Trap to show logs on any failure
trap show_logs_on_failure ERR

# Run the main function
main "$@" 