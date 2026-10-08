#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
# certifi = trusted certificates for HTTPS (python.org Python on Mac doesn't use the system ones)
python3 -c "import certifi" 2>/dev/null || python3 -m pip install --user --quiet certifi 2>/dev/null || true
python3 admin/admin.py
