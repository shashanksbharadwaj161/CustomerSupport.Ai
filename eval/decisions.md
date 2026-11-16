Status 2026-11-16: no engine is locked yet. Native recordings, native ratings and a GPU run are pending.

Context for the numbers above: they were produced in the Claude Code cloud VM (4 CPUs, no GPU, host `vm`), not on the demo machine.
- Retrieval hit rates ARE meaningful (accuracy does not depend on hardware). BGE-M3 hit@3 is 100% for en/ja/hi/bn and 89% for kn on a 13-chunk English fixture; hit@1 is 89% in every language. The same miss repeats in all languages: "transfer money to my sister" ranks the human-agent chunk ("ask the assistant to transfer you") first, so this is a word-sense collision, not a cross-lingual failure. Two mixed flight-booking lines ranked the airport-pickup chunk first (arguably a fixture labeling issue). Real check comes in M4 on a crawled site; consider a hybrid (BM25 + dense) or reranker if it persists.
- TTS timings are CPU timings for Kokoro only (en/ja). Not representative of the demo machine; first audio about 0.8-2.0 s per sentence on 4 CPU cores.
- STT and LID rows here are SYNTHETIC pipeline checks (Kokoro audio into Whisper small on CPU), not accuracy results.
- Hardware section shows the VM. Re-run `python scripts/check_hardware.py` on the demo PC.

Findings that change setup (already applied):
- Kokoro needs Python 3.10-3.12 (`requires-python` pinned). English G2P needs espeak-ng and the spaCy `en_core_web_sm` model (added to the `tts-kokoro` extra). Japanese needs `python -m unidic download` once.
- Whisper writes numbers as digits ("4729", "5,000") while references spell them out: results show WER both with and without the two number lines per language.
