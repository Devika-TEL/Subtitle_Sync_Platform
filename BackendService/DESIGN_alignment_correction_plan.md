# Subtitle Alignment and Correction - Implementation Plan

This document outlines a concrete, staged implementation plan to add:
1) Actual subtitle text correction
2) Robust multi-language alignment (language-aware tokenization and semantic similarity)
3) Robust fuzzy-matching (character/token-level + embeddings)
4) Explicit logic/fix for delayed or improperly corrected cue start times

Repository integration points:
- `BackendService/subtitle_alignment_simple.py` — extend with hybrid similarity and start-time correction.
- `BackendService/subtitle_correction.py` — implement grammar/spell/punctuation normalization and wrapping.
- `BackendService/backend_subtitle_service.py` or `subtitle_processor.py` — orchestrate pipeline and add config flags.
- `BackendService/config.py` — new configuration values (see below).

## Phase 1 (MVP)

### Dependencies
- langid
- spacy
- language-tool-python
- rapidfuzz
- sentence-transformers
- python-srt

Optional (later):
- stanza, jieba, faiss-cpu, whisperx

### Config additions (config.py)
- ALIGNMENT_EMBEDDINGS_ENABLED: bool
- ALIGNMENT_MODEL_NAME: str = "paraphrase-multilingual-MiniLM-L12-v2"
- NLP_BACKEND: str = "spacy" | "stanza"
- STARTTIME_FIX_MIN_GAP_MS: int (e.g., 100)
- MAX_CUE_DURATION_MS: int (e.g., 6000)
- FUZZY_WEIGHTS: dict = {"rapidfuzz_partial": 0.4, "rapidfuzz_token": 0.4, "embedding": 0.2}
- LANGUAGE_TOOL_ENABLED: bool
- MAX_CHARS_PER_LINE: int (e.g., 42)
- MAX_LINES: int (e.g., 2)
- DEFAULT_CHARS_PER_SEC: float (e.g., 15)
- DELAY_THRESHOLD_MS: int (e.g., 500)

### Pipeline steps

1. Language detection and normalization
   - `detect_language(text)` using langid on combined cues+transcript (or metadata).
   - `normalize_text(text, lang)` with Unicode NFKC, punctuation mapping, whitespace collapsing, safe lowercasing.

2. Tokenization and lemmatization
   - spaCy pipeline per language (if supported). Fallback to regex splitting.
   - Provide helper `tokenize_and_lemmatize(text, lang)`.

3. Transcript acquisition
   - Use provided transcript if available.
   - Else, default ASR stub (Phase 1 can skip actual ASR; use content-based alignment only; add Whisper later).

4. Hybrid similarity alignment
   - For each cue:
     - Build candidate windows in transcript segments near last matched index for monotonicity.
     - Compute RapidFuzz scores: `partial_ratio`, `token_set_ratio`.
     - If embeddings enabled, compute sentence-transformers cosine similarity.
     - Combined score = weights * [rf_partial, rf_token, emb].
     - Choose best >= threshold; else pick best and mark uncertain.

5. Start-time correction (MVP)
   - If candidate segment has timestamps:
     - `new_start = max(segment.start, last_end + min_gap)`
     - Estimate reading time (`len(text)/chars_per_sec`), clamp between min and `MAX_CUE_DURATION_MS`.
     - `new_end = min(new_start + reading_time, segment.end)`
     - Ensure min duration and gap to next cues.
   - Handle delayed starts:
     - If `cue.start - segment.start > DELAY_THRESHOLD_MS` or overlap small, snap start close to `segment.start + pad`.
     - Recompute end accordingly.
   - If no segment times:
     - Enforce `min_gap`, preserve or cap original duration, apply drift correction (Phase 2).

6. Text correction and wrapping
   - Use `language-tool-python` suggestions.
   - Protect named entities (spaCy NER) to avoid altering proper names.
   - Normalize punctuation, apply sentence case (where applicable).
   - Wrap lines to `MAX_CHARS_PER_LINE` and `MAX_LINES`, respecting word boundaries.

7. Output
   - Save SRT using `python-srt`, preserving cue ids and order.

### Pseudocode (simplified)
See main README for code-oriented pseudocode.

## Phase 2 (Quality)

- Add spaCy NER-based entity protection robustly.
- Add regression-based drift correction using anchors (cue index ↔ transcript time).
- Add FAISS for fast nearest-neighbor on long transcripts.
- Add language-specific segmentation (jieba for Chinese, MeCab for Japanese).
- Strengthen delayed start detection and correction heuristics.

## Phase 3 (Advanced)

- Integrate WhisperX for word-level timestamps and diarization.
- Align cue boundaries to word timestamp spans; better start-end precision.
- Add LLM-guided cue rewriting for low similarity or overly long text.
- Introduce human-in-the-loop toggles and audit summaries.

## Public function signatures (intended)

In `subtitle_alignment_simple.py`:

```python
# PUBLIC_INTERFACE
def align_subtitles_to_transcript(cues, transcript_segments, lang, config) -> List[Cue]:
    """Align cues to transcript segments using hybrid fuzzy/semantic similarity and correct timings."""
```

In `subtitle_correction.py`:

```python
# PUBLIC_INTERFACE
def correct_subtitle_text(text: str, lang: str, config) -> str:
    """Grammar/spell/punctuation correction and wrapping."""
```

In orchestrator:

```python
# PUBLIC_INTERFACE
def run_alignment_and_correction(input_srt_path, transcript, out_srt_path, config):
    """High-level pipeline: detect lang, align cues, correct text, save output."""
```

## Testing

- Unit tests for:
  - Language detection and normalization across EN/ES/FR/CJK samples.
  - Hybrid similarity ranking with multilingual samples.
  - Delayed start correction edge cases.
  - Text correction preserves entities, obeys line wrap and reading speed.

## Notes

- Cache models (spaCy, sentence-transformers) at process level.
- Batch embedding calls.
- Provide flags in config and document environment toggles in README.
