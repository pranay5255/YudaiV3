#!/bin/bash

# Docker Production Environment Test
# This script tests frontend-to-backend connectivity from within the Docker network

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 Docker Production Environment Test${NC}"
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

# Function to test internal connectivity
test_internal_connectivity() {
    local service=$1
    local port=$2
    local endpoint=$3
    local description=$4
    
    echo -e "${YELLOW}Testing internal: $description${NC}"
    echo -e "Service: $service:$port$endpoint"
    
    # Test using curl from within the Docker network
    if curl -s -f --max-time 10 "http://$service:$port$endpoint" > /dev/null 2>&1; then
        print_status 0 "Internal connectivity successful"
    else
        print_status 1 "Internal connectivity failed"
        return 1
    fi
    
    echo ""
}

# Function to test container health
test_container_health() {
    local container=$1
    local description=$2
    
    echo -e "${YELLOW}Testing container health: $description${NC}"
    echo -e "Container: $container"
    
    # Check if container is running
    if docker ps --format "table {{.Names}}" | grep -q "^$container$"; then
        print_status 0 "Container is running"
        
        # Check container health status
        health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-health-check")
        if [ "$health_status" = "healthy" ]; then
            print_status 0 "Container health check passed"
        elif [ "$health_status" = "no-health-check" ]; then
            print_status 0 "Container has no health check (OK)"
        else
            print_status 1 "Container health check failed: $health_status"
            return 1
        fi
    else
        print_status 1 "Container is not running"
        return 1
    fi
    
    echo ""
}

# Function to test network connectivity
test_network_connectivity() {
    local from_container=$1
    local to_service=$2
    local port=$3
    local description=$4
    
    echo -e "${YELLOW}Testing network connectivity: $description${NC}"
    echo -e "From: $from_container -> To: $to_service:$port"
    
    # Test connectivity using docker exec
    if docker exec "$from_container" curl -s -f --max-time 10 "http://$to_service:$port/health" > /dev/null 2>&1; then
        print_status 0 "Network connectivity successful"
    else
        print_status 1 "Network connectivity failed"
        return 1
    fi
    
    echo ""
}

# Function to test API functionality
test_api_functionality() {
    local service=$1
    local port=$2
    local description=$3
    
    echo -e "${YELLOW}Testing API functionality: $description${NC}"
    echo -e "Service: $service:$port"
    
    # Test health endpoint
    health_response=$(curl -s "http://$service:$port/health" 2>/dev/null || echo "FAILED")
    if [ "$health_response" != "FAILED" ]; then
        print_status 0 "Health endpoint responding"
        echo -e "Response: $health_response"
    else
        print_status 1 "Health endpoint failed"
        return 1
    fi
    
    # Test docs endpoint
    docs_status=$(curl -s -o /dev/null -w "%{http_code}" "http://$service:$port/docs" 2>/dev/null || echo "FAILED")
    if [ "$docs_status" = "200" ]; then
        print_status 0 "API docs accessible"
    elif [ "$docs_status" = "404" ]; then
        print_status 0 "API docs not found (expected for some setups)"
    else
        print_status 1 "API docs failed (HTTP $docs_status)"
    fi
    
    echo ""
}

# Function to test database connectivity
test_database_connectivity() {
    local container=$1
    local description=$2
    
    echo -e "${YELLOW}Testing database connectivity: $description${NC}"
    echo -e "Container: $container"
    
    # Test PostgreSQL connectivity
    if docker exec "$container" pg_isready -U yudai_user -d yudai_db > /dev/null 2>&1; then
        print_status 0 "Database connectivity successful"
    else
        print_status 1 "Database connectivity failed"
        return 1
    fi
    
    echo ""
}

# Main test execution
echo -e "${BLUE}Starting Docker environment tests...${NC}"
echo ""

# Test 1: Check if containers are running
test_container_health "yudai-db" "PostgreSQL Database"
test_container_health "yudai-be" "Backend API Service"
test_container_health "yudai-fe" "Frontend Service"

# Test 2: Test internal backend connectivity
test_internal_connectivity "backend" "8000" "/health" "Backend health endpoint"
test_internal_connectivity "backend" "8000" "/docs" "Backend API documentation"

# Test 3: Test database connectivity from backend
test_database_connectivity "yudai-be" "Backend to database"

# Test 4: Test frontend to backend connectivity
test_network_connectivity "yudai-fe" "backend" "8000" "Frontend to backend"

# Test 5: Test API functionality
test_api_functionality "backend" "8000" "Backend API"

# Test 6: Test nginx proxy configuration (if nginx container exists)
if docker ps --format "table {{.Names}}" | grep -q "yudai-nginx"; then
    test_container_health "yudai-nginx" "Nginx Proxy"
    test_network_connectivity "yudai-nginx" "backend" "8000" "Nginx to backend"
    test_network_connectivity "yudai-nginx" "frontend" "80" "Nginx to frontend"
else
    echo -e "${YELLOW}Note: Nginx container not found, skipping nginx tests${NC}"
    echo ""
fi

# Test 7: Test Docker network
echo -e "${YELLOW}Testing Docker network configuration...${NC}"
echo -e "Network: yudai-network"

# Check if network exists
if docker network ls --format "table {{.Name}}" | grep -q "^yudai-network$"; then
    print_status 0 "Docker network exists"
    
    # List containers in network
    echo -e "${BLUE}Containers in yudai-network:${NC}"
    docker network inspect yudai-network --format='{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || echo "No containers found"
else
    print_status 1 "Docker network not found"
fi

echo ""

# Test 8: Test environment variables
echo -e "${YELLOW}Testing environment variables...${NC}"

# Check backend environment
backend_env=$(docker exec yudai-be env | grep -E "(DATABASE_URL|GITHUB_|API_DOMAIN)" || echo "No env vars found")
if echo "$backend_env" | grep -q "DATABASE_URL"; then
    print_status 0 "Backend environment variables configured"
else
    print_status 1 "Backend environment variables missing"
fi

echo ""

# Test 9: Test volume mounts
echo -e "${YELLOW}Testing volume mounts...${NC}"

# Check if backend volume is mounted
if docker exec yudai-be ls /app > /dev/null 2>&1; then
    print_status 0 "Backend volume mount working"
else
    print_status 1 "Backend volume mount failed"
fi

# Check if database volume is mounted
if docker exec yudai-db ls /var/lib/postgresql/data > /dev/null 2>&1; then
    print_status 0 "Database volume mount working"
else
    print_status 1 "Database volume mount failed"
fi

echo ""

# Test 10: Performance test
echo -e "${YELLOW}Testing performance...${NC}"

# Test response time for health endpoint
start_time=$(date +%s%N)
curl -s -f "http://backend:8000/health" > /dev/null
end_time=$(date +%s%N)

response_time=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds
if [ $response_time -lt 1000 ]; then
    print_status 0 "Response time acceptable (${response_time}ms)"
else
    print_status 1 "Response time too slow (${response_time}ms)"
fi

echo ""

# Summary
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}🎉 Docker Environment Test Complete${NC}"
echo -e "${BLUE}=====================================${NC}"

# Check if all tests passed
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All Docker environment tests passed!${NC}"
    echo -e "${GREEN}Your frontend-to-backend communication is working correctly within Docker.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some Docker environment tests failed.${NC}"
    echo -e "${YELLOW}Please check your Docker Compose configuration and container logs.${NC}"
    exit 1
fi 