# ShaOn two-speaker website recordings

Recorded on a CPU-only cloud machine (4 cores, no GPU): Xvfb + PulseAudio + headed Chromium on the real /call/ page + ffmpeg (screen and audio in one process, unedited). shaon-conversation-xx.mp4 is a labelled 30-s EXCERPT (one contiguous cut); the -full.mp4 file is the whole unedited call. First audio = customer stopped speaking -> first agent audio played in the browser. Agent replies: SCRIPTED test provider (no Anthropic key on this machine): real Claude conversations are PENDING.

| Language | Result | Agent replies | Agent voice | Customer voice | STT | First audio (ms) | Audio errors | Full duration | 30-s excerpt |
|---|---|---|---|---|---|---|---|---|---|
| English | PASS | scripted (scripted) | kokoro_en_heart (kokoro) | kokoro_en_michael | faster-whisper:small | [6509, 7074] | 0 | 52.76 s | 2.3-32.3 s |
| Hindi | PASS | scripted (scripted) | mithi_hi_ahana (mithi) | kokoro_hi_omega | mms | [8290, 8441] | 0 | 59.16 s | 2.2-32.2 s |
| Bengali | PASS | scripted (scripted) | mithi_bn_ahana (mithi) | mithi_bn_nakul | mms | [8238, 8137] | 0 | 57.8 s | 3.1-33.1 s |
| Kannada | PASS | scripted (scripted) | mithi_kn_ahana (mithi) | mithi_kn_nakul | mms | [8912, 8739] | 0 | 61.8 s | 2.4-34.1 s |
| Japanese | PASS | scripted (scripted) | kokoro_ja_alpha (kokoro) | kokoro_ja_kumo | faster-whisper:small | [6399, 7963] | 0 | 58.92 s | 3.5-33.5 s |

All languages passed every check.
