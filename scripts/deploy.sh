#!/bin/bash
# ===========================================
# YudaiV3 Full Stack Deployment Script
# Frontend: Vercel
# Backend: Docker Compose
# ===========================================

set -e

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
FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-yudai.app}"
BACKEND_IP="${BACKEND_IP:-}"
DEPLOY_MODE="${DEPLOY_MODE:-nginx}"  # Options: nginx, direct
SSL_EMAIL="${SSL_EMAIL:-}"
VERCEL_TOKEN="${VERCEL_TOKEN:-}"
VERCEL_ORG_ID="${VERCEL_ORG_ID:-}"
VERCEL_PROJECT_ID="${VERCEL_PROJECT_ID:-}"

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --mode <nginx|direct>    Deployment mode (default: nginx)"
    echo "                           nginx: Backend behind nginx with SSL"
    echo "                           direct: Vercel rewrites to backend IP"
    echo "  --backend-ip <IP>        Backend server IP (required for direct mode)"
    echo "  --backend-domain <domain> Backend domain (default: api.yudai.app)"
    echo "  --frontend-domain <domain> Frontend domain (default: yudai.app)"
    echo "  --ssl-email <email>      Email for Let's Encrypt SSL"
    echo "  --vercel-token <token>   Vercel API token"
    echo "  --vercel-org-id <id>     Vercel organization ID"
    echo "  --vercel-project-id <id> Vercel project ID"
    echo "  --skip-backend           Skip backend deployment"
    echo "  --skip-frontend          Skip frontend deployment"
    echo "  --help                   Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  BACKEND_IP, BACKEND_DOMAIN, FRONTEND_DOMAIN"
    echo "  SSL_EMAIL, VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID"
}

# Parse arguments
SKIP_BACKEND=false
SKIP_FRONTEND=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            DEPLOY_MODE="$2"
            shift 2
            ;;
        --backend-ip)
            BACKEND_IP="$2"
            shift 2
            ;;
        --backend-domain)
            BACKEND_DOMAIN="$2"
            shift 2
            ;;
        --frontend-domain)
            FRONTEND_DOMAIN="$2"
            shift 2
            ;;
        --ssl-email)
            SSL_EMAIL="$2"
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
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=()
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing+=("docker-compose")
    fi
    
    # Check Vercel CLI for frontend deployment
    if [ "$SKIP_FRONTEND" = false ]; then
        if ! command -v vercel &> /dev/null && [ -z "$VERCEL_TOKEN" ]; then
            missing+=("vercel-cli (or set VERCEL_TOKEN)")
        fi
    fi
    
    # Check for nginx mode
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        if ! command -v nginx &> /dev/null; then
            log_warning "nginx not found - will attempt to install"
        fi
        if ! command -v certbot &> /dev/null; then
            log_warning "certbot not found - will attempt to install"
        fi
    fi
    
    # Check for direct mode
    if [ "$DEPLOY_MODE" = "direct" ] && [ -z "$BACKEND_IP" ]; then
        log_error "Backend IP is required for direct mode. Use --backend-ip or set BACKEND_IP"
        exit 1
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Install nginx and certbot if needed
install_nginx_certbot() {
    if [ "$DEPLOY_MODE" != "nginx" ]; then
        return
    fi
    
    log_info "Ensuring nginx and certbot are installed..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -qq
        if ! command -v nginx &> /dev/null; then
            sudo apt-get install -y nginx
        fi
        if ! command -v certbot &> /dev/null; then
            sudo apt-get install -y certbot python3-certbot-nginx
        fi
    elif command -v yum &> /dev/null; then
        if ! command -v nginx &> /dev/null; then
            sudo yum install -y nginx
        fi
        if ! command -v certbot &> /dev/null; then
            sudo yum install -y certbot python3-certbot-nginx
        fi
    else
        log_warning "Could not install nginx/certbot automatically. Please install manually."
    fi
    
    log_success "Nginx and certbot ready"
}

# Generate nginx configuration
generate_nginx_config() {
    log_info "Generating nginx configuration..."
    
    local nginx_conf="/etc/nginx/sites-available/$BACKEND_DOMAIN"
    local nginx_enabled="/etc/nginx/sites-enabled/$BACKEND_DOMAIN"
    
    cat << 'EOF' | sudo tee "$nginx_conf" > /dev/null
# ===========================================
# YudaiV3 Backend Nginx Configuration
# Auto-generated by deploy.sh
# ===========================================

# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# Upstream for backend
upstream backend_upstream {
    server 127.0.0.1:8000;
    keepalive 32;
}

# HTTP -> HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name BACKEND_DOMAIN_PLACEHOLDER;
    
    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name BACKEND_DOMAIN_PLACEHOLDER;
    
    # SSL Configuration (will be updated by certbot)
    ssl_certificate /etc/letsencrypt/live/BACKEND_DOMAIN_PLACEHOLDER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/BACKEND_DOMAIN_PLACEHOLDER/privkey.pem;
    
    # Modern SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # CORS headers for frontend domain
    add_header Access-Control-Allow-Origin "https://FRONTEND_DOMAIN_PLACEHOLDER" always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH" always;
    add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, X-Requested-With, X-Session-Id" always;
    add_header Access-Control-Allow-Credentials "true" always;
    add_header Access-Control-Max-Age "86400" always;
    
    # Rate limiting
    limit_req zone=api_limit burst=20 nodelay;
    limit_conn conn_limit 20;
    
    # Increase buffer sizes for large requests
    client_body_buffer_size 128k;
    client_max_body_size 50m;
    
    # Proxy settings
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    
    # WebSocket support
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
    
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    
    # Handle preflight requests
    if ($request_method = 'OPTIONS') {
        add_header Access-Control-Allow-Origin "https://FRONTEND_DOMAIN_PLACEHOLDER" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, X-Requested-With, X-Session-Id" always;
        add_header Access-Control-Allow-Credentials "true" always;
        add_header Access-Control-Max-Age "86400" always;
        add_header Content-Length 0;
        add_header Content-Type text/plain;
        return 204;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://backend_upstream;
        access_log off;
    }
    
    # API routes
    location / {
        proxy_pass http://backend_upstream;
    }
    
    # Logging
    access_log /var/log/nginx/BACKEND_DOMAIN_PLACEHOLDER.access.log;
    error_log /var/log/nginx/BACKEND_DOMAIN_PLACEHOLDER.error.log;
}
EOF
    
    # Replace placeholders
    sudo sed -i "s/BACKEND_DOMAIN_PLACEHOLDER/$BACKEND_DOMAIN/g" "$nginx_conf"
    sudo sed -i "s/FRONTEND_DOMAIN_PLACEHOLDER/$FRONTEND_DOMAIN/g" "$nginx_conf"
    
    # Enable site
    sudo ln -sf "$nginx_conf" "$nginx_enabled"
    
    # Remove default site if exists
    sudo rm -f /etc/nginx/sites-enabled/default
    
    log_success "Nginx configuration generated at $nginx_conf"
}

# Setup SSL certificates
setup_ssl() {
    if [ "$DEPLOY_MODE" != "nginx" ]; then
        return
    fi
    
    if [ -z "$SSL_EMAIL" ]; then
        log_warning "SSL_EMAIL not set. Skipping SSL certificate setup."
        log_warning "Run: certbot --nginx -d $BACKEND_DOMAIN"
        return
    fi
    
    log_info "Setting up SSL certificate for $BACKEND_DOMAIN..."
    
    # Create certbot webroot directory
    sudo mkdir -p /var/www/certbot
    
    # Test nginx config first
    if ! sudo nginx -t; then
        log_error "Nginx configuration test failed"
        exit 1
    fi
    
    # Reload nginx
    sudo systemctl reload nginx
    
    # Obtain certificate (use --register-unsafely-without-email if no email)
    if [ -n "$SSL_EMAIL" ]; then
        sudo certbot --nginx -d "$BACKEND_DOMAIN" --non-interactive --agree-tos --email "$SSL_EMAIL"
    else
        sudo certbot --nginx -d "$BACKEND_DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
    fi
    
    # Set up auto-renewal
    sudo systemctl enable certbot.timer 2>/dev/null || true
    
    log_success "SSL certificate configured"
}

# Deploy backend with Docker Compose
deploy_backend() {
    if [ "$SKIP_BACKEND" = true ]; then
        log_info "Skipping backend deployment"
        return
    fi
    
    log_info "Deploying backend with Docker Compose..."
    
    cd "$PROJECT_ROOT"
    
    # Update backend environment for production
    local env_file="$BACKEND_DIR/.env.prod"
    
    # Update ALLOW_ORIGINS for CORS
    if grep -q "^ALLOW_ORIGINS=" "$env_file" 2>/dev/null; then
        sed -i "s|^ALLOW_ORIGINS=.*|ALLOW_ORIGINS=https://$FRONTEND_DOMAIN|" "$env_file"
    else
        echo "ALLOW_ORIGINS=https://$FRONTEND_DOMAIN" >> "$env_file"
    fi
    
    # Update domain configurations
    sed -i "s|^DOMAIN=.*|DOMAIN=$FRONTEND_DOMAIN|" "$env_file"
    sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=https://$FRONTEND_DOMAIN|" "$env_file"
    sed -i "s|^BACKEND_URL=.*|BACKEND_URL=https://$BACKEND_DOMAIN|" "$env_file"
    sed -i "s|^GITHUB_REDIRECT_URI=.*|GITHUB_REDIRECT_URI=https://$FRONTEND_DOMAIN/auth/callback|" "$env_file"
    sed -i "s|^CONTROLLER_BASE_URL=.*|CONTROLLER_BASE_URL=https://$FRONTEND_DOMAIN|" "$env_file"
    
    # Pull latest images and rebuild
    docker-compose -f docker-compose.backend-only.yml pull 2>/dev/null || true
    docker-compose -f docker-compose.backend-only.yml build --no-cache
    
    # Stop existing containers
    docker-compose -f docker-compose.backend-only.yml down
    
    # Start containers
    docker-compose -f docker-compose.backend-only.yml up -d
    
    # Wait for backend to be healthy
    log_info "Waiting for backend to be healthy..."
    local max_attempts=60
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "http://localhost:8000/health" > /dev/null 2>&1; then
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "Backend failed to start within timeout"
        docker-compose -f docker-compose.backend-only.yml logs --tail=50
        exit 1
    fi
    
    log_success "Backend deployed and healthy"
    
    # Reload nginx if using nginx mode
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        sudo nginx -t && sudo systemctl reload nginx
    fi
}

# Update vercel.json for deployment
update_vercel_config() {
    log_info "Updating Vercel configuration..."
    
    local vercel_json="$FRONTEND_DIR/vercel.json"
    
    if [ "$DEPLOY_MODE" = "direct" ]; then
        # Direct mode: rewrite to backend IP
        cat > "$vercel_json" << EOF
{
  "\$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "http://${BACKEND_IP}:8000/:path*"
    }
  ]
}
EOF
    else
        # Nginx mode: no rewrites needed, frontend calls backend domain directly
        cat > "$vercel_json" << EOF
{
  "\$schema": "https://openapi.vercel.sh/vercel.json",
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" }
      ]
    }
  ]
}
EOF
    fi
    
    log_success "Vercel configuration updated"
}

# Deploy frontend to Vercel
deploy_frontend() {
    if [ "$SKIP_FRONTEND" = true ]; then
        log_info "Skipping frontend deployment"
        return
    fi
    
    log_info "Deploying frontend to Vercel..."
    
    cd "$FRONTEND_DIR"
    
    # Set environment variables for Vercel
    local vercel_env_args=()
    
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        # Backend is at api.yudai.app
        vercel_env_args+=(--env VITE_API_BASE_URL="https://$BACKEND_DOMAIN")
    else
        # Backend is accessed via Vercel rewrite
        vercel_env_args+=(--env VITE_API_BASE_URL="/api")
    fi
    
    # Check if using Vercel CLI or API token
    if [ -n "$VERCEL_TOKEN" ]; then
        log_info "Using Vercel API token for deployment..."
        
        # Create .vercel directory and project.json if org/project IDs provided
        if [ -n "$VERCEL_ORG_ID" ] && [ -n "$VERCEL_PROJECT_ID" ]; then
            mkdir -p .vercel
            cat > .vercel/project.json << EOF
{
  "orgId": "$VERCEL_ORG_ID",
  "projectId": "$VERCEL_PROJECT_ID"
}
EOF
        fi
        
        # Deploy using token
        vercel --token "$VERCEL_TOKEN" --prod --yes "${vercel_env_args[@]}"
    else
        # Use Vercel CLI (requires interactive login)
        log_info "Using Vercel CLI for deployment..."
        vercel --prod --yes "${vercel_env_args[@]}"
    fi
    
    log_success "Frontend deployed to Vercel"
}

# Configure DNS (instructions)
configure_dns() {
    log_info "DNS Configuration Instructions:"
    echo ""
    echo "For the frontend ($FRONTEND_DOMAIN):"
    echo "  - A Record: $FRONTEND_DOMAIN -> 76.76.21.21 (Vercel)"
    echo "  - Or CNAME: $FRONTEND_DOMAIN -> cname.vercel-dns.com"
    echo ""
    
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        echo "For the backend ($BACKEND_DOMAIN):"
        echo "  - A Record: $BACKEND_DOMAIN -> $(curl -s ifconfig.me)"
    fi
    echo ""
    echo "Note: DNS changes may take up to 48 hours to propagate."
}

# Health check
health_check() {
    log_info "Running health checks..."
    
    # Check backend
    log_info "Checking backend health..."
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        if curl -sf "https://$BACKEND_DOMAIN/health" > /dev/null 2>&1; then
            log_success "Backend (HTTPS): healthy"
        else
            log_warning "Backend (HTTPS): not responding (may need DNS/SSL setup)"
        fi
    else
        if curl -sf "http://$BACKEND_IP:8000/health" > /dev/null 2>&1; then
            log_success "Backend (direct): healthy"
        else
            log_warning "Backend (direct): not responding"
        fi
    fi
    
    # Check frontend
    log_info "Checking frontend health..."
    if curl -sf "https://$FRONTEND_DOMAIN" > /dev/null 2>&1; then
        log_success "Frontend: accessible"
    else
        log_warning "Frontend: not accessible (may need DNS setup)"
    fi
}

# Main deployment flow
main() {
    echo ""
    echo "==========================================="
    echo "  YudaiV3 Full Stack Deployment"
    echo "==========================================="
    echo ""
    echo "Mode: $DEPLOY_MODE"
    echo "Backend Domain: $BACKEND_DOMAIN"
    echo "Frontend Domain: $FRONTEND_DOMAIN"
    if [ "$DEPLOY_MODE" = "direct" ]; then
        echo "Backend IP: $BACKEND_IP"
    fi
    echo ""
    
    check_prerequisites
    
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        install_nginx_certbot
        generate_nginx_config
    fi
    
    deploy_backend
    
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        setup_ssl
        sudo nginx -t && sudo systemctl reload nginx
    fi
    
    update_vercel_config
    deploy_frontend
    configure_dns
    health_check
    
    echo ""
    echo "==========================================="
    echo "  Deployment Complete!"
    echo "==========================================="
    echo ""
    echo "Frontend: https://$FRONTEND_DOMAIN"
    if [ "$DEPLOY_MODE" = "nginx" ]; then
        echo "Backend:  https://$BACKEND_DOMAIN"
    else
        echo "Backend:  http://$BACKEND_IP:8000 (via Vercel rewrite)"
    fi
    echo ""
}

# Run main
main "$@"
