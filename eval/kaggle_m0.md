# Running M0 on a free Kaggle GPU notebook ($0 plan)

Use this when `scripts/check_hardware.py` says `decision: kaggle`. Batch runs only, never live calls.
Free quota is roughly 30 GPU-hours a week with 9-12 hour sessions: check your Kaggle account page
for the real number. Colab free is the backup (same commands; no SSH or web UIs there).

1. Kaggle account: verify your phone number (needed for GPU and internet in notebooks).
2. New notebook -> Settings: Accelerator `GPU T4 x2` (or P100), Internet `On`.
3. Secrets (Add-ons -> Secrets): `HF_TOKEN` (for the gated ai4bharat models; accept their terms on
   huggingface.co first). Do NOT add the Anthropic key: the Claude step runs on your PC.
4. Recordings: upload `eval/audio/` as a private Kaggle Dataset (e.g. `shaon-m0-audio`) and attach it.
5. Code: clone the repo in a cell (private repo: add a read-only GitHub token as a Kaggle secret,
   or upload the repo as a private Dataset instead).

```python
from kaggle_secrets import UserSecretsClient
import os
os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
```
```bash
!git clone https://github.com/<owner>/<repo>.git shaon && cd shaon && git checkout <branch>
%cd shaon
!mkdir -p eval/audio && cp /kaggle/input/shaon-m0-audio/* eval/audio/
!apt-get -qq install -y espeak-ng ffmpeg > /dev/null
!python scripts/check_hardware.py
!pip -q install -e ".[stt-whisper]" && python -m eval.runners.run_stt --engine faster-whisper --model large-v3
!python -m eval.runners.run_stt --engine faster-whisper --model turbo
!python -m eval.runners.run_lid --model large-v3
!pip -q install -e ".[stt-indic]" && python -m eval.runners.run_stt --engine indicconformer --decoding rnnt
!python -m eval.runners.run_stt --engine indicconformer --decoding ctc
!pip -q install -e ".[tts-kokoro]" ".[tts-parler]" && python -m eval.runners.run_tts --engines kokoro indic-parler
!pip -q install -e ".[tts-omnivoice]" && python -m eval.runners.run_tts --engines omnivoice
!pip -q install -e ".[retrieval]" && python -m eval.runners.run_retrieval
!cd eval && zip -qr /kaggle/working/m0_out.zip out
```

6. Download `m0_out.zip` from the notebook's Output tab, unzip into your local `eval/out/`, then on
   your PC run the Claude step and `python -m eval.make_report`.

Notes
- Kaggle numbers are T4/P100 numbers, not your PC's: results.md shows the host. Live-demo latency
  must be re-measured on the machine that runs the demo.
- If two engine groups conflict in one environment, restart the session between groups.
