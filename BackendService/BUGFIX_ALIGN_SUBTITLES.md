# Bugfix: Prevent cascading early-start shifts in align_subtitles

Issue:
- When only a few input timestamps were inaccurate, many output cues were being shifted near the start (continuous, wrongly timed cues).
- Root cause: refit thresholds were too lenient and the monotonic enforcement used a global `last_end` that could cascade forward shifts, effectively dragging subsequent cues.

Fix summary:
- Tightened the “already good” detection thresholds to preserve well-aligned cues (overlap >= 70% and a tighter center tolerance).
- Introduced anchor-based stabilization: cues deemed “already good” become anchors and subsequent cues cannot pull them earlier.
- Adjusted the monotonic enforcement to reference the latest anchor end rather than naïve `last_end`, applying only minimal forward shifts.
- Softened the final global monotonic pass (smaller min_gap) to avoid unnecessary broad movements after per-cue adjustments.
- Added guardrails for sparse/short transcripts to avoid aggressive refits.

Testing:
- Added tests in BackendService/tests/test_subtitle_alignment.py:
  - test_preserve_good_cues_only_adjust_bad_ones: verifies only mis-timed cues are adjusted.
  - test_sparse_transcript_no_bunching_at_zero: ensures distribution without clustering at t=0 when transcript is empty.
  - test_cross_lingual_preserves_text: ensures text is not modified in cross-lingual mode.

Behavioral change:
- Correct cues are now preserved more reliably; only cues that are clearly misaligned are refit.
- Minor timing adjustments still ensure non-overlap and realistic durations, but without cascading drifts.

Notes:
- This is a conservative change targeting stability; further tuning may be applied per content type or platform policy.
