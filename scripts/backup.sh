#!/usr/bin/env bash
# ==============================================================================
# 🌾 Khoosheh (خوشه) — Instant Terminal Backup Trigger
# ==============================================================================
set -e

echo "Triggering immediate Khoosheh backup via local API..."
curl -s -X POST http://127.0.0.1:2099/api/backup -H "Content-Type: application/json"
echo ""
