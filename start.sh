#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  ALFA_CORE v2.0 - Quick Start
# ═══════════════════════════════════════════════════════════════

if [ ! -d "venv" ]; then
    echo "[!] Run ./install.sh first!"
    exit 1
fi

source venv/bin/activate
echo ""
echo " Starting ALFA_CORE..."
echo " Press Ctrl+C to stop"
echo ""
python -m alfa_core "$@"
