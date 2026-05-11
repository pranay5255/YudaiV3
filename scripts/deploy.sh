#!/bin/bash
# ===========================================
# YudaiV3 Full Stack Deployment Script
# Frontend: Vercel
# Backend: Docker Compose
# ===========================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/src"

# Default values (override with environment variables or flags)
BACKEND_DOMAIN="${BACKEND_DOMAIN:-api.yudai.app}"
FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-www.yudai.app}"
BACKEND_IP="${BACKEND_IP:-}"
VERCEL_TOKEN="${VERCEL_TOKEN:-}"
VERCEL_ORG_ID="${VERCEL_ORG_ID:-}"
VERCEL_PROJECT_ID="${VERCEL_PROJECT_ID:-}"

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --backend-domain <domain>  Backend domain (default: api.yudai.app)"
    echo "  --backend-ip <ip>          Backend server IP (optional, used in DNS output)"
    echo "  --frontend-domain <domain> Frontend domain (default: www.yudai.app)"
    echo "  --vercel-token <token>     Vercel API token"
    echo "  --vercel-org-id <id>       Vercel organization ID"
    echo "  --vercel-project-id <id>   Vercel project ID"
    echo "  --skip-backend             Skip backend deployment"
    echo "  --skip-frontend            Skip frontend deployment"
    echo "  --help                     Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  BACKEND_DOMAIN, BACKEND_IP, FRONTEND_DOMAIN"
    echo "  YUDAI_INTERNAL_MIDDLEWARE_SECRET"
    echo "  VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID"
}

# Parse arguments
SKIP_BACKEND=false
SKIP_FRONTEND=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-domain)
            BACKEND_DOMAIN="$2"
            shift 2
            ;;
        --backend-ip)
            BACKEND_IP="$2"
            shift 2
            ;;
        --frontend-domain)
            FRONTEND_DOMAIN="$2"
            shift 2
            ;;
        --vercel-token)
            VERCEL_TOKEN="$2"
            shift 2
            ;;
        --vercel-org-id)
            VERCEL_ORG_ID="$2"
            shift 2
            ;;
        --vercel-project-id)
            VERCEL_PROJECT_ID="$2"
            shift 2
            ;;
        --skip-backend)
            SKIP_BACKEND=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

upsert_env() {
    local file="$1"
    local key="$2"
    local value="$3"

    if grep -q "^${key}=" "$file" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

read_env_value() {
    local file="$1"
    local key="$2"
    local value
    if [ ! -f "$file" ]; then
        return 1
    fi
    value="$(grep -E "^${key}=" "$file" | tail -n 1 | cut -d= -f2-)"
    value="${value%$'\r'}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s' "$value"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    if ! command -v docker >/dev/null 2>&1; then
        missing+=("docker")
    fi

    if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
        missing+=("docker-compose (or docker compose)")
    fi

    if ! command -v curl >/dev/null 2>&1; then
        missing+=("curl")
    fi

    if [ "$SKIP_FRONTEND" = false ]; then
        if ! command -v vercel >/dev/null 2>&1 && [ -z "$VERCEL_TOKEN" ]; then
            missing+=("vercel-cli (or set VERCEL_TOKEN)")
        fi
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi

    log_success "All prerequisites met"
}

# Deploy backend with Docker Compose
deploy_backend() {
    if [ "$SKIP_BACKEND" = true ]; then
        log_info "Skipping backend deployment"
        return
    fi

    log_info "Deploying backend with Docker Compose..."

    cd "$PROJECT_ROOT"

    local env_file="$BACKEND_DIR/.env.prod"
    if [ ! -f "$env_file" ]; then
        log_error "Missing backend env file: $env_file"
        exit 1
    fi

    # Update backend runtime domain and CORS settings.
    upsert_env "$env_file" "DOMAIN" "$FRONTEND_DOMAIN"
    upsert_env "$env_file" "FRONTEND_URL" "https://$FRONTEND_DOMAIN"
    upsert_env "$env_file" "FRONTEND_BASE_URL" "https://$FRONTEND_DOMAIN"
    upsert_env "$env_file" "BACKEND_URL" "https://$BACKEND_DOMAIN"
    upsert_env "$env_file" "API_DOMAIN" "$BACKEND_DOMAIN"
    upsert_env "$env_file" "ALLOW_ORIGINS" "https://yudai.app,https://www.yudai.app"
    upsert_env "$env_file" "ALLOW_ORIGIN_REGEX" "^https://.*\\.vercel\\.app$"
    upsert_env "$env_file" "GITHUB_REDIRECT_URI" "https://api.yudai.app/auth/callback"
    upsert_env "$env_file" "CONTROLLER_BASE_URL" "https://$BACKEND_DOMAIN"
    if [ -z "$(read_env_value "$env_file" "YUDAI_INTERNAL_MIDDLEWARE_SECRET")" ]; then
        log_error "Missing YUDAI_INTERNAL_MIDDLEWARE_SECRET in $env_file"
        exit 1
    fi

    compose -f docker-compose.backend-only.yml pull 2>/dev/null || true
    compose -f docker-compose.backend-only.yml build --no-cache
    log_info "Running Modal sandbox preflight before backend replacement..."
    compose -f docker-compose.backend-only.yml up \
        --abort-on-container-exit \
        --exit-code-from modal-preflight \
        modal-preflight
    compose -f docker-compose.backend-only.yml up -d db backend

    log_info "Waiting for backend health endpoint..."
    local max_attempts=60
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "http://localhost:8000/health" > /dev/null 2>&1; then
            log_success "Backend deployed and healthy"
            return
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    log_error "Backend failed to become healthy in time"
    compose -f docker-compose.backend-only.yml logs --tail=50
    exit 1
}

# Validate src/vercel.json is present. It contains the app middleware rewrites and
# must not be rewritten by this deployment helper.
update_vercel_config() {
    log_info "Validating Vercel configuration..."

    local vercel_json="$FRONTEND_DIR/vercel.json"
    if [ ! -f "$vercel_json" ]; then
        log_error "Missing Vercel config: $vercel_json"
        exit 1
    fi

    if ! grep -Fq '"/ai/:path*"' "$vercel_json" || ! grep -Fq '"/realtime/:path*"' "$vercel_json"; then
        log_error "$vercel_json is missing AI or realtime middleware rewrites"
        exit 1
    fi

    log_success "Vercel configuration is ready"
}

# Deploy frontend to Vercel
deploy_frontend() {
    if [ "$SKIP_FRONTEND" = true ]; then
        log_info "Skipping frontend deployment"
        return
    fi

    log_info "Deploying frontend to Vercel..."

    cd "$FRONTEND_DIR"

    local env_file="$BACKEND_DIR/.env.prod"
    local internal_secret="${YUDAI_INTERNAL_MIDDLEWARE_SECRET:-}"
    if [ -z "$internal_secret" ]; then
        internal_secret="$(read_env_value "$env_file" "YUDAI_INTERNAL_MIDDLEWARE_SECRET" || true)"
    fi
    if [ -z "$internal_secret" ]; then
        log_error "YUDAI_INTERNAL_MIDDLEWARE_SECRET must be available for Vercel middleware"
        exit 1
    fi

    local vercel_env_args=(
        --env "VITE_AUTH_API_BASE_URL=https://$BACKEND_DOMAIN"
        --env "YUDAI_BACKEND_BASE_URL=https://$BACKEND_DOMAIN"
        --env "YUDAI_INTERNAL_MIDDLEWARE_SECRET=$internal_secret"
    )

    if [ -n "$VERCEL_TOKEN" ]; then
        log_info "Using Vercel token deployment"

        if [ -n "$VERCEL_ORG_ID" ] && [ -n "$VERCEL_PROJECT_ID" ]; then
            mkdir -p .vercel
            cat > .vercel/project.json << EOF_JSON
{
  "orgId": "$VERCEL_ORG_ID",
  "projectId": "$VERCEL_PROJECT_ID"
}
EOF_JSON
        fi

        vercel --token "$VERCEL_TOKEN" --prod --yes "${vercel_env_args[@]}"
    else
        log_info "Using logged-in Vercel CLI deployment"
        vercel --prod --yes "${vercel_env_args[@]}"
    fi

    log_success "Frontend deployed to Vercel"
}

# DNS instructions
configure_dns() {
    log_info "DNS configuration"
    echo ""
    echo "Frontend domain:"
    echo "  - A Record: $FRONTEND_DOMAIN -> 76.76.21.21"
    echo "  - Or CNAME: $FRONTEND_DOMAIN -> cname.vercel-dns.com"
    echo ""
    echo "Backend domain:"
    if [ -n "$BACKEND_IP" ]; then
        echo "  - A Record: $BACKEND_DOMAIN -> $BACKEND_IP"
    else
        echo "  - A Record: $BACKEND_DOMAIN -> <YOUR_SERVER_IP>"
    fi
    echo ""
    echo "DNS propagation can take up to 48 hours."
}

# Health checks
health_check() {
    log_info "Running health checks..."

    if curl -sf "https://$BACKEND_DOMAIN/health" > /dev/null 2>&1; then
        log_success "Backend HTTPS endpoint: healthy"
    else
        log_warning "Backend HTTPS endpoint not reachable yet"
    fi

    if curl -sf "https://$FRONTEND_DOMAIN" > /dev/null 2>&1; then
        log_success "Frontend endpoint: reachable"
    else
        log_warning "Frontend endpoint not reachable yet"
    fi
}

main() {
    echo ""
    echo "==========================================="
    echo "  YudaiV3 Full Stack Deployment"
    echo "==========================================="
    echo ""
    echo "Frontend Domain: $FRONTEND_DOMAIN"
    echo "Backend Domain:  $BACKEND_DOMAIN"
    echo ""

    check_prerequisites
    deploy_backend
    update_vercel_config
    deploy_frontend
    configure_dns
    health_check

    echo ""
    echo "==========================================="
    echo "  Deployment Complete"
    echo "==========================================="
    echo ""
    echo "Frontend: https://$FRONTEND_DOMAIN"
    echo "Backend:  https://$BACKEND_DOMAIN"
    echo ""
}

main "$@"
