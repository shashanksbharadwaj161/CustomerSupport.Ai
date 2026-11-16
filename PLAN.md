# ShaOn Voice AI - detailed plan (v3)

A local web app where you configure any kind of voice agent (bank support, tourism, anything), drop a website link to give it full context, then talk to it live in Bengali, Hindi, Kannada, Japanese or English, switching language freely between turns. Fully working demo for a client. UI direction is in DESIGN.md.

Status key used below: VERIFIED = read in the source's own docs/README; CLAIMED = vendor or page claim, not tested; TEST = must be measured in M0.

---------------------------------------------------------------------

## 1. Scope

In scope (MVP demo):
- Browser-based live voice calls (WebRTC), 5 languages, per-turn switching.
- Agent Studio: agent type, persona, response style, guardrails, languages, voices, knowledge, versions.
- Website URL -> crawl -> knowledge base -> agent answers with full site context.
- Voice picker with preview per language, persona sets, live voice switching.
- Call logs with transcripts, language per turn, latency, guardrail triggers.
- Spectacular futuristic UI (DESIGN.md).

Out of scope for now: real phone numbers (Twilio/SIP), login/multi-client accounts, file-upload knowledge, real banking/booking integrations, cloud GPU hosting, mid-sentence language switching (stretch goal).

---------------------------------------------------------------------

## 2. Reference register (every link you gave, plus what I found)

### 2.1 Links you added

| # | Link | What it actually is | Status | How we use it |
|---|---|---|---|---|
| 1 | https://github.com/topics/ai-voice-agent | GitHub topic page, 20 repos listed. Mostly apps; several depend on the OpenAI Realtime API. Frameworks among them: rapidaai/voice-ai, streamcoreai/streamcore-server, slng-ai/unmute. None state spoken-language support. | VERIFIED | Not a base. Browse for ideas only. |
| 2 | https://github.com/zachlatta/freeflow.git | FreeFlow: macOS dictation app, MIT, transcription via OpenAI-compatible APIs (Groq default), local models via Ollama/LM Studio. Not a voice-agent framework. | VERIFIED | Not used. Idea only: OpenAI-compatible endpoint abstraction for STT/LLM. |
| 3 | https://github.com/OpenWhispr/openwhispr.git | OpenWhispr: Electron dictation app, MIT, React 19/TypeScript, whisper.cpp, sherpa-onnx. Not a voice-agent framework. | VERIFIED | Not used. Possible later: sherpa-onnx as a lightweight local ASR runtime. |
| 4 | https://github.com/debpalash/VoiceStudio.git | VoiceStudio: AGPL-3.0 desktop app (cloning, dubbing, dictation, audiobooks). Default engine is OmniVoice. Local API exists but README gives no endpoints. Real-time and telephony not described. | VERIFIED | Listening playground for engines during M0. Do NOT embed (AGPL). |
| 5 | https://github.com/topics/elevenlabs-alternative | 14 repos, mostly apps/wrappers over Kokoro, Piper, F5-TTS, Fish, VoxCPM, MiniMax. None mention Bengali or Japanese. One is a written review. | VERIFIED | No new voice models. Underlying engines are evaluated directly (section 4). |
| 6 | https://github.com/Iamsdt/awesome-bengali-ai | Bengali resource list. Has Bengali ASR (SPRING LAB streaming Zipformer, supports Banglish; Bhashini ASR), Bangla TTS datasets (HF collection), Bengali LLMs (TigerLLM, BanglaLLaMA, etc.). NO Bengali TTS model listed. No licenses listed. | VERIFIED | STT candidates for Bengali, TTS fine-tuning datasets (fallback), LLM names for reference. |
| 7 | https://www.siliconflow.com/articles/best-open-source-llm-for-bengali | Vendor promo for Qwen3-235B-A22B, Llama-3.1-8B, Qwen3-8B. No Bengali benchmark results. | VERIFIED | Ignored for decisions. We use Claude Haiku 5.5 and measure Bengali ourselves. |
| 8 | https://openai.github.io/openai-agents-js/guides/voice-agents/ | OpenAI Agents JS voice guide: RealtimeAgent/RealtimeSession, OpenAI-named WebRTC/WebSocket/SIP transports. OpenAI-specific. | VERIFIED (partial page) | Not used. Not open-source/local. |
| 9 | https://github.com/whobot-ai/awesome-voice-agents | Awesome list: frameworks (Pipecat, LiveKit Agents, TEN, Vocode, Bolna, Speaches...), huggingface/speech-to-speech, Unmute (Kyutai), Smart Turn (23 languages, BSD-2). No Bengali/Japanese in the part read. | VERIFIED (first 100k chars) | Map of options. Smart Turn adopted for end-of-turn detection. |
| 10 | https://github.com/topics/open-source-voice-ai | Only one repo: dograh-hq/dograh, self-hosted Vapi/Retell alternative with workflow builder, MCP, telephony. Languages not stated. | VERIFIED | Revisit after MVP for telephony/workflow ideas. |
| 11 | https://github.com/pipecat-ai/pipecat.git | Pipecat: BSD-2 Python framework for real-time voice agents. STT: Whisper, Moonshine, Sarvam, Soniox, etc. TTS: Kokoro, Piper, XTTS, Fish, Sarvam, etc. LLMs incl. Anthropic, Ollama. Transports incl. SmallWebRTC. | VERIFIED | THE orchestration framework. |

### 2.2 Other sources used (found during research)

| Link | What | Status | Use |
|---|---|---|---|
| https://huggingface.co/ai4bharat/indic-parler-tts | Indic Parler-TTS, Apache-2.0, 0.9B. Bengali 6 speakers, Hindi 4 (Rohit, Divya, Aman, Rani), Kannada 4 (Suresh, Anu, Chetan, Vidya). Voice controlled by text description. Page lists official languages inconsistently. | VERIFIED | Product-track TTS for bn/hi/kn. |
| https://github.com/k2-fsa/OmniVoice | OmniVoice 0.6B, 600+ languages. Code Apache-2.0, WEIGHTS CC-BY-NC. Training hours: en ~206k, ja ~36.9k, bn ~272, kn ~128, hi ~117. Voice cloning needs reference audio (+ transcript in example). Voice design trained on zh/en only. Streaming not mentioned. RTF 0.025 CLAIMED (H100). | VERIFIED | Demo-track TTS for all 5 languages if it passes listening. |
| https://huggingface.co/k2-fsa/OmniVoice | Model card: CC-BY-NC weights, terms prohibit unauthorized cloning/impersonation. | VERIFIED | Licensing rules in CLAUDE.md. |
| https://github.com/AI4Bharat/IndicConformerASR | IndicConformer, MIT, 22 Indian languages, monolingual bn/hi/kn plus a 600M multilingual model. Requires AI4Bharat NeMo fork. Streaming not mentioned. | VERIFIED | Primary STT for bn/hi/kn. |
| https://github.com/huggingface/speech-to-speech | Apache-2.0 local pipeline, swappable stages (--stt, --llm_backend, --tts). Defaults: Silero VAD, Parakeet TDT (25 European languages), Qwen3.5-4B, Qwen3-TTS. Lists OmniVoice (weights CC-BY-NC), Kokoro, MMS TTS as TTS options. OmniVoice emits first audio only after the full utterance. Needs ~24GB VRAM (NVIDIA) or 16GB (Apple Silicon) for defaults. | VERIFIED | M0 spike tool for fast listening tests. |
| https://github.com/QwenLM/Qwen3-TTS | Apache-2.0, 10 languages incl. English and Japanese; no Bengali/Hindi/Kannada. | CLAIMED (secondary sources) | Product-track TTS for ja/en candidate. |
| Kokoro-82M (Hexgrad) | Apache-2.0; English, Japanese, Chinese, Korean. | CLAIMED (secondary source) | Product-track TTS for ja/en candidate, fast. |
| https://github.com/unclecode/crawl4ai | Crawl4AI, Apache-2.0: site -> markdown, deep crawl (BFS/DFS/best-first), JS rendering. robots.txt handling NOT confirmed. | VERIFIED | Website ingestion. |
| https://huggingface.co/BAAI/bge-m3 | BGE-M3 embeddings, MIT, 1024-dim, 8192 tokens, "100+ languages" (Bengali/Hindi/Kannada/Japanese not named on the page). | VERIFIED / TEST for our languages | Embeddings for retrieval. |
| https://github.com/fishaudio/fish-speech | Code Apache-2.0, S1-mini weights CC-BY-NC-SA-4.0. Bengali not listed. | VERIFIED | NOT used (non-commercial, no Bengali). |
| LiveKit Agents, TEN Framework (from your pasted summary) | Alternatives to Pipecat. | CLAIMED | Not used for MVP. Fallback if Pipecat blocks. |
| https://www.unicorn.studio/ , https://gsap.com/standard-license/ , https://threejs.org/ | Design tooling, see DESIGN.md. | VERIFIED | UI. |

---------------------------------------------------------------------

## 3. Architecture

```
 Browser (Next.js)                        Backend (Python)
 +-------------------------+   WebRTC    +-----------------------------------------------+
 | Live Call page          |<==========>| Pipecat pipeline (SmallWebRTC transport)        |
 |  mic, playback,         |  audio      |  VAD (Silero) -> Smart Turn -> language ID     |
 |  AnalyserNode -> visuals|             |  -> STT router (IndicConformer | faster-whisper)|
 +-------------------------+             |  -> guard_in -> Claude Haiku 5.5 (stream,tools)|
 | Agent Studio / Knowledge|   REST/SSE  |  -> guard_out -> sentence splitter             |
 | Voices / Call Logs      |<==========>|  -> TTS router (per language + voice) -> audio |
 +-------------------------+             +-----------------------------------------------+
                                         | FastAPI: profiles, versions, ingest, voices,   |
                                         | logs.  SQLite + Chroma + local files           |
                                         +-----------------------------------------------+
                                                   |  text only
                                                   v
                                            Anthropic API (claude-haiku-5-5)
```

Everything audio stays on the machine. Only text (transcripts, retrieved chunks, prompts) goes to the Anthropic API.

---------------------------------------------------------------------

## 4. Stack decisions

| Layer | Choice | License | Notes |
|---|---|---|---|
| Frontend | Next.js + React + Tailwind | MIT | See DESIGN.md for animation/3D libraries. |
| Backend | Python 3.11+, FastAPI, Pipecat | BSD-2 (Pipecat) | One start script runs web + api + agent. |
| LLM | Claude Haiku 5.5, `claude-haiku-5-5` | API | Key entered in Settings, stored encrypted server-side (CLAUDE.md). Streaming, tool use, prompt caching. Fallback to Sonnet 5.5 (`claude-sonnet-5-5`) per language if TEST shows weak Kannada/Bengali. |
| VAD / turn | Silero VAD + Smart Turn | BSD-2 (Smart Turn) | Confirm Bengali/Hindi/Kannada are among its 23 languages (TEST). |
| STT bn/hi/kn | AI4Bharat IndicConformer; also test SPRING LAB streaming Zipformer for Banglish | MIT / unstated | Utterance-level recognition (no documented streaming). |
| STT ja/en (and hi fallback) | faster-whisper | MIT | Whisper large-v3 or turbo, pick in M0. |
| TTS (demo track) | OmniVoice, all 5 languages, cloned persona voices | code Apache-2.0, weights CC-BY-NC | Demo only. |
| TTS (product track) | Indic Parler-TTS (bn/hi/kn); Kokoro or Qwen3-TTS (ja/en) | Apache-2.0 | Commercially usable. |
| Crawler | Crawl4AI | Apache-2.0 | Same-domain, limits, own robots.txt check. |
| Embeddings / store | BGE-M3 + Chroma | MIT / Apache-2.0 | Local. |
| DB | SQLite | public domain | |

TTS engines are chosen per language in M0 from listening scores. Everything sits behind `STT` and `TTS` interfaces.

---------------------------------------------------------------------

## 5. Language matrix

| Language | Script | STT | TTS demo | TTS product | Haiku quality | Risk |
|---|---|---|---|---|---|---|
| English | Latin | faster-whisper | OmniVoice / Kokoro | Kokoro / Qwen3-TTS | TEST | Low |
| Japanese | Kana/Kanji | faster-whisper | OmniVoice / Kokoro | Kokoro / Qwen3-TTS | TEST | Low-Med (keigo) |
| Hindi | Devanagari | IndicConformer (Whisper fallback) | OmniVoice | Indic Parler (Rohit, Divya, Aman, Rani) | TEST | Med |
| Bengali | Bengali | IndicConformer / Zipformer | OmniVoice | Indic Parler (6 speakers) | TEST | High |
| Kannada | Kannada | IndicConformer | OmniVoice | Indic Parler (Suresh, Anu, Chetan, Vidya) | TEST | Highest |

Integration order: English -> Japanese -> Hindi -> Bengali -> Kannada.

---------------------------------------------------------------------

## 6. Language switching, step by step

1. VAD + Smart Turn cut the caller audio into a turn.
2. Language ID over the 5 candidates: Whisper language detection on the turn audio, biased toward the previous language. If top confidence is below a threshold, run the previous language's recognizer and the top candidate's recognizer and keep the transcript whose script and confidence fit best. Thresholds are set from M0 data.
3. Script check on the transcript (Unicode ranges: Bengali, Devanagari, Kannada, kana/kanji, Latin). A mismatch with the LID guess flips to the script's language.
4. Route to the STT for that language. The detected language goes into the LLM turn context.
5. Claude replies in the caller's language, in NATIVE SCRIPT (never romanized), with numbers, currencies and dates written out as words in that language (TTS engines mispronounce digits).
6. The reply language is determined deterministically from the reply's script, not from the model's word. The TTS router and voice are chosen from that.
7. Low confidence anywhere keeps the previous language. The UI shows the language badge and lets you override manually.
8. Romanized Hindi/Bengali typed-style speech and heavy English mixing (Hinglish, Banglish) are TEST cases.

Latency budget (targets to verify, not measurements): endpointing ~0.5s, STT ~0.4s, Claude first sentence ~0.6s, TTS first audio ~0.6s, total under about 2.5s. OmniVoice only emits audio after a full utterance, so replies are split into sentences and each is synthesized as soon as it completes. Prompt asks for 1-2 short sentences.

---------------------------------------------------------------------

## 7. Agent Studio spec

Agent profile (JSON, versioned on every save):
- `name`, `type` (preset: bank_support | tourism | ecommerce | clinic_frontdesk | custom), `custom_role_text`.
- `persona`: name, tone, formality, greeting, closing, per-language politeness (ja keigo level; hi/bn/kn formal-informal pronoun form).
- `response_style`: max sentences (default 2), verbosity, confirm-numbers on/off, filler phrases on/off, readback rules.
- `languages`: enabled list, default language, auto-switch on/off.
- `guardrails`: allowed topics, forbidden topics, required disclaimers (with trigger conditions), PII rules, escalation triggers, handoff message per language, refusal style, banned claims list.
- `voices`: per language, voice id; persona set id.
- `knowledge`: list of source ids, retrieval settings (top-k, min score), site brief on/off.
- `tools`: enabled mock tools for the type (bank: balance lookup, card block request; tourism: itinerary search; ecommerce: order lookup).

Presets ship with sensible defaults and disclaimers. Custom type uses free text. Rollback restores a previous version.

---------------------------------------------------------------------

## 8. Website -> full-context agent

1. User enters URL(s) and limits (default depth 3, max 50 pages, same domain only).
2. Backend checks robots.txt itself, identifies with a clear user agent, and skips disallowed paths. Warns that it is for sites you own or have permission for.
3. Crawl4AI deep-crawl (BFS) renders JS pages and returns markdown.
4. Clean: strip nav/footer duplicates, dedupe.
5. Chunk by headings (target a few hundred tokens), keep source URL and title.
6. Embed with BGE-M3, store in Chroma, one collection per knowledge source.
7. Site brief: Claude reads the cleaned pages and writes a structured brief (business summary, products/services, prices, hours, contacts, policies, FAQs). Stored, cached in the system prompt.
8. Per turn: embed the caller's transcript, retrieve top-k, pass chunks to Claude, instruct to answer only from brief/chunks/tools. Cross-lingual retrieval is TEST.
9. Small sites: skip retrieval and put the entire cleaned text in the cached prompt when it fits.
10. Knowledge page shows status via SSE, pages found, chunk preview, and an "ask a test question" box with sources.
11. Re-crawl and delete supported.

---------------------------------------------------------------------

## 9. Guardrails spec

- Layer 1: prompt rules built from profile fields.
- Layer 2 (default, cost-saving): local rules on caller input (keywords, patterns: injection, off-topic, forbidden topic, PII) plus ONE combined Claude check on the reply before TTS. Settings toggle: full Claude checker on input as well. Reply check covers (forbidden content, banned claims, missing disclaimer, ungrounded answers). Implemented as a small Claude call with a strict JSON verdict; fails closed to the handoff message.
- Layer 3: tool allowlist per agent type.
- Every trigger logged with turn id.
- Red-team set: 10 attacks per preset (prompt injection, off-topic, other customer's data, "ignore your rules", social engineering for account details, language-switch jailbreaks in each of the 5 languages). Report pass rate honestly.
- Always: opening line says it is an AI assistant. Never read back full card/account numbers.

---------------------------------------------------------------------

## 10. Voices spec

- Voice registry table: `id, language, engine, display_name, persona_tag, reference_clip_path, license, demo_only`.
- Persona sets: warm female, calm male, energetic young, formal senior. Each persona maps to a voice per language.
- Demo track: each persona = one reference clip cloned by OmniVoice, which can give one consistent voice across languages. Clips only from consenting speakers or generated by Kokoro/Parler. The transcript of the clip is stored with it.
- Product track: Parler speaker + description per persona for bn/hi/kn; Kokoro or Qwen3 voice for ja/en.
- Voice picker: per language list, 5-second preview with a language-appropriate sample sentence, set default, change live during a call (applies from the next sentence).
- Demo-only voices carry a visible badge in the UI.

---------------------------------------------------------------------

## 11. Pages (design details in DESIGN.md)

1. Landing / gallery: wordmark, hero, agent preset gallery, "Start a demo".
2. Agent Studio: profile list, editor with tabs (Role, Persona, Style, Guardrails, Languages, Voices, Knowledge, Tools, Versions).
3. Live Call: voice-reactive visual, transcript with language badges, latency readout, voice switcher, override, end call, profile selector.
4. Knowledge: URL drop zone, crawl progress, pages list, chunk preview, test question.
5. Call Logs: list, call detail with transcript, per-turn timings, guardrail events.

---------------------------------------------------------------------

## 12. Data model (SQLite)

- `profiles(id, name, type, created_at)`
- `profile_versions(id, profile_id, version, config_json, created_at)`
- `knowledge_sources(id, profile_id, url, status, pages, chunks, brief_text, created_at)`
- `voices(id, language, engine, display_name, persona_tag, reference_path, license, demo_only)`
- `calls(id, profile_version_id, started_at, ended_at, languages_used)`
- `settings(key, value_encrypted, updated_at)`, `spend(id, call_id, model, input_tokens, output_tokens, cache_read_tokens, usd, created_at)`
- `turns(id, call_id, role, language, text, stt_ms, llm_ms, tts_ms, guardrail_json, created_at)`
- Chroma collections: one per knowledge source (chunk text, source URL, title).

## 13. API

- `GET/POST /api/profiles`, `GET/PUT /api/profiles/{id}`, `GET /api/profiles/{id}/versions`, `POST /api/profiles/{id}/rollback`
- `POST /api/knowledge` {url, limits}, `GET /api/knowledge/{id}`, `GET /api/knowledge/{id}/events` (SSE), `POST /api/knowledge/{id}/ask`, `DELETE /api/knowledge/{id}`
- `GET /api/voices`, `POST /api/voices/preview`, `POST /api/voices` (add persona clip)
- `POST /api/calls/offer` (WebRTC SDP exchange), `GET /api/calls`, `GET /api/calls/{id}`
- `GET /api/settings` (key last 4, spend cap, spend so far, edit allowed), `PUT /api/settings/key`, `POST /api/settings/key/test`, `PUT /api/settings/spend-cap` (edits need `ADMIN_PASSWORD`; disabled when `ALLOW_KEY_EDIT=false`)
- `GET /api/health` (models loaded, VRAM, key present, spend so far)

---------------------------------------------------------------------

## 14. Repo layout

```
shaon-voice-ai/
  PLAN.md  DESIGN.md  CLAUDE.md  DEPLOY.md  README.md  .env.example  pyproject.toml
  web/        Next.js app, design system, 3D/ASCII components
  api/        FastAPI: profiles, ingest, voices, logs
  agent/      Pipecat pipeline, routers, prompt builder, guardrails
  eval/       test lines (50 + 10 mixed), scoring scripts, results.md
  voices/     reference clips, persona config
  design/     moodboard, reference inventory, assets
  data/       sqlite, chroma (gitignored)
  scripts/    start.sh, download_models.sh, check_hardware.py
  tests/      unit tests (pytest) for agent/ api/ eval/ code
  deploy/     added at M10 only: tunnel script + checklist (DEPLOY.md, $0 plan)
```
Additions vs v3 (2026-11-16): DEPLOY.md (hosted demo plan), pyproject.toml (one Python project with optional extras per engine), tests/, deploy/ (M10).

---------------------------------------------------------------------

## 15. Milestones (acceptance criteria)

**M0 - Bake-off.** 50 test lines (10 per language) + 10 mixed, recorded by a native speaker per language where possible. Measure: STT word error rate and latency per language; language-ID accuracy incl. mixed; TTS naturalness (native-speaker 1-5) for each engine and language; Claude Haiku 5.5 reply quality in each language (native speaker); BGE-M3 cross-lingual retrieval hit rate; VRAM and speed on your machine. Optional 1-hour spike with huggingface/speech-to-speech. Use VoiceStudio for listening. Output `eval/results.md`; lock engines; decide fallbacks.
**D0 - Design spike (parallel to M0/M1).** Landing hero + Live Call visual prototype (DESIGN.md section 8), performance checked while a model is running.
**M1 - Voice skeleton.** Next.js shell + Pipecat pipeline, English only, one voice, one profile. Transport chosen by config (SmallWebRTC local, FastAPI WebSocket hosted). Settings page with encrypted key store and spend cap. Turn latency logged.
**M2 - Agent Studio core.** Profiles, presets, persona/style, prompt builder, versions, rollback. Auth + rate-limit layer in `api/`.
**M3 - Languages.** Add ja, hi, bn, kn with routers and language ID. Pass: 3 consecutive switch directions on the test lines per language pair.
**M4 - Knowledge.** URL ingest, brief, retrieval, Knowledge page, sources in transcript.
**M5 - Guardrails.** Settings, checker, handoff, red-team run and report.
**M6 - Voices.** Registry, picker, preview, personas, live switching.
**M7 - UI build-out.** Full design system applied to all pages, motion, ASCII, performance tiers, accessibility pass.
**M8 - Demo hardening.** Call logs, one-command start, fallback video, two demo agents with sample sites (one bank-style fake, one tourism), demo script, README.
**M9 - Eval report.** Numbers per language, honest weak spots, product-track notes.
**M10 - $0 remote demo.** See DEPLOY.md. Worker stays on your PC; optional Cloudflare Quick Tunnel + WebSocket transport (tested first); frontend from your PC or Vercel Hobby; app-level password; recorded fallback video. No paid hosts.

Estimate: about 3 weeks of focused work with Claude Code including design (estimate, not measurement).

---------------------------------------------------------------------

## 16. Risks

1. Bengali, Hindi, Kannada voice naturalness unproven (OmniVoice has little data for them). Fallback: hosted voice for those languages in demo only, clearly labeled; or fine-tune Parler on the Bangla TTS datasets (separate project).
2. Kannada is likely weakest in STT, TTS and LLM. Measure before promising.
3. IndicConformer needs the AI4Bharat NeMo fork and has no documented streaming: extra delay per turn, install friction. Whisper is the Hindi fallback.
4. Memory: 5 languages of STT/TTS + BGE-M3 on one machine. Load on demand, measure in M0. UI effects compete for the GPU: see DESIGN.md performance tiers.
5. OmniVoice weights are non-commercial; demo only. Cloning needs consent.
6. Claude Haiku 5.5 in Kannada/Bengali untested; Sonnet 5.5 fallback per language.
7. Ungrounded answers: retrieval plus "answer only from sources" plus handoff; checker flags ungrounded replies.
8. Crawl legality/ethics: permission, robots.txt, limits.
9. Bank demo: fake data only, AI disclosure, no real account numbers.
10. Needs an Anthropic API key and spend cap (a claude.ai subscription does not include API usage). The Claude API is the only spend ($0 rule, DEPLOY.md); default app cap $10.
11. Demo from a laptop: record a fallback video; tunnel if the client must connect.
12. Naming: check that "ShaOn Voice AI" is not already used before showing a client.
