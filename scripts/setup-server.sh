#!/bin/bash

# YudaiV3 Server Setup Script
# Run this script on your Vultr instance to set up the production environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run this script as root (use sudo)"
    exit 1
fi

log_info "Starting YudaiV3 server setup..."

# Update system
log_info "Updating system packages..."
apt update && apt upgrade -y

# Install essential packages
log_info "Installing essential packages..."
apt install -y curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release

# Install Docker
log_info "Installing Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Install Docker Compose
log_info "Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Caddy
log_info "Installing Caddy..."
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy

# Create application directory
log_info "Creating application directory..."
mkdir -p /opt/yudai
chown $SUDO_USER:$SUDO_USER /opt/yudai

# Configure firewall
log_info "Configuring firewall..."
ufw allow ssh
ufw allow 80
ufw allow 443
ufw allow 8000
ufw --force enable

# Create log directory for Caddy
log_info "Setting up Caddy logging..."
mkdir -p /var/log/caddy
chown caddy:caddy /var/log/caddy

# Create log rotation configuration
log_info "Setting up log rotation..."
cat > /etc/logrotate.d/yudai << 'EOF'
/var/log/caddy/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 caddy caddy
    postrotate
        systemctl reload caddy
    endscript
}
EOF

# Install fail2ban for security
log_info "Installing fail2ban..."
apt install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# Set up automatic security updates
log_info "Setting up automatic security updates..."
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# Generate SSH key for GitHub Actions
log_info "Generating SSH key for GitHub Actions..."
if [ ! -f /home/$SUDO_USER/.ssh/github_actions ]; then
    sudo -u $SUDO_USER ssh-keygen -t ed25519 -C "github-actions@yudai.app" -f /home/$SUDO_USER/.ssh/github_actions -N ""
    cat /home/$SUDO_USER/.ssh/github_actions.pub >> /home/$SUDO_USER/.ssh/authorized_keys
    log_success "SSH key generated for GitHub Actions"
    log_warning "Copy the private key to GitHub secret VULTR_SSH_KEY:"
    echo "=== PRIVATE KEY ==="
    cat /home/$SUDO_USER/.ssh/github_actions
    echo "=== END PRIVATE KEY ==="
else
    log_info "SSH key already exists"
fi

# Create monitoring script
log_info "Creating monitoring script..."
cat > /opt/yudai/monitor.sh << 'EOF'
#!/bin/bash

# Simple monitoring script
echo "=== YudaiV3 System Status ==="
echo "Date: $(date)"
echo ""

echo "=== Container Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

echo "=== Service Health ==="
if curl -f https://yudai.app > /dev/null 2>&1; then
    echo "✅ Frontend: OK"
else
    echo "❌ Frontend: DOWN"
fi

if curl -f https://api.yudai.app/health > /dev/null 2>&1; then
    echo "✅ Backend: OK"
else
    echo "❌ Backend: DOWN"
fi

if docker exec yudai_db_prod pg_isready -U yudai_user -d yudai_db > /dev/null 2>&1; then
    echo "✅ Database: OK"
else
    echo "❌ Database: DOWN"
fi

echo ""
echo "=== Caddy Status ==="
systemctl status caddy --no-pager -l
echo ""

echo "=== Disk Usage ==="
df -h /opt/yudai
echo ""

echo "=== Memory Usage ==="
free -h
EOF

chmod +x /opt/yudai/monitor.sh

# Create backup script
log_info "Creating backup script..."
cat > /opt/yudai/backup.sh << 'EOF'
#!/bin/bash

# Backup script
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker exec yudai_db_prod pg_dump -U yudai_user yudai_db > $BACKUP_DIR/db_backup_$DATE.sql

# Backup application files
tar -czf $BACKUP_DIR/app_backup_$DATE.tar.gz -C /opt yudai

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
EOF

chmod +x /opt/yudai/backup.sh

log_success "Server setup completed!"
log_info ""
log_info "Next steps:"
log_info "1. Clone your repository: cd /opt && git clone https://github.com/yourusername/YudaiV3.git yudai"
log_info "2. Copy environment file: cp env.prod.example .env.prod"
log_info "3. Edit environment file: nano .env.prod"
log_info "4. Copy Caddyfile: cp config/Caddyfile /etc/caddy/"
log_info "5. Reload Caddy: systemctl reload caddy"
log_info "6. Run deployment: ./deploy.sh"
log_info ""
log_info "Don't forget to:"
log_info "- Set up DNS records in GoDaddy"
log_info "- Add GitHub secrets for CI/CD"
log_info "- Test the deployment" 