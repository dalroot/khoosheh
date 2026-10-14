#!/usr/bin/env bash
# ==============================================================================
# 🌾 Khoosheh (خوشه) — Automated Installer & Multi-Panel Backup Engine
# Repository: https://github.com/dalroot/khoosheh
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
cat << "BANNER"
  🌾  _  ___                     _          _     
     | |/ / |__   ___   ___  ___| |__   ___| |__  
     | ' /| '_ \ / _ \ / _ \/ __| '_ \ / _ \ '_ \ 
     | . \| | | | (_) | (_) \__ \ | | |  __/ | | |
     |_|\_\_| |_|\___/ \___/|___/_| |_|\___|_| |_|
     Universal Multi-Panel Backup & Restore Engine
BANNER
echo -e "${NC}"

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}❌ Please run as root (sudo bash install.sh)${NC}"
  exit 1
fi

echo -e "${BLUE}▶ [1/5] Updating packages and installing prerequisites...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-pip p7zip-full sqlite3 curl tar > /dev/null

echo -e "${BLUE}▶ [2/5] Setting up installation directories...${NC}"
mkdir -p /opt/khoosheh
mkdir -p /opt/khoosheh/ssl
mkdir -p /var/backups/khoosheh
chmod 755 /opt/khoosheh
chmod 700 /var/backups/khoosheh

echo -e "${BLUE}▶ [3/5] Installing Khoosheh engine files...${NC}"
REPO_RAW="https://raw.githubusercontent.com/dalroot/khoosheh/main"

# Download latest engine files from GitHub repository
curl -sSL "$REPO_RAW/server.py" -o /opt/khoosheh/server.py
curl -sSL "$REPO_RAW/khoosheh.service" -o /etc/systemd/system/khoosheh.service
curl -sSL "$REPO_RAW/install.sh" -o /opt/khoosheh/install.sh
curl -sSL "$REPO_RAW/config.example.json" -o /opt/khoosheh/config.example.json

chmod +x /opt/khoosheh/server.py
chmod +x /opt/khoosheh/install.sh

# Initialize config if not present
if [ ! -f /opt/khoosheh/config.json ]; then
  if [ -f /opt/khoosheh/config.example.json ]; then
    cp /opt/khoosheh/config.example.json /opt/khoosheh/config.json
  else
    cat << 'CFG' > /opt/khoosheh/config.json
{
  "bot_token": "",
  "admin_chat_id": 0,
  "web_port": 2099,
  "ssl_port": 2098,
  "admin_username": "admin",
  "admin_password_hash": "",
  "auth_tokens": [],
  "backup_password": "",
  "interval_hours": 6,
  "auto_schedule": true,
  "backup_type": "full",
  "keep_local_count": 15,
  "custom_panels": [],
  "servers": [],
  "last_backup_at": "",
  "last_status": "آماده به کار",
  "last_error": ""
}
CFG
  fi
  chmod 600 /opt/khoosheh/config.json
fi

echo -e "${BLUE}▶ [4/5] Configuring systemd service...${NC}"
if [ ! -f /etc/systemd/system/khoosheh.service ]; then
  cat << 'UNIT' > /etc/systemd/system/khoosheh.service
[Unit]
Description=Khoosheh Universal Multi-Panel Backup & Web Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/khoosheh
ExecStart=/usr/bin/python3 /opt/khoosheh/server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
fi

systemctl daemon-reload
systemctl enable khoosheh
systemctl restart khoosheh

echo -e "${BLUE}▶ [5/5] Checking service status...${NC}"
sleep 2
if systemctl is-active --quiet khoosheh; then
  echo -e "${GREEN}✔ Service khoosheh is running successfully!${NC}"
else
  echo -e "${YELLOW}⚠️ Service started, please check: systemctl status khoosheh${NC}"
fi

# Detect Server IP
SERVER_IP=$(curl -s -m 3 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}  🌾 Khoosheh Multi-Panel Backup Engine installed successfully!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo -e "  🌐 ${CYAN}Web Dashboard:${NC}    http://${SERVER_IP}:2099"
echo -e "  🔑 ${CYAN}Initial Setup:${NC}    Open the dashboard in your browser to configure admin credentials."
echo -e "  📁 ${CYAN}Installation Dir:${NC} /opt/khoosheh/"
echo -e "  📦 ${CYAN}Backups Storage:${NC}  /var/backups/khoosheh/"
echo -e "  🔄 ${CYAN}Service Control:${NC}  systemctl restart|status|stop khoosheh"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
