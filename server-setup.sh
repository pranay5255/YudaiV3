#!/bin/bash

# Vultr Server Setup Script for Yudaiv3
# Run this as root on your Vultr instance

set -e

echo "🔧 Setting up Vultr server for Yudaiv3..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

print_status "Updating system packages..."
apt update && apt upgrade -y

print_status "Installing essential packages..."
apt install -y curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release ufw

print_status "Installing Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

print_status "Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

print_status "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

print_status "Installing pnpm..."
npm install -g pnpm

print_status "Installing Certbot..."
apt install -y certbot python3-certbot-nginx

print_status "Creating application user..."
useradd -m -s /bin/bash yudai
usermod -aG docker yudai

print_status "Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw --force enable

print_status "Creating application directory..."
mkdir -p /home/yudai/yudai-app
chown -R yudai:yudai /home/yudai/yudai-app

print_status "Setting up log rotation..."
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

print_status "Setting up backup script..."
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

print_status "Setting up SSL renewal script..."
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

print_status "Setting up cron jobs..."
(crontab -l 2>/dev/null; echo "0 12 * * * /home/yudai/renew-ssl.sh") | crontab -
(crontab -l 2>/dev/null; echo "0 2 * * * /home/yudai/backup.sh") | crontab -

print_status "Setting up systemd service for auto-restart..."
cat > /etc/systemd/system/yudai-app.service << 'EOF'
[Unit]
Description=Yudaiv3 Application
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/yudai/yudai-app
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
User=yudai
Group=yudai

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable yudai-app.service

print_status "🎉 Server setup completed!"
print_status ""
print_status "Next steps:"
print_status "1. Switch to yudai user: su - yudai"
print_status "2. Clone your repository: git clone YOUR_REPO_URL /home/yudai/yudai-app"
print_status "3. Copy configuration files to /home/yudai/yudai-app/"
print_status "4. Create .env file from .env.example"
print_status "5. Set up SSL certificates: sudo certbot certonly --standalone -d yudai.app -d www.yudai.app"
print_status "6. Copy SSL certificates to /home/yudai/yudai-app/ssl/"
print_status "7. Run deployment: cd /home/yudai/yudai-app && ./deploy.sh"
print_status ""
print_status "Useful commands:"
print_status "- View logs: docker-compose -f docker-compose.prod.yml logs -f"
print_status "- Restart services: docker-compose -f docker-compose.prod.yml restart"
print_status "- Check status: docker-compose -f docker-compose.prod.yml ps"
print_status "- Update application: git pull && ./deploy.sh"