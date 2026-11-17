#!/usr/bin/env bash
# Thin wrapper: the same launcher as Windows (scripts/share.ps1) under PowerShell 7 on macOS/Linux.
#   scripts/share.sh [-Port 8000] [-MaxCalls 2] [-MaxCallSeconds 300]
# Needs pwsh (macOS: brew install powershell; Linux: see learn.microsoft.com/powershell) and cloudflared.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v pwsh >/dev/null || { echo "PowerShell 7 (pwsh) is required: macOS 'brew install powershell', Linux: install the powershell package." >&2; exit 1; }
exec pwsh -NoProfile -File scripts/share.ps1 "$@"
