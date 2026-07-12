#!/bin/bash
# ============================================================
# AI Monitor - One-Click Deployment Script
# Target: Ubuntu 22.04+ / Debian 12+ with systemd
# Usage:  sudo bash deploy/deploy.sh
# ============================================================
set -euo pipefail

PROJECT_DIR="/opt/monitor"
REPO_URL="https://github.com/ht-yun/monitor.git"
BRANCH="main"
SERVICE_NAME="ai-monitor"
NGINX_SITE="ai-monitor"
LOG_DIR="/var/log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash deploy/deploy.sh"
fi

info "=== AI Monitor Deployment ==="

# ===== 1. System dependencies =====
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx curl

# ===== 2. Clone / pull code =====
if [ -d "$PROJECT_DIR/.git" ]; then
    info "Updating existing installation..."
    cd "$PROJECT_DIR"
    git stash || true
    git pull origin "$BRANCH"
else
    info "Cloning repository..."
    git clone -b "$BRANCH" "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# ===== 3. Create system user =====
if ! id -u monitor &>/dev/null; then
    useradd -r -s /bin/false -d "$PROJECT_DIR" monitor
    info "Created system user: monitor"
fi
chown -R monitor:monitor "$PROJECT_DIR"

# ===== 4. Python virtual environment =====
info "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
chown -R monitor:monitor .venv
sudo -u monitor bash -c 'source .venv/bin/activate && pip install --upgrade pip -q && pip install -r ai_monitor/requirements.txt -q'
info "Dependencies installed"

# ===== 5. Environment file =====
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp deploy/.env.production "$PROJECT_DIR/.env"
    chown monitor:monitor "$PROJECT_DIR/.env"
    chmod 600 "$PROJECT_DIR/.env"
    warn "!!! Please edit $PROJECT_DIR/.env with your secrets !!!"
    warn "    Then re-run this script to start the service."
    exit 0
fi

# ===== 6. Initialize database =====
info "Initializing database..."
sudo -u monitor bash -c 'cd ai_monitor && source ../.venv/bin/activate && python -c "
import asyncio
from ai_monitor.store.database import init_db
asyncio.run(init_db())
print(\"Database initialized\")
"'

# ===== 7. Install systemd service =====
info "Installing systemd service..."
cp deploy/ai-monitor.service /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME
info "Service started"

# ===== 8. Install nginx config =====
info "Installing nginx configuration..."
cp deploy/nginx.conf /etc/nginx/sites-available/$NGINX_SITE
if [ ! -f "/etc/nginx/sites-enabled/$NGINX_SITE" ]; then
    ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/$NGINX_SITE
fi
nginx -t && systemctl reload nginx
info "Nginx reloaded"

# ===== 9. Setup SSL (optional) =====
DOMAIN=""
if [ -f "$PROJECT_DIR/.domain" ]; then
    DOMAIN=$(cat "$PROJECT_DIR/.domain")
fi
if [ -n "$DOMAIN" ] && [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    info "Attempting Let'"'"'s Encrypt SSL for $DOMAIN..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN" || true
fi

# ===== 10. Verify =====
sleep 3
if systemctl is-active --quiet $SERVICE_NAME; then
    info "Service is running!"
    systemctl status $SERVICE_NAME --no-pager -l | head -15
else
    warn "Service may have failed to start. Check: journalctl -u $SERVICE_NAME -n 50"
fi

info "=== Deployment complete! ==="
info "Check:  systemctl status $SERVICE_NAME"
