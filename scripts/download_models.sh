#!/usr/bin/env bash
# Download M0 model weights into the Hugging Face cache (or $HF_HOME). Free; needs disk space.
# Gated models (ai4bharat/*): log in at huggingface.co, accept the model terms, then
# export HF_TOKEN=... before running. Never commit weights (see .gitignore).
#
#   scripts/download_models.sh            # everything
#   scripts/download_models.sh whisper indic-stt
set -euo pipefail

declare -A REPOS=(
  [whisper]="Systran/faster-whisper-large-v3 mobiuslabsgmbh/faster-whisper-large-v3-turbo"
  [indic-stt]="ai4bharat/indic-conformer-600m-multilingual"
  [parler]="ai4bharat/indic-parler-tts"
  [kokoro]="hexgrad/Kokoro-82M"
  [omnivoice]="k2-fsa/OmniVoice"   # DEMO ONLY: CC-BY-NC weights
  [bge]="BAAI/bge-m3"
)
groups=("$@")
[ ${#groups[@]} -eq 0 ] && groups=(whisper indic-stt parler kokoro omnivoice bge)

for g in "${groups[@]}"; do
  for repo in ${REPOS[$g]:?unknown group $g}; do
    echo "== $repo"
    python - "$repo" <<'PY'
import sys
from huggingface_hub import snapshot_download
repo = sys.argv[1]
try:
    print(snapshot_download(repo))
except Exception as e:  # gated or network error: report and continue
    print(f"FAILED {repo}: {type(e).__name__}: {e}")
PY
  done
done
