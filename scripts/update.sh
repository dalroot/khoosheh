#!/usr/bin/env bash
# ==============================================================================
# 🌾 Khoosheh (خوشه) — Instant Updater Script
# ==============================================================================
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}▶ Updating Khoosheh to latest release...${NC}"
REPO_RAW="https://raw.githubusercontent.com/dalroot/khoosheh/main"

mkdir -p /opt/khoosheh/web
curl -sSL "$REPO_RAW/server.py" -o /opt/khoosheh/server.py
curl -sSL "$REPO_RAW/web/index.html" -o /opt/khoosheh/web/index.html 2>/dev/null || true
curl -sSL "$REPO_RAW/install.sh" -o /opt/khoosheh/install.sh
chmod +x /opt/khoosheh/server.py /opt/khoosheh/install.sh

python3 -m py_compile /opt/khoosheh/server.py
systemctl restart khoosheh

echo -e "${GREEN}✔ Khoosheh updated and restarted successfully!${NC}"
systemctl status khoosheh --no-pager
