# Feature Details: Audio-Subtitle-Sync Platform

This document provides a comprehensive description of the Audio-Subtitle-Sync platform features as implemented in this repository. It covers how uploads are handled, how automated analysis and correction work, what the deterministic generation and translation stubs do, how validation is performed, how repositioning avoids overlap with hardcoded text, and the current state of the dashboard, notifications, RBAC, and in-browser editing. For each feature, we summarize the purpose, tools and technologies used, inputs, processing and logic, outputs, configuration, error handling, example usage, and CI/testability notes.

The platform consists of:
- Backend Service (FastAPI) providing REST endpoints for quality check, generation, translation, validation, job status, and file download.
- Frontend Web Dashboard (React) with an API client, notifications, and a progress tracker.
- Database layer (SQLite schema and models) prepared for users, videos, subtitles, and jobs.

All core processing paths use deterministic stubs so CI runs are reproducible without external services.

## 1) Upload and File Handling

### Purpose
The backend accepts video and subtitle files via multipart form-data. Files are validated and saved to a configured uploads directory, where background jobs are then enqueued to perform quality checks, generation, translation, or validation. Processed outputs are stored in a configured processed directory for later download.

### Tools/Technologies used
- FastAPI for HTTP endpoints and multipart file upload handling (python-multipart).
- Custom utilities in file_utils.py for directory management and format checks.
- Environment-driven paths via config.py (UPLOAD_DIR, PROCESSED_DIR, WORK_DIR).
- In-memory background job queue in job_processor.py (thread-based).
- UUID-based temp filenames and shutil streaming to persist UploadFile contents.

### Inputs
- Endpoint: POST /subtitles/quality-check
  - Form fields:
    - subtitle_file (file, required)
    - video_file (file, optional)
    - language (form field, optional)
    - enforce_ott_compliance (boolean form field, default true)
- Endpoint: POST /subtitles/generate
  - Form fields:
    - video_file (file, required)
    - language (form field, optional)
    - translate_to (comma-separated string of ISO-639-1 codes, optional)
    - model_hint (optional)
- Endpoint: POST /subtitles/translate
  - Form fields:
    - subtitle_file (file, required)
    - target_language (string, required)
    - source_language (string, optional)
    - model_hint (optional)
- Endpoint: POST /subtitles/validate
  - Form fields:
    - subtitle_file (file, required)
    - optional validation parameters (max_chars_per_line, max_lines_per_caption, min_caption_duration_ms, max_caption_duration_ms, reading_speed_cps, frame_rate, language)

Accepted subtitle extensions for upload are checked by allowed_subtitle_extension in file_utils.py: .srt, .vtt, .ass, .ssa, .sbv, .txt.

### Processing/Logic overview
- UploadFile persistence is performed by an internal helper (_save_upload), which writes streamed content into a temporary file under UPLOAD_DIR with a UUID-based name.
- Subtitle format hints are derived with guess_subtitle_format, using the file extension and rudimentary inspection for .txt.
- A JobQueue instance enqueues a closure for the requested operation. The background thread updates job status and captures result file paths relative to PROCESSED_DIR.
- The validate endpoint reads the uploaded file and returns a JSON response immediately without queuing a job.

### Outputs
- For queued operations (quality-check, generate, translate):
  - Response: JSON with job_id and initial status.
  - Subsequent: GET /jobs/{job_id} returns status, optional message, and result_files (list of relative paths).
  - Processed files are written to PROCESSED_DIR and can be downloaded via GET /files/{filename} using the value returned in result_files.
- For validation:
  - Response: JSON with fields valid (bool), issues (list of strings), and format (format detection result).

### Configuration
- BACKEND_HOST (default 0.0.0.0)
- BACKEND_PORT (default 8000)
- DEBUG (default false; enables reload when running directly)
- CORS_ALLOW_ORIGINS (default "*")
- UPLOAD_DIR (default ./uploads)
- PROCESSED_DIR (default ./processed)
- WORK_DIR (default ./work)
- Optional provider hints: LLM_PROVIDER, LLM_API_KEY, STT_PROVIDER, STT_API_KEY (not used by stubs; reserved for integrations)

### Error handling and typical failure cases
- 400 Unsupported subtitle file extension (quality-check/translate/validate) when extension not in allowed set.
- 404 Job not found when querying an unknown job_id.
- 404 File not found for GET /files/{filename} if the produced path does not exist.
- Standard error cases may produce a 500 with a traceback within JobQueue.message if the background function raises.

### Example usage
- Health and connectivity:
```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/hello
```

- Quality check with optional video:
```bash
curl -X POST http://localhost:8000/subtitles/quality-check \
  -F "subtitle_file=@sample.srt" \
  -F "video_file=@sample.mp4" \
  -F "language=en" \
  -F "enforce_ott_compliance=true"
```

- Poll job and download result:
```bash
curl -s http://localhost:8000/jobs/<job_id>
curl -L -o corrected.srt "http://localhost:8000/files/<result_file_from_job>"
```

### Testability/CI notes
- Upload persistence uses deterministic UUID-based temp naming; processing stubs produce consistent content across runs.
- No external network calls are required. The system is suitable for CI environments with no GPU or heavyweight dependencies.

## 2) Automated Analysis and Correction

### Purpose
Run a quality check on an uploaded subtitle, optionally using a reference video, and write a corrected subtitle file. The backend also contains a more advanced, programmatic correction module for aligning cues to a transcript, enforcing OTT constraints, and performing conservative text corrections.

### Tools/Technologies used
- API endpoint: POST /subtitles/quality-check.
- subtitle_processor.run_quality_check_and_correct: deterministic normalization and naive compliance stub.
- subtitle_correction module: advanced correction pipeline for programmatic use (not directly exposed via API).
- subtitle_correction.apply_additional_compliance_fixes: post-processing hook (currently a copy).

### Inputs
- subtitle_file (required), video_file (optional), language (optional), enforce_ott_compliance (boolean).

### Processing/Logic overview
- The endpoint enqueues a job that:
  - Normalizes line endings and whitespace, ensures blank-line separation, and applies a simple rule to limit lines per caption when enforce_ott is true.
  - If a video is provided, a deterministic console summary logs sample findings (e.g., long text lines).
  - Writes the result into PROCESSED_DIR and then applies a post-processing copy hook.
- The subtitle_correction module provides pure functions for transcript-aligned correction:
  - correct_subtitles aligns cues to a transcript (seconds), refines times, inserts missing cues from transcript, and enforces OTT timing with no overlaps.
  - correct_subtitles_with_audio and hybrid_correct_subtitles introduce stubs for audio-based disambiguation and staged pipelines while remaining deterministic.

### Outputs
- Job response with job_id and final result_files containing the corrected subtitle.
- The corrected file is an SRT written to PROCESSED_DIR with a temp_<uuid>_corrected.srt (and a subsequent postfix copy name).

### Configuration
- Uses config-driven directories. No external ASR/LLM keys are used in this stub.

### Error handling and typical failure cases
- Unsupported subtitle extension: HTTP 400.
- Processing exceptions are caught in JobQueue and returned in the job status message field if failures occur.

### Example usage
- API (see Upload section).
- Programmatic advanced correction:
```python
from Subtitle_Sync_Platform.BackendService.subtitle_correction import correct_subtitles

transcript = {
    "language": "en",
    "segments": [
        {"start": 1.0, "end": 2.0, "text": "Hello world"},
        {"start": 2.2, "end": 3.0, "text": "How are you"},
    ],
}
subtitles = [
    {"start": 0.8, "end": 2.3, "text": "Hello wrld", "language": "en", "format": "srt"},
]
corrected = correct_subtitles(transcript, subtitles)
```

### Testability/CI notes
- Unit tests at BackendService/tests/test_alignment_snap.py validate snapping behavior and ensure the pipeline is deterministic.
- The correction functions are pure for easy unit testing; file I/O is confined to post-processing hooks.

## 3) Subtitle Generation (Deterministic Stub)

### Purpose
Generate a simple, deterministic SRT file from a video upload to simulate STT output for CI and development.

### Tools/Technologies used
- API endpoint: POST /subtitles/generate.
- subtitle_processor.generate_subtitles_for_video creates a consistent two-cue SRT for the requested language.

### Inputs
- video_file (file), optional language code (defaults to "en"), optional translate_to (comma-separated list) to trigger subsequent translation jobs within the same task.

### Processing/Logic overview
- The job writes a generated SRT to PROCESSED_DIR with a name like temp_<uuid>_generated_<lang>.srt.
- If translate_to is provided, each target language is translated via translate_subtitles and appended to the result_files.

### Outputs
- job_id and later a result_files array including the generated subtitle and any translations.

### Configuration
- No external providers are used in the stub; PROCESSED_DIR is respected.

### Error handling and typical failure cases
- Standard job-level failure handling. Video format validation is minimal at this layer; ensure the frontend enforces acceptable types.

### Example usage
```bash
curl -X POST http://localhost:8000/subtitles/generate \
  -F "video_file=@sample.mp4" \
  -F "language=en" \
  -F "translate_to=es,fr"
```

### Testability/CI notes
- Output is text-based and content is deterministic. No STT engines are required.

## 4) Translation (Deterministic Stub)

### Purpose
Translate an uploaded subtitle file into a target language using a stub that preserves SRT structure while marking text lines with the target language code.

### Tools/Technologies used
- API endpoint: POST /subtitles/translate.
- subtitle_processor.translate_subtitles for deterministic translation behavior.

### Inputs
- subtitle_file (file), target_language (required), source_language (optional), model_hint (optional).

### Processing/Logic overview
- The translation function appends “[<target_language>]” to non-timing, non-index lines, leaving SRT headers and blank lines intact.

### Outputs
- job_id producing a single translated file in PROCESSED_DIR named temp_<uuid>_translated_<lang>.srt.

### Configuration
- None beyond directory paths; external providers are not used.

### Error handling and typical failure cases
- 400 for unsupported subtitle extension.
- Job errors returned in job status message if failures occur.

### Example usage
```bash
curl -X POST http://localhost:8000/subtitles/translate \
  -F "subtitle_file=@corrected_en.srt" \
  -F "target_language=es"
```

### Testability/CI notes
- Translation modifies only text lines and is intentionally deterministic.

## 5) Validation

### Purpose
Validate a subtitle file against configurable constraints such as characters per line, lines per caption, caption duration, and reading speed.

### Tools/Technologies used
- API endpoint: POST /subtitles/validate.
- subtitle_processor.validate_subtitles performing simple checks.

### Inputs
- subtitle_file (file, required)
- Optional parameters:
  - max_chars_per_line (default 42)
  - max_lines_per_caption (default 2)
  - min_caption_duration_ms (default 800)
  - max_caption_duration_ms (default 8000)
  - reading_speed_cps (default 17)
  - frame_rate (optional float)
  - language (optional string)

### Processing/Logic overview
- The validator parses SRT-like blocks and inspects timing lines and text lines, flagging blocks that exceed configured constraints.

### Outputs
- JSON:
```json
{
  "valid": true,
  "issues": [],
  "format": "srt"
}
```

### Configuration
- Validation is parameterized per request; no global config is required.

### Error handling and typical failure cases
- 400 if unsupported extension.
- Parsing issues are reported in the issues array rather than throwing exceptions.

### Example usage
```bash
curl -X POST http://localhost:8000/subtitles/validate \
  -F "subtitle_file=@some.srt" \
  -F "max_chars_per_line=42" \
  -F "max_lines_per_caption=2"
```

### Testability/CI notes
- The validator uses simple regex-based parsing; results are deterministic and suitable for snapshot testing.

## 6) Subtitle Repositioning

### Purpose
Reposition subtitle cues to avoid overlap with hardcoded (burnt-in) text inside the video. This is provided as a programmatic utility and CLI, not as an HTTP endpoint.

### Tools/Technologies used
- subtitle_reposition.reposition_subtitles_based_on_hardcoded_text for format-aware repositioning.
- Deterministic OCR stub: _sample_frames_and_detect_burnt_in_text infers bottom/top presence based on filename keywords (“top”, “bottom”), defaulting to bottom presence.

Supported formats and how positioning is applied:
- SRT: Inserts a comment “NOTE: position=<top|bottom>” after the timing line within each block (portable hint).
- VTT: Appends or updates cue settings with a line value (top: line:0, bottom: line:90).
- ASS/SSA: Attempts to modify “Style: Default” alignment (top=8, bottom=2) or appends a comment note if not modifiable.

### Inputs
- video_path (string path)
- subtitle_path (string path)
- Optional:
  - output_path (string path; default is auto-generated in PROCESSED_DIR with consistent extension)
  - processed_dir (default ./processed)
  - sample_rate (float; used by the OCR stub for future compatibility)

### Processing/Logic overview
- The stub detects likely burnt-in text location and chooses a safer subtitle position:
  - If bottom text is present and top is not, selects top.
  - If top text is present and bottom is not, selects bottom.
  - If both or neither detected, defaults to top as a safer choice against player controls.
- The function writes the updated subtitle content while keeping the original format.

### Outputs
- Returns the absolute path to the output subtitle file written to output_path or PROCESSED_DIR.

### Configuration
- Respects processed_dir and output_path arguments; no environment variables are required.

### Error handling and typical failure cases
- FileNotFoundError if either the video or subtitle path does not exist.

### Example usage
- Programmatic:
```python
from Subtitle_Sync_Platform.BackendService.subtitle_reposition import reposition_subtitles_based_on_hardcoded_text

out = reposition_subtitles_based_on_hardcoded_text(
    video_path="input.mp4",
    subtitle_path="captions.srt",
    processed_dir="./processed",
    sample_rate=1.0
)
print("Repositioned file at:", out)
```

- CLI:
```bash
python -m Subtitle_Sync_Platform.BackendService.subtitle_reposition \
  --video input.mp4 \
  --subs captions.ass \
  --processed-dir ./processed
```

### Testability/CI notes
- OCR behavior is stubbed and deterministic, making outputs stable in CI. The format-specific transformations are pure string manipulations.

## 7) Dashboard (Frontend)

### Purpose
Provide a React-based UI for initiating processing, tracking job progress, and downloading results. The current dashboard includes a notifications system and a progress tracker and relies on environment-configured API base URL.

### Tools/Technologies used
- React 18 application.
- Axios-based API client (src/services/api.js), configured via REACT_APP_API_BASE_URL with request/response interceptors.
- ProgressTracker component for job polling.
- Notification component for user feedback.
- File utility helpers for validation and client-side downloads.

### Inputs
- The API client expects REACT_APP_API_BASE_URL to be set in the environment.
- The client currently defines methods like processFiles, generateSubtitles, correctSubtitles, getJobStatus, getSubtitleFiles, downloadSubtitleFile, requestTranslation, authenticateUser, registerUser, testBackend.

Operational note: In this repository, the backend implements /subtitles/* endpoints and GET /jobs/{job_id}, while the frontend API client includes placeholder paths like /process, /jobs/${jobId}/status, /subtitles listing and per-id routes, and /auth endpoints that the backend does not implement yet. For production usage, either map the frontend to the current backend routes or extend the backend to serve these routes. The “Test Backend” action calls /api/hello, which is implemented and useful for connectivity checks.

### Processing/Logic overview
- ProgressTracker polls job status periodically and invokes callbacks on completion or failure. It expects a structure with status, progress, and message. The backend returns status and message; progress is not emitted and defaults in the component to 0, which is acceptable but may show a static bar until completion.
- Notifications are displayed for success and error states and auto-dismiss by default.

### Outputs
- UI feedback for job states and notifications.
- Client-side file downloads initiated by the dashboard (downloadBlob).

### Configuration
- REACT_APP_API_BASE_URL is mandatory for correct endpoint resolution.
- Optional: REACT_APP_SITE_URL may be used by other parts of the app (see Frontend README for guidance).

### Error handling and typical failure cases
- The API client logs detailed error diagnostics to the console.
- Notification strings are constructed based on HTTP error status when present.
- File validation errs early with user-friendly messages for unsupported types or oversized files.

### Example usage
- Connectivity test (frontend button triggers):
```javascript
const data = await testBackend(); // calls GET /api/hello
alert(`Backend says: ${data?.message ?? 'no message'}`);
```

- File download:
```javascript
const response = await downloadSubtitleFile(fileId);
// response.data is a Blob; downloadBlob(response.data, filename)
```

### Testability/CI notes
- The dashboard can run against the deterministic backend stubs for consistent integration tests.
- Ensure environment variables are set in CI for the frontend to communicate with the backend.

## 8) Notifications

### Purpose
Provide user-visible feedback for operations such as job submission, completion, errors, and generic system messages.

### Tools/Technologies used
- React Notification component (src/components/Notification.js) with CSS for styling and transitions.

### Inputs
- Props: message (string), type (success, error, warning, info), duration (ms), onClose (callback).

### Processing/Logic overview
- A timer auto-dismisses notifications and calls onClose after a brief fade-out to allow animations to complete.

### Outputs
- Accessible UI element with close control and styling variants.

### Configuration
- Duration can be configured per notification instance in the dashboard.

### Error handling and typical failure cases
- None specific; rendering simply returns null when not visible.

### Example usage
```javascript
<Notification
  message="Subtitle generation completed!"
  type="success"
  duration={5000}
  onClose={() => setNotification(null)}
/>
```

### Testability/CI notes
- Stateless visual component; behavior is deterministic and testable with DOM snapshots or integration tests.

## 9) Role-based Access Control (RBAC) Status

### Purpose
Securely restrict access to features and actions by user role when implemented. The current repository includes placeholders for authentication and a database schema that anticipates user roles.

### Tools/Technologies used
- Backend placeholders:
  - auth.py: require_user() dependency placeholder.
  - database.py: get_db() placeholder.
- Database schema and models:
  - users table with a role column (default "user").
  - Related tables for videos, subtitles, and jobs.

### Inputs
- The frontend API client includes authenticateUser and registerUser methods targeting /auth/login and /auth/register; however, these routes are not implemented in the backend yet.

### Processing/Logic overview
- RBAC is not enforced at the API level in the current backend. The placeholders are ready for integrating JWT or OAuth2 authorization and attaching user context to operations.

### Outputs
- None in the current implementation; it is a planned capability.

### Configuration
- None at present beyond database setup; production would require auth secrets and token configuration.

### Error handling and typical failure cases
- Attempting to call non-existent auth routes will result in 404 errors. The frontend handles this by showing error notifications.

### Example usage
- Planned usage:
  - Protect routes with a require_user dependency that validates tokens and checks roles.
  - Attach user_id and role to created videos, subtitles, and jobs in the database.

### Testability/CI notes
- With RBAC not enforced yet, deterministic stubs are preserved in CI. When implemented, provide test fixtures for tokens and user roles.

## 10) In-browser Editor (Planned)

### Purpose
Provide a subtitle editor synchronized with video playback to manually review and adjust text and timing, and to export edited subtitles. This is a planned feature not currently present in the repository.

### Tools/Technologies used
- Planned: React components for waveform/timeline, text editing, and keyboard shortcuts. Backend endpoints to save edits and version files.

### Inputs
- Planned: Editor would accept a selected subtitle file and the associated video for synchronized playback.

### Processing/Logic overview
- Planned: Editing would update cue text and times in memory, with debounced auto-save or explicit save to backend endpoints.

### Outputs
- Planned: Edited files persisted on the backend with versioning and downloadable output in requested formats.

### Configuration
- Planned: User preferences (e.g., font size, snapping behavior) stored in local storage or user profile.

### Error handling and typical failure cases
- Planned: Validation warnings for overlapping or invalid cue times during editing.

### Example usage
- Not available yet; refer to the frontend and backend READMEs once this feature is added.

### Testability/CI notes
- When implemented, deterministic fixtures for video segments and example subtitle files will allow stable UI tests.

## Operational Notes

- Endpoints and path alignment: The backend implements /subtitles/* and GET /jobs/{job_id}, while the current frontend API client includes some placeholder routes (e.g., /process, /jobs/${jobId}/status, /auth/*) not present in the backend. Align these by either updating the frontend to use the current backend endpoints (POST /subtitles/quality-check, /subtitles/generate, /subtitles/translate, /subtitles/validate; GET /jobs/{job_id}; GET /files/{filename}) or by extending the backend to add compatibility routes.
- Real-time updates: There is no WebSocket endpoint. Poll GET /jobs/{job_id} for status and results, as noted by GET /docs/websocket.
- Database integration: The provided schema and models cover users, videos, subtitles, and jobs; however, the backend service in this repository does not yet persist to the database. Integrate SQLAlchemy and wire endpoints as needed.
- File formats: Processing logic favors SRT for stub operations. Repositioning supports SRT, VTT, and ASS/SSA without external parser libraries by performing textual transformations that preserve file structure.
- Determinism: All processing is deterministic for CI, including OCR stubs for repositioning and stubbed generation/translation. This ensures stable output names and contents differing only by UUID prefixes for filenames.
