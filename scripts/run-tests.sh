#!/bin/bash

# Test Runner Script for Production Connectivity
# This script runs all connectivity tests for the production environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Production Connectivity Test Runner${NC}"
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

# Check if we're in the right directory
if [ ! -f "docker-compose.prod.yml" ]; then
    echo -e "${RED}Error: docker-compose.prod.yml not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Parse command line arguments
RUN_TYPESCRIPT_TESTS=true
RUN_SHELL_TESTS=true
RUN_DOCKER_TESTS=true
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --typescript-only)
            RUN_SHELL_TESTS=false
            RUN_DOCKER_TESTS=false
            shift
            ;;
        --shell-only)
            RUN_TYPESCRIPT_TESTS=false
            RUN_DOCKER_TESTS=false
            shift
            ;;
        --docker-only)
            RUN_TYPESCRIPT_TESTS=false
            RUN_SHELL_TESTS=false
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --typescript-only    Run only TypeScript tests"
            echo "  --shell-only         Run only shell script tests"
            echo "  --docker-only        Run only Docker environment tests"
            echo "  --verbose, -v        Enable verbose output"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all tests"
            echo "  $0 --typescript-only  # Run only TypeScript tests"
            echo "  $0 --shell-only       # Run only external connectivity tests"
            echo "  $0 --docker-only      # Run only Docker internal tests"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Test results tracking
TYPESCRIPT_RESULT=0
SHELL_RESULT=0
DOCKER_RESULT=0

# Run TypeScript tests
if [ "$RUN_TYPESCRIPT_TESTS" = true ]; then
    echo -e "${BLUE}📝 Running TypeScript connectivity tests...${NC}"
    echo ""
    
    if [ "$VERBOSE" = true ]; then
        npm test tests/prod-connectivity.test.ts
    else
        npm test tests/prod-connectivity.test.ts --reporter=verbose
    fi
    
    if [ $? -eq 0 ]; then
        print_status 0 "TypeScript tests passed"
    else
        print_status 1 "TypeScript tests failed"
        TYPESCRIPT_RESULT=1
    fi
    echo ""
fi

# Run shell script tests (external connectivity)
if [ "$RUN_SHELL_TESTS" = true ]; then
    echo -e "${BLUE}🌐 Running external connectivity tests...${NC}"
    echo ""
    
    if [ -f "scripts/test-prod-connectivity.sh" ]; then
        if [ "$VERBOSE" = true ]; then
            bash scripts/test-prod-connectivity.sh
        else
            bash scripts/test-prod-connectivity.sh 2>/dev/null || true
        fi
        
        if [ $? -eq 0 ]; then
            print_status 0 "External connectivity tests passed"
        else
            print_status 1 "External connectivity tests failed"
            SHELL_RESULT=1
        fi
    else
        print_status 1 "External connectivity test script not found"
        SHELL_RESULT=1
    fi
    echo ""
fi

# Run Docker environment tests
if [ "$RUN_DOCKER_TESTS" = true ]; then
    echo -e "${BLUE}🐳 Running Docker environment tests...${NC}"
    echo ""
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_status 1 "Docker is not running"
        DOCKER_RESULT=1
    else
        # Check if containers are running
        if docker ps --format "table {{.Names}}" | grep -q "yudai-"; then
            if [ -f "tests/docker-prod-test.sh" ]; then
                if [ "$VERBOSE" = true ]; then
                    bash tests/docker-prod-test.sh
                else
                    bash tests/docker-prod-test.sh 2>/dev/null || true
                fi
                
                if [ $? -eq 0 ]; then
                    print_status 0 "Docker environment tests passed"
                else
                    print_status 1 "Docker environment tests failed"
                    DOCKER_RESULT=1
                fi
            else
                print_status 1 "Docker test script not found"
                DOCKER_RESULT=1
            fi
        else
            print_status 1 "No Yudai containers running. Start with: docker compose -f docker-compose.prod.yml up -d"
            DOCKER_RESULT=1
        fi
    fi
    echo ""
fi

# Summary
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}🎉 Test Runner Complete${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Print individual test results
if [ "$RUN_TYPESCRIPT_TESTS" = true ]; then
    if [ $TYPESCRIPT_RESULT -eq 0 ]; then
        print_status 0 "TypeScript tests: PASSED"
    else
        print_status 1 "TypeScript tests: FAILED"
    fi
fi

if [ "$RUN_SHELL_TESTS" = true ]; then
    if [ $SHELL_RESULT -eq 0 ]; then
        print_status 0 "External connectivity tests: PASSED"
    else
        print_status 1 "External connectivity tests: FAILED"
    fi
fi

if [ "$RUN_DOCKER_TESTS" = true ]; then
    if [ $DOCKER_RESULT -eq 0 ]; then
        print_status 0 "Docker environment tests: PASSED"
    else
        print_status 1 "Docker environment tests: FAILED"
    fi
fi

echo ""

# Overall result
TOTAL_RESULT=$((TYPESCRIPT_RESULT + SHELL_RESULT + DOCKER_RESULT))

if [ $TOTAL_RESULT -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Your frontend-to-backend communication is working correctly.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please check the output above for details.${NC}"
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo -e "  - Make sure your production environment is running"
    echo -e "  - Check that all containers are healthy"
    echo -e "  - Verify your nginx configuration"
    echo -e "  - Ensure SSL certificates are valid"
    exit 1
fi 