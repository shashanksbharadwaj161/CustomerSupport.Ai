# ShaOn Voice AI - runbook

Two paths from clone to first call:
- **Path A** - Windows PC with WSL2 and an NVIDIA GPU: everything local, all five languages (GPU engines).
- **Path B** - Kaggle only (no usable local GPU): the app runs on your PC in the CPU profile (English and Japanese fully;
  Hindi with an unrated CPU voice; Bengali/Kannada text replies until the GPU engines run), and the M0 bake-off runs on a free Kaggle GPU.

What costs money: only the Anthropic API (DEPLOY.md, $0 rule). Everything else here is free.

You need: an Anthropic API key (console.anthropic.com; set a monthly limit there), a free Hugging Face account
(two AI4Bharat models are gated), Chrome or Edge, about 40 GB free disk for all models (estimate).

---------------------------------------------------------------------------------------------------

## Path A - Windows + WSL2 + NVIDIA GPU

### A1. WSL2 and the GPU (once)
1. Windows: install the latest NVIDIA driver for your GPU from nvidia.com (it includes WSL support).
   Do NOT install a Linux NVIDIA driver inside WSL.
2. PowerShell as Administrator:
   ```powershell
   wsl --install -d Ubuntu-24.04
   ```
   Reboot, open "Ubuntu 24.04", create your Linux user.
3. Recommended for WebRTC from the Windows browser: enable mirrored networking. Create `C:\Users\<you>\.wslconfig`:
   ```ini
   [wsl2]
   networkingMode=mirrored
   ```
   then in PowerShell: `wsl --shutdown` and reopen Ubuntu. (Without it, use the WebSocket transport - see Troubleshooting.)
4. In Ubuntu, check the GPU is visible:
   ```bash
   nvidia-smi
   ```

### A2. System packages (Ubuntu, once)
```bash
sudo apt update && sudo apt install -y git curl build-essential ffmpeg espeak-ng python3.12 python3.12-venv python3.12-dev
```
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
```
Close and reopen the terminal, then:
```bash
nvm install 22
```

### A3. Get the code (inside the Linux filesystem, not /mnt/c - much faster)
```bash
cd ~ && git clone https://github.com/shashanksbharadwaj161/CustomerSupport.Ai.git shaon && cd shaon
```
```bash
git checkout claude/sweet-ptolemy-7qza59
```

### A4. Python environment
```bash
python3.12 -m venv .venv && source .venv/bin/activate && pip install -U pip
```
PyTorch with CUDA (pick the index that matches `nvidia-smi` "CUDA Version"; cu128 works with recent drivers):
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
```
The app, the CPU-capable engines, embeddings and tests:
```bash
pip install -e ".[app,stt-whisper,tts-kokoro,retrieval,dev]"
```
faster-whisper on the GPU needs cuBLAS 12 + cuDNN 9 libraries:
```bash
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```
```bash
echo 'export LD_LIBRARY_PATH=$(python -c "import os,nvidia.cublas.lib,nvidia.cudnn.lib as c;print(os.path.dirname(nvidia.cublas.lib.__file__)+\":\"+os.path.dirname(c.__file__))"):$LD_LIBRARY_PATH' >> .venv/bin/activate && source .venv/bin/activate
```
Japanese dictionary for Kokoro, and the browser used by the crawler (JS pages) and the tests:
```bash
python -m unidic download
```
```bash
playwright install --with-deps chromium
```

### A5. GPU engines for Hindi, Bengali, Kannada
```bash
pip install -e ".[stt-indic,tts-parler]"
```
OmniVoice is optional and DEMO ONLY (CC-BY-NC weights, never commercial):
```bash
pip install -e ".[tts-omnivoice]"
```
If pip reports a dependency conflict between these groups, keep `stt-indic` + `tts-parler` (the commercially usable
product track) in the app environment and skip OmniVoice. Status of these engines in this repo: adapters complete,
**never run by the developer** (no GPU) - Settings > Engines shows any load error with the exact message.

### A6. Hugging Face token (gated models)
1. Log in at huggingface.co, open and click "Agree" on both pages:
   `https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual` and `https://huggingface.co/ai4bharat/indic-parler-tts`.
2. Create a read token at `https://huggingface.co/settings/tokens`, then:
```bash
huggingface-cli login
```

### A7. Check the machine and download models
```bash
python scripts/check_hardware.py
```
It should say `decision: local` (NVIDIA, >= 12 GB VRAM). Otherwise use Path B for the bake-off.
```bash
scripts/download_models.sh
```
```bash
python scripts/doctor.py
```
Everything you plan to demo should be PASS. PENDING lines say exactly what to do.

### A8. Start and first call
```bash
scripts/start.sh
```
1. In Windows Chrome open `http://localhost:8000`. The yellow banner lists what is still missing.
2. Settings > Anthropic API key: paste the key, Save, press **Test key** (one tiny call). Set the spend cap (default $10).
   The key is stored encrypted in `data/` and is never shown again (last 4 characters only).
3. Live Call > agent "Lotus Bay Bank support" > Start call > allow the microphone. Ask:
   "What time does your branch open on Saturday?" then switch to Hindi, Bengali, Kannada or Japanese.
4. The telemetry strip shows STT, language ID, LLM first text and **first audio** in ms for each turn.

### A9. Measure visuals vs latency on YOUR GPU (DESIGN.md section 8)
```bash
CASES="en_question:smallwebrtc:off en_question:smallwebrtc:lite en_question:smallwebrtc:full en_question:websocket:full" tests/e2e/run_e2e.sh
```
Copy the first-audio numbers into `design/perf.md` (the numbers there are from a GPU-less VM). Choose the default tier from them.

---------------------------------------------------------------------------------------------------

## Path B - Kaggle only (no usable local GPU)

1. On your PC (Linux, macOS or WSL2 without GPU): steps A2-A4 without the CUDA lines:
   ```bash
   python3.12 -m venv .venv && source .venv/bin/activate && pip install -U pip
   ```
   ```bash
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
   ```
   ```bash
   pip install -e ".[app,stt-whisper,tts-kokoro,retrieval,dev]" && python -m unidic download && playwright install --with-deps chromium
   ```
2. `scripts/download_models.sh whisper kokoro bge` then `scripts/start.sh`. The app uses the CPU profile automatically
   (Whisper small + Kokoro): English and Japanese are verified end to end on CPU; Hindi speaks with Kokoro's Hindi voice
   (not yet rated by a native speaker); Bengali and Kannada replies are shown as text with a "no speech voice yet" note.
3. Run the M0 bake-off on Kaggle (free GPU, about 30 h/week): follow `eval/kaggle_m0.md` exactly. Download `m0_out.zip`,
   unzip into `eval/out/`, then on your PC run the Claude step and the report (section M0 below).
4. Expect slower turns on CPU (about 4-6 s to first audio in our VM with effects Lite/Off). Set Effects to **Off** or **Lite**
   for demos on CPU-only machines (design/perf.md: Full made the pipeline 5-7x slower without a GPU).

---------------------------------------------------------------------------------------------------

## M0 - recordings, ratings, results (both paths)

1. Native-speaker review of the test lines: edit `eval/lines/build_lines.py`, run it, sign off in `eval/lines/REVIEW.md`.
2. Record (consenting speakers only):
   ```bash
   python -m http.server 8090
   ```
   Open `http://localhost:8090/eval/tools/recorder.html`, pick the language, record each line, save files into `eval/audio/`.
3. GPU runs (local Path A, or Kaggle Path B): STT, language ID, switching, TTS - commands in `eval/README.md`.
   Then: `python -m eval.runners.run_lid --model large-v3` and copy the recommended threshold / prev_bias into
   `agent/engines.json` -> `lid`.
4. Claude quality (costs a few cents): `python -m eval.runners.run_llm` (quick set first), red-team with Claude:
   `python -m eval.runners.run_redteam --real --max-usd 0.30`.
5. Native ratings: `http://localhost:8090/eval/tools/rater.html` (blind, shuffled). Save CSVs to `eval/ratings/`.
6. `python -m eval.make_report` -> `eval/results.md`; `python -m eval.make_eval_report` -> `docs/EVAL_REPORT.md`.
   Write the engine decisions in `eval/decisions.md`.

---------------------------------------------------------------------------------------------------

## Switching engines per language

All selection lives in `agent/engines.json` (restart the app after editing):
- `stt` (used when a CUDA GPU is present) and `stt_cpu` (no GPU): engine + options per language, e.g.
  ```json
  "hi": {"engine": "indicconformer", "options": {"decoding": "rnnt"}, "fallback": "faster-whisper"}
  ```
  Use `{"engine": "faster-whisper", "options": {"model": "large-v3"}}` to put a language on Whisper instead.
  If an engine fails to load, that turn falls back to Whisper automatically and the transcript says so.
- `lid`: language-ID threshold and previous-language bias (from `run_lid`).
- `default_voices`: the voice used per language when an agent has no override; `cpu_fallback_voices`: used when that
  voice's engine is unavailable on this machine.
Per agent (no file editing): Studio > Voices: persona set (`warm_female`, `calm_male`, `energetic_young`, `formal_senior`,
or `one_voice_demo` = OmniVoice, demo only) and per-language overrides; Studio > Languages: Sonnet 5.5 per language.
During a call: the voice dock switches the voice from the next sentence; the language override pins a language.
Voice catalog files: `voices/catalog.json`, `voices/bakeoff_voices.json`; Settings > Voices previews any voice.

---------------------------------------------------------------------------------------------------

## Remote demo through a tunnel ($0)
`deploy/tunnel.sh` + `deploy/CHECKLIST.md` (password required, key locked, polling instead of SSE, WebSocket transport).

## Everyday commands
| What | Command |
|---|---|
| Start | `scripts/start.sh` |
| Checklist of what is missing | `python scripts/doctor.py` |
| All checks (fake LLM, no spend) | `scripts/test_all.sh` |
| Unit tests only | `pytest -q` |
| Silent walkthrough video | `cd web && node scripts/record_demo.mjs http://127.0.0.1:8000 ../tests/e2e/audio/en_question.wav` |
| Scripted LLM, no key | `SHAON_LLM_PROVIDER=fake scripts/start.sh` (banner says so) |

## Troubleshooting
| Symptom | Fix |
|---|---|
| WebRTC call connects but no audio (WSL2) | Enable mirrored networking (A1.3), or use Transport: WebSocket on the Live Call page (`/call/?transport=websocket`) |
| `Could not load library libcudnn_ops.so.9` | A4 cuDNN step; re-`source .venv/bin/activate` |
| Kokoro: `No virtual environment found` / spaCy download error | `pip install -e ".[tts-kokoro]"` (it bundles `en_core_web_sm`) |
| Kokoro Japanese: MeCab / `mecabrc` error | `python -m unidic download` |
| Python 3.13 install fails for kokoro | use Python 3.12 (`python3.12 -m venv .venv`) |
| 401 / gated repo for ai4bharat models | A6: accept both model pages, `huggingface-cli login` |
| Banner "spend cap reached" | Settings > Spend cap; check the Anthropic Console |
| Slow replies on a laptop | Effects Off; one warm-up call; check `nvidia-smi` shows the models on the GPU |
| Crawl shows "robots.txt disallows" | That page is excluded by the site's robots.txt (by design) |
