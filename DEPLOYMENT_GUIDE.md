# Yudaiv3 Deployment Guide for Vultr

This guide will help you deploy your Yudaiv3 application to Vultr with proper DNS configuration for your domain `yudai.app`.

## Prerequisites

1. **Vultr Account**: You need a Vultr account with billing set up
2. **Domain**: Your domain `yudai.app` purchased from GoDaddy
3. **DNS Records**: The DNS records provided by GoDaddy
4. **Git Access**: Your code repository should be accessible

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
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git /home/yudai/yudai-app
cd /home/yudai/yudai-app
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

### 3.3 Update Docker Compose for Production
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

### 3.4 Create Production Nginx Configuration
```bash
cat > nginx.prod.conf << 'EOF'
server {
    listen 80;
    server_name yudai.app www.yudai.app;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yudai.app www.yudai.app;
    
    # SSL Configuration (will be set up with Let's Encrypt)
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
    
    # Frontend
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # API endpoints
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

## Step 4: SSL Certificate Setup

### 4.1 Install Certbot
```bash
# Install Certbot
apt install -y certbot python3-certbot-nginx

# Create SSL directory
mkdir -p /home/yudai/yudai-app/ssl
```

### 4.2 Get SSL Certificate
```bash
# Stop nginx temporarily
docker-compose -f docker-compose.prod.yml stop nginx

# Get certificate
certbot certonly --standalone -d yudai.app -d www.yudai.app

# Copy certificates to project directory
cp /etc/letsencrypt/live/yudai.app/fullchain.pem /home/yudai/yudai-app/ssl/
cp /etc/letsencrypt/live/yudai.app/privkey.pem /home/yudai/yudai-app/ssl/

# Set proper permissions
chown -R yudai:yudai /home/yudai/yudai-app/ssl
chmod 600 /home/yudai/yudai-app/ssl/*
```

## Step 5: DNS Configuration

### 5.1 Configure GoDaddy DNS Records
In your GoDaddy DNS management panel, add these records:

**A Records:**
- `yudai.app` → `YOUR_VULTR_SERVER_IP`
- `www.yudai.app` → `YOUR_VULTR_SERVER_IP`

**CNAME Records (if needed):**
- `api.yudai.app` → `yudai.app`

**Optional:**
- `*.yudai.app` → `YOUR_VULTR_SERVER_IP` (for subdomains)

### 5.2 Verify DNS Propagation
```bash
# Check DNS propagation
nslookup yudai.app
nslookup www.yudai.app
```

## Step 6: Deploy Application

### 6.1 Build and Start Services
```bash
cd /home/yudai/yudai-app

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

## Step 7: Monitoring and Maintenance

### 7.1 Set up SSL Auto-renewal
```bash
# Create renewal script
cat > /home/yudai/renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/yudai.app/fullchain.pem /home/yudai/yudai-app/ssl/
cp /etc/letsencrypt/live/yudai.app/privkey.pem /home/yudai/yudai-app/ssl/
chown -R yudai:yudai /home/yudai/yudai-app/ssl
chmod 600 /home/yudai/yudai-app/ssl/*
docker-compose -f /home/yudai/yudai-app/docker-compose.prod.yml restart nginx
EOF

chmod +x /home/yudai/renew-ssl.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 12 * * * /home/yudai/renew-ssl.sh") | crontab -
```

### 7.2 Set up Log Rotation
```bash
# Create log rotation config
cat > /etc/logrotate.d/yudai << 'EOF'
/home/yudai/yudai-app/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 yudai yudai
    postrotate
        docker-compose -f /home/yudai/yudai-app/docker-compose.prod.yml restart nginx
    endscript
}
EOF
```

### 7.3 Set up Backup Script
```bash
cat > /home/yudai/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/yudai/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker exec yudai-db pg_dump -U yudai_user yudai_db > $BACKUP_DIR/db_backup_$DATE.sql

# Backup application files
tar -czf $BACKUP_DIR/app_backup_$DATE.tar.gz -C /home/yudai yudai-app

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
EOF

chmod +x /home/yudai/backup.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /home/yudai/backup.sh") | crontab -
```

## Step 8: Testing Your Deployment

### 8.1 Test Frontend
- Visit `https://yudai.app`
- Verify the application loads correctly
- Test all major functionality

### 8.2 Test Backend API
```bash
# Test API endpoints
curl -X GET https://yudai.app/api/health
curl -X GET https://yudai.app/api/your-endpoint
```

### 8.3 Test SSL Certificate
```bash
# Check SSL certificate
openssl s_client -connect yudai.app:443 -servername yudai.app
```

## Troubleshooting

### Common Issues:

1. **DNS not resolving**: Wait 24-48 hours for DNS propagation
2. **SSL certificate issues**: Check if domain is pointing to correct IP
3. **Docker build failures**: Check logs with `docker-compose logs`
4. **Database connection issues**: Verify environment variables
5. **Frontend not loading**: Check nginx configuration and logs

### Useful Commands:
```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f [service_name]

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Update application
cd /home/yudai/yudai-app
git pull
docker-compose -f docker-compose.prod.yml up -d --build
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