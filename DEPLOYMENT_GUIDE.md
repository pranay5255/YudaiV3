# Yudaiv3 Deployment Guide for Vultr

This guide will help you deploy your Yudaiv3 application to Vultr with proper DNS configuration for your domain `yudai.app`.

## Prerequisites

1. **Vultr Account**: You need a Vultr account with billing set up
2. **GoDaddy Domain**: Your domain `yudai.app` purchased from GoDaddy
3. **GoDaddy Account Access**: Access to your GoDaddy dashboard for DNS management
4. **Git Access**: Your code repository should be accessible
5. **API Keys**: Your OpenRouter and GitHub API keys for the application

## GoDaddy Domain Management

### Accessing Your Domain
1. **GoDaddy Login**: Visit [godaddy.com](https://godaddy.com) and sign in
2. **Domain List**: Navigate to "Domains" → "My Domains"
3. **Domain Details**: Click on `yudai.app` to access domain management
4. **DNS Management**: Click "DNS" or "Manage DNS" to configure DNS records

### Important GoDaddy Settings
- **Domain Lock**: Ensure domain is unlocked for DNS changes
- **Privacy Protection**: Can be enabled/disabled as needed
- **Auto-Renewal**: Recommended to enable for continuous service
- **Nameservers**: Keep default GoDaddy nameservers (don't change to custom nameservers)

## Step 1: Create Vultr Instance

### 1.1 Create a New Instance
1. Log into your Vultr account
2. Click "Deploy" → "Deploy New Instance"
3. Choose the following settings:
   - **Server**: Choose a location close to your target users
   - **Server Type**: Cloud Compute
   - **Server Size**: At least 2GB RAM, 1 vCPU (recommended: 4GB RAM, 2 vCPU)
   - **Operating System**: Ubuntu 22.04 LTS
   - **Enable IPv6**: Yes
   - **Add to Startup Script**: No (we'll set up manually)

### 1.2 Configure Instance
- **Hostname**: `yudai-app`
- **Label**: `Yudaiv3 Production`
- **SSH Keys**: Add your SSH key for secure access

## Step 2: Server Setup

### 2.1 Connect to Your Server
```bash
ssh root@YOUR_SERVER_IP
```

### 2.2 Update System and Install Dependencies
```bash
# Update system
apt update && apt upgrade -y

# Install essential packages
apt install -y curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release

# Install Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Node.js (for potential frontend builds)
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Install pnpm
npm install -g pnpm

# Create application user
useradd -m -s /bin/bash yudai
usermod -aG docker yudai
```

### 2.3 Configure Firewall
```bash
# Install UFW
apt install -y ufw

# Configure firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw --force enable
```

## Step 3: Application Deployment

### 3.1 Clone Your Repository
```bash
# Switch to yudai user
su - yudai

# Clone your repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git /home/yudai/YudaiV3
cd /home/yudai/YudaiV3
```

### 3.2 Create Environment File
```bash
# Create .env file
cat > .env << 'EOF'
# Database Configuration
POSTGRES_DB=yudai_db
POSTGRES_USER=yudai_user
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD_HERE

# API Keys (Replace with your actual keys)
OPENROUTER_API_KEY=your_openrouter_api_key_here
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here

# Domain Configuration
DOMAIN=yudai.app
FRONTEND_URL=https://yudai.app
BACKEND_URL=https://yudai.app/api

# Security
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here

# Environment
NODE_ENV=production
DOCKER_COMPOSE=true
EOF
```

### 3.3 Create Test Nginx Configuration
```bash
cat > nginx.test.conf << 'EOF'
# Test configuration for frontend container only
server {
    listen 80;
    server_name localhost;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Block access to .git directory (SECURITY)
    location ~ /\.git {
        deny all;
        return 403;
    }
    
    # Block access to sensitive files
    location ~ /\.(env|htaccess|htpasswd) {
        deny all;
        return 403;
    }
    
    # Frontend static files
    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
    
    # API endpoints - return 404 for testing (no backend)
    location /api/ {
        return 404 "API not available in test mode\n";
        add_header Content-Type text/plain;
    }
    
    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types 
        text/plain 
        text/css 
        text/xml 
        text/javascript 
        application/javascript 
        application/xml+rss 
        application/json;
}
EOF
```

### 3.4 Update Dockerfile for Testing Support
I'll modify the `Dockerfile` instructions in your guide to use a new, dedicated frontend Nginx configuration, which you'll create in the next step.

```bash
# Update the Dockerfile to support both configurations
cat > Dockerfile << 'EOF'
# Multi-stage build for React frontend
FROM node:18-alpine AS builder

# Install pnpm
RUN npm install -g pnpm

# Set work directory
WORKDIR /app

# Copy package files
COPY package*.json pnpm-lock.yaml* ./

# Install dependencies using pnpm
RUN pnpm install

# Copy source code
COPY . .

# Build the application
RUN pnpm run build

# Verify build output
RUN ls -la /app/dist/ && test -f /app/dist/index.html

# Production stage
FROM nginx:alpine

# Copy built app from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configurations
COPY ./nginx.frontend.conf /etc/nginx/conf.d/default.conf

# Create health endpoint
RUN echo "healthy" > /usr/share/nginx/html/health

# Set proper permissions
RUN chmod -R 755 /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
EOF
```

### 3.5 Create Frontend Nginx Configuration
This new configuration file, `nginx.frontend.conf`, is a simplified version of the test configuration, which is appropriate for the production frontend service.

```bash
cat > nginx.frontend.conf << 'EOF'
server {
    listen 80;
    server_name localhost;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/xml+rss
        application/json;
}
EOF
```

### 3.6 Test Frontend Container in Isolation
```bash
# Build frontend container with test configuration
docker build -t yudai-fe-test .

# Run with test nginx configuration
docker run -d --name yudai-fe-test -p 8080:80 \
  -v $(pwd)/nginx.test.conf:/etc/nginx/conf.d/default.conf \
  yudai-fe-test

# Check if it's running
docker ps | grep yudai-fe-test

# Test the container
curl http://localhost:8080/health
curl http://localhost:8080/
curl http://localhost:8080/api/test

# Clean up test container
docker stop yudai-fe-test
docker rm yudai-fe-test
```

### 3.7 Update Docker Compose for Production
Create a production docker-compose file:

```bash
cat > docker-compose.prod.yml << 'EOF'
version: '3.8'

services:
  # PostgreSQL Database
  db:
    build:
      context: ./backend/db
      dockerfile: Dockerfile
    container_name: yudai-db
    restart: unless-stopped
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/db/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - yudai-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Backend API Service
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: yudai-be
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - DB_ECHO=false
      - PYTHONPATH=/app
      - DOCKER_COMPOSE=true
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
      - GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
      - GITHUB_REDIRECT_URI=https://${DOMAIN}/auth/callback
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET=${JWT_SECRET}
      - NODE_ENV=production
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - /app/__pycache__
    networks:
      - yudai-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Frontend Service
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: yudai-fe
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:80"
    depends_on:
      - backend
    networks:
      - yudai-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: yudai-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.prod.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    networks:
      - yudai-network

volumes:
  postgres_data:
    driver: local

networks:
  yudai-network:
    driver: bridge
EOF
```

### 3.8 Create Production Nginx Configuration
```bash
cat > nginx.prod.conf << 'EOF'
# HTTP to HTTPS redirect for all domains
server {
    listen 80;
    server_name yudai.app www.yudai.app api.yudai.app dev.yudai.app;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

# Main application server
server {
    listen 443 ssl http2;
    server_name yudai.app www.yudai.app;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Block access to .git directory (SECURITY)
    location ~ /\.git {
        deny all;
        return 403;
    }
    
    # Block access to sensitive files
    location ~ /\.(env|htaccess|htpasswd) {
        deny all;
        return 403;
    }
    
    # Frontend static files
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # API endpoints - proxy to backend container
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' 'https://yudai.app' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;
        
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://yudai.app';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
        
        # Timeout settings
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types 
        text/plain 
        text/css 
        text/xml 
        text/javascript 
        application/javascript 
        application/xml+rss 
        application/json;
}

# API subdomain server
server {
    listen 443 ssl http2;
    server_name api.yudai.app;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # API endpoints - proxy directly to backend
    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' 'https://yudai.app' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;
        
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://yudai.app';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }
    
    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}

# Development subdomain server
server {
    listen 443 ssl http2;
    server_name dev.yudai.app;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Development frontend - proxy to frontend container
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF
```

## Step 4: SSL Certificate Setup

### 4.1 Prerequisites for SSL Certificate
Before obtaining SSL certificates, ensure:
1. **DNS is configured**: Your GoDaddy DNS records must be pointing to your Vultr server IP
2. **Domain is accessible**: Test that `yudai.app` resolves to your server IP
3. **Port 80 is open**: Certbot needs port 80 to verify domain ownership

### 4.2 Install Certbot
```bash
# Install Certbot
apt install -y certbot python3-certbot-nginx

# Create SSL directory
mkdir -p /home/yudai/YudaiV3/ssl
```

### 4.3 Verify DNS Resolution
```bash
# Test DNS resolution before getting SSL certificate
nslookup yudai.app
nslookup www.yudai.app

# Should return your Vultr server IP address
# If not, wait for DNS propagation or check GoDaddy DNS settings
```

### 4.4 Get SSL Certificate

#### **Option 1: Individual Certificates (Recommended for initial setup)**
```bash
# Stop nginx temporarily (if running)
docker-compose -f docker-compose.prod.yml stop nginx || true

# Get certificate for main domains
certbot certonly --standalone -d yudai.app -d www.yudai.app -d api.yudai.app -d dev.yudai.app

# If successful, you'll see a success message with certificate paths
```

#### **Option 2: Wildcard Certificate (Advanced)**
```bash
# Get wildcard certificate for all subdomains
sudo certbot certonly --manual -d "*.yudai.app" -d yudai.app --preferred-challenges dns

# Follow the interactive prompts to add DNS TXT records
# This requires manual DNS verification for each challenge
```

**Note**: For initial deployment, use Option 1. Option 2 requires manual DNS verification and is more complex.

### 4.5 Copy Certificates to Application Directory
```bash
# Copy certificates to project directory
cp /etc/letsencrypt/live/yudai.app/fullchain.pem /home/yudai/YudaiV3/ssl/
cp /etc/letsencrypt/live/yudai.app/privkey.pem /home/yudai/YudaiV3/ssl/

# Set proper permissions
chown -R yudai:yudai /home/yudai/YudaiV3/ssl
chmod 600 /home/yudai/YudaiV3/ssl/*

# Verify certificates are in place
ls -la /home/yudai/YudaiV3/ssl/
```

### 4.6 Troubleshooting SSL Certificate Issues

#### **Common Issues and Solutions:**

**Issue 1: "Domain not pointing to this server"**
```bash
# Check if domain resolves to your server
dig yudai.app
# Should show your Vultr server IP in the ANSWER section
```

**Issue 2: "Connection refused on port 80"**
```bash
# Ensure port 80 is not blocked
sudo ufw status
# Should show port 80 as ALLOW

# Check if any service is using port 80
sudo netstat -tlnp | grep :80
```

**Issue 3: "DNS propagation not complete"**
- Wait 15-30 minutes after updating GoDaddy DNS
- Use online tools like https://www.whatsmydns.net/
- Try from different locations/networks

**Issue 4: "Rate limit exceeded"**
- Let's Encrypt has rate limits
- Wait 1 hour before retrying
- Use `--dry-run` flag to test without counting against limits:
```bash
certbot certonly --standalone -d yudai.app -d www.yudai.app --dry-run
```

## Step 5: DNS Configuration

### 5.1 Access GoDaddy DNS Management
1. **Log into GoDaddy**: Go to [godaddy.com](https://godaddy.com) and sign in to your account
2. **Navigate to Domains**: Click on "Domains" in the top navigation
3. **Select your domain**: Find and click on `yudai.app` in your domain list
4. **Access DNS Management**: Click on "DNS" or "Manage DNS" button

### 5.2 Get Your Vultr Public IP Address
1. **Log into Vultr Dashboard**: Go to [vultr.com](https://vultr.com) and sign in
2. **Find your instance**: Locate your Yudaiv3 server instance
3. **Copy the IP address**: Note down the public IP address (e.g., `143.110.123.45`)

### 5.3 Configure DNS Records in GoDaddy Dashboard

#### **Step 1: Update Root Domain A Record**
1. **Find the existing `@` A record** (usually pointing to "WebsiteBuilder Site")
2. **Click "Edit"** on the `@` A record
3. **Update the "Data" field** with your Vultr IP address
4. **Save the changes**

#### **Step 2: Add API Subdomain A Record**
1. **Click "Add" button** to create a new record
2. **Select "A" record type**
3. **Configure the record:**

   | Field | Value |
   |-------|-------|
   | **Type** | `A` |
   | **Name** | `api` |
   | **Value** | `YOUR_VULTR_IP` (e.g., 143.110.123.45) |
   | **TTL** | `1 Hour` |

4. **Click "Save"**

#### **Step 3: Add Development Subdomain A Record**
1. **Click "Add" button** to create another record
2. **Select "A" record type**
3. **Configure the record:**

   | Field | Value |
   |-------|-------|
   | **Type** | `A` |
   | **Name** | `dev` |
   | **Value** | `YOUR_VULTR_IP` (e.g., 143.110.123.45) |
   | **TTL** | `1 Hour` |

4. **Click "Save"**

#### **Step 4: Add WWW Subdomain A Record (Optional)**
1. **Click "Add" button**
2. **Select "A" record type**
3. **Configure the record:**

   | Field | Value |
   |-------|-------|
   | **Type** | `A` |
   | **Name** | `www` |
   | **Value** | `YOUR_VULTR_IP` (e.g., 143.110.123.45) |
   | **TTL** | `1 Hour` |

4. **Click "Save"**

### 5.4 Verify DNS Configuration
After saving all records, your DNS configuration should look like this:

| Type | Name | Value | TTL | Purpose |
|------|------|-------|-----|---------|
| A | @ | YOUR_VULTR_IP | 1 Hour | Root domain |
| A | api | YOUR_VULTR_IP | 1 Hour | API subdomain |
| A | dev | YOUR_VULTR_IP | 1 Hour | Development subdomain |
| A | www | YOUR_VULTR_IP | 1 Hour | WWW subdomain |

### 5.5 Test DNS Propagation
```bash
# Test from your local machine
nslookup yudai.app
nslookup api.yudai.app
nslookup dev.yudai.app
nslookup www.yudai.app

# Or use online tools
# Visit: https://dnschecker.org
# Enter: yudai.app, api.yudai.app, dev.yudai.app
```

### 5.6 DNS Propagation Timeline
- **Local propagation**: 5-30 minutes
- **Global propagation**: 24-48 hours
- **Full propagation**: Up to 72 hours

**Note**: You can proceed with SSL certificate setup once local DNS resolution works, but some users worldwide may not see the site until full propagation is complete.

## Step 6: Deploy Application

### 6.1 Build and Start Services
```bash
cd /home/yudai/YudaiV3

# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# Check service status
docker-compose -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 6.2 Verify Deployment
```bash
# Check if services are running
curl -f http://localhost/health
curl -f http://localhost/api/health

# Check SSL certificate
curl -I https://yudai.app
```

## Step 7: Testing Your Deployment

### 7.1 Test Frontend Container in Isolation
```bash
# Test frontend container with test configuration
docker build -t yudai-fe-test .
docker run -d --name yudai-fe-test -p 8080:80 \
  -v $(pwd)/nginx.test.conf:/etc/nginx/conf.d/default.conf \
  yudai-fe-test

# Test the container
curl http://localhost:8080/health
curl http://localhost:8080/
curl http://localhost:8080/api/test

# Clean up
docker stop yudai-fe-test && docker rm yudai-fe-test
```

### 7.2 Test Main Application
- Visit `https://yudai.app`
- Verify the application loads correctly
- Test all major functionality

### 7.3 Test API Subdomain
- Visit `https://api.yudai.app`
- Test API endpoints:
```bash
curl -X GET https://api.yudai.app/health
curl -X GET https://api.yudai.app/your-endpoint
```

### 7.4 Test Development Subdomain
- Visit `https://dev.yudai.app`
- Verify the development environment loads correctly

### 7.5 Test WWW Subdomain
- Visit `https://www.yudai.app`
- Should redirect to or load the same as `https://yudai.app`

### 7.6 Test SSL Certificates
```bash
# Check SSL certificates for all domains
openssl s_client -connect yudai.app:443 -servername yudai.app
openssl s_client -connect api.yudai.app:443 -servername api.yudai.app
openssl s_client -connect dev.yudai.app:443 -servername dev.yudai.app
```

### 7.7 Verify All Subdomains
```bash
# Test all subdomains resolve correctly
nslookup yudai.app
nslookup www.yudai.app
nslookup api.yudai.app
nslookup dev.yudai.app

# Test HTTP to HTTPS redirects
curl -I http://yudai.app
curl -I http://api.yudai.app
curl -I http://dev.yudai.app
```

## Step 8: Monitoring and Maintenance

### 8.1 Set up SSL Auto-renewal
```bash
# Create renewal script
cat > /home/yudai/renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/yudai.app/fullchain.pem /home/yudai/YudaiV3/ssl/
cp /etc/letsencrypt/live/yudai.app/privkey.pem /home/yudai/YudaiV3/ssl/
chown -R yudai:yudai /home/yudai/YudaiV3/ssl
chmod 600 /home/yudai/YudaiV3/ssl/*
docker-compose -f /home/yudai/YudaiV3/docker-compose.prod.yml restart nginx
EOF

chmod +x /home/yudai/renew-ssl.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 12 * * * /home/yudai/renew-ssl.sh") | crontab -
```

### 8.2 Set up Log Rotation
```bash
# Create log rotation config
cat > /etc/logrotate.d/yudai << 'EOF'
/home/yudai/YudaiV3/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 yudai yudai
    postrotate
        docker-compose -f /home/yudai/YudaiV3/docker-compose.prod.yml restart nginx
    endscript
}
EOF
```

### 8.3 Set up Backup Script
```bash
cat > /home/yudai/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/yudai/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker exec yudai-db pg_dump -U yudai_user yudai_db > $BACKUP_DIR/db_backup_$DATE.sql

# Backup application files
tar -czf $BACKUP_DIR/app_backup_$DATE.tar.gz -C /home/yudai YudaiV3

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
EOF

chmod +x /home/yudai/backup.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /home/yudai/backup.sh") | crontab -
```

## Troubleshooting

### Common Issues:

1. **DNS not resolving**: Wait 24-48 hours for DNS propagation
2. **SSL certificate issues**: Check if domain is pointing to correct IP
3. **Docker build failures**: Check logs with `docker-compose logs`
4. **Database connection issues**: Verify environment variables
5. **Frontend not loading**: Check nginx configuration and logs

### Frontend Container Testing Issues:

#### **Issue: "host not found in upstream 'backend'"**
**Solution**: Use the test nginx configuration when testing frontend in isolation:
```bash
# Build and test with test configuration
docker build -t yudai-fe-test .
docker run -d --name yudai-fe-test -p 8080:80 \
  -v $(pwd)/nginx.test.conf:/etc/nginx/conf.d/default.conf \
  yudai-fe-test

# Test the container
curl http://localhost:8080/health
curl http://localhost:8080/
curl http://localhost:8080/api/test

# Clean up
docker stop yudai-fe-test && docker rm yudai-fe-test
```

#### **Issue: "nginx configuration test failed"**
**Solution**: Check nginx configuration syntax:
```bash
# Test nginx configuration
docker run --rm -v $(pwd)/nginx.test.conf:/etc/nginx/conf.d/default.conf nginx:alpine nginx -t
```

### GoDaddy-Specific Issues:

#### **DNS Records Not Updating**
```bash
# Check current DNS resolution
dig yudai.app
dig www.yudai.app

# If still showing old IP or GoDaddy parking page:
# 1. Verify DNS records in GoDaddy dashboard
# 2. Clear browser cache and DNS cache
# 3. Try from different network/location
# 4. Contact GoDaddy support if issue persists
```

#### **GoDaddy DNS Management Issues**
- **Can't edit DNS records**: Ensure domain is unlocked
- **Changes not saving**: Try refreshing page and re-entering values
- **Wrong nameservers**: Keep default GoDaddy nameservers, don't change to custom
- **Domain pointing to parking page**: Remove any A records pointing to GoDaddy's IPs

#### **SSL Certificate with GoDaddy Domain**
- **Domain verification fails**: Ensure DNS A records are correct
- **Certificate not issued**: Check that domain resolves to your Vultr server IP
- **Wildcard certificate issues**: Use specific subdomain certificates instead

### Useful Commands:
```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f [service_name]

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Update application
cd /home/yudai/YudaiV3
git pull
docker-compose -f docker-compose.prod.yml up -d --build

# Test frontend container
docker build -t yudai-fe-test .
docker run -d --name yudai-fe-test -p 8080:80 \
  -v $(pwd)/nginx.test.conf:/etc/nginx/conf.d/default.conf \
  yudai-fe-test
```

## Security Considerations

1. **Firewall**: Only necessary ports are open
2. **SSL**: HTTPS enforced with HSTS
3. **Updates**: Regular system updates
4. **Backups**: Automated daily backups
5. **Monitoring**: Health checks and logging
6. **Environment Variables**: Sensitive data in .env file

## Cost Optimization

1. **Instance Size**: Start with 2GB RAM, scale up if needed
2. **Backup Storage**: Use Vultr Object Storage for backups
3. **CDN**: Consider Cloudflare for static assets
4. **Monitoring**: Use Vultr's built-in monitoring

Your Yudaiv3 application should now be successfully deployed and accessible at `https://yudai.app`!