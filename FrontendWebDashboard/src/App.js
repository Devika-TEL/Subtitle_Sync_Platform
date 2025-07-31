import React, { useState, useRef } from "react";
import "./App.css";

// Languages supported for subtitle generation
const LANGUAGE_OPTIONS = [
  { value: "", label: "Select language" },
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "zh", label: "Chinese" },
  { value: "hi", label: "Hindi" },
  { value: "ru", label: "Russian" },
  { value: "ar", label: "Arabic" },
  { value: "pt", label: "Portuguese" }
];

/**
 * Subtitle Sync Platform Main Dashboard
 * Provides two workflows: Subtitle Correction, Subtitle Generation.
 * Language selection is required and visually prominent in the Generation workflow.
 */
// PUBLIC_INTERFACE
function App() {
  // UI state
  const [isCorrectionMode, setIsCorrectionMode] = useState(true);
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);

  // Language selector for generation mode
  const [selectedLanguage, setSelectedLanguage] = useState("");
  const [languageTouched, setLanguageTouched] = useState(false);

  const [processing, setProcessing] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [error, setError] = useState("");

  // References to input fields for reset
  const videoInputRef = useRef();
  const subtitleInputRef = useRef();

  // Handle file changes
  const handleVideoChange = (e) => {
    setVideoFile(e.target.files[0]);
    setDownloadUrl("");
    setError("");
  };

  const handleLanguageChange = (e) => {
    setSelectedLanguage(e.target.value);
    setLanguageTouched(true);
    setError("");
    setDownloadUrl("");
  };

  const handleSubtitleChange = (e) => {
    setSubtitleFile(e.target.files[0]);
    setDownloadUrl("");
    setError("");
  };

  // PUBLIC_INTERFACE
  const handleProcess = async () => {
    /**
     * Uploads files to backend (synchronous). Requires language for generation workflow.
     */
    setProcessing(true);
    setError("");
    setDownloadUrl("");

    const formData = new FormData();

    if (videoFile) formData.append("video", videoFile);
    if (isCorrectionMode && subtitleFile) {
      formData.append("subtitle", subtitleFile);
    }
    if (!isCorrectionMode && selectedLanguage) {
      formData.append("language", selectedLanguage);
    }

    try {
      let endpoint = "";
      if (isCorrectionMode) {
        endpoint = `${process.env.REACT_APP_API_BASE}/subtitle/correct`;
      } else {
        endpoint = `${process.env.REACT_APP_API_BASE}/subtitle/generate`;
      }

      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Processing failed. Please try again.");
      }

      const contentType = response.headers.get("Content-Type") || "";
      let url = "";
      if (contentType.includes("application/json")) {
        const data = await response.json();
        url = data.download_url;
        if (!url) throw new Error("No download URL in response.");
      } else {
        const blob = await response.blob();
        url = window.URL.createObjectURL(blob);
      }
      setDownloadUrl(url);
    } catch (err) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setProcessing(false);
    }
  };

  // PUBLIC_INTERFACE
  const resetForm = () => {
    setVideoFile(null);
    setSubtitleFile(null);
    setSelectedLanguage("");
    setLanguageTouched(false);
    setDownloadUrl("");
    setError("");
    setProcessing(false);
    if (videoInputRef.current) videoInputRef.current.value = null;
    if (subtitleInputRef.current) subtitleInputRef.current.value = null;
  };

  // Disable process button if required fields are missing
  const canStartCorrection = videoFile && subtitleFile && !processing;
  const canStartGeneration = videoFile && selectedLanguage && !processing;

  return (
    <div className="App">
      <header className="app-header" role="banner">
        <div className="brand-logo-container">
          <span className="brand-logo">🎬</span>
          <span className="brand-title">Subtitle Sync Platform</span>
        </div>
        <div className="brand-subtitle">
          AI-powered Subtitle Correction & Generation
        </div>
      </header>
      <nav className="tab-nav" aria-label="Workflow Navigation">
        <button
          className={`tab-btn${isCorrectionMode ? " active" : ""}`}
          onClick={() => {
            setIsCorrectionMode(true);
            resetForm();
          }}
          aria-selected={isCorrectionMode}
          aria-controls="correction-tab"
          disabled={processing}
        >
          Subtitle Correction
        </button>
        <button
          className={`tab-btn${!isCorrectionMode ? " active" : ""}`}
          onClick={() => {
            setIsCorrectionMode(false);
            resetForm();
          }}
          aria-selected={!isCorrectionMode}
          aria-controls="generation-tab"
          disabled={processing}
        >
          Subtitle Generation
        </button>
      </nav>
      <main className="main-content">
        <section id="workflow-forms" aria-live="polite">
          {isCorrectionMode ? (
            <div className="workflow-card">
              <h2 className="workflow-card-header">Subtitle Correction</h2>
              <label className="file-label">
                Video File <span aria-hidden="true">*</span>
                <input
                  ref={videoInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleVideoChange}
                  disabled={processing}
                  required
                />
              </label>
              <label className="file-label">
                Subtitle File <span aria-hidden="true">*</span>
                <input
                  ref={subtitleInputRef}
                  type="file"
                  accept=".srt,.vtt,.ass,.ssa,.sbv"
                  onChange={handleSubtitleChange}
                  disabled={processing}
                  required
                />
              </label>
              <div className="actions">
                <button
                  className="primary-button"
                  onClick={handleProcess}
                  disabled={!canStartCorrection}
                >
                  {processing ? "Correcting..." : "Start Correction"}
                </button>
                <button onClick={resetForm} disabled={processing}>
                  Reset
                </button>
              </div>
              {error && <div className="error-message">{error}</div>}
            </div>
          ) : (
            <div className="workflow-card">
              <h2 className="workflow-card-header">Subtitle Generation</h2>
              <label className="file-label">
                Video File <span aria-hidden="true">*</span>
                <input
                  ref={videoInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleVideoChange}
                  disabled={processing}
                  required
                />
              </label>
              <label className="file-label language-label emphasis-label">
                <span className="language-label-title">
                  Subtitles Language
                </span>{" "}
                <span className="required-asterisk" aria-hidden="true">*</span>
                <select
                  className={`language-select${languageTouched && !selectedLanguage ? " invalid" : ""}`}
                  value={selectedLanguage}
                  onChange={handleLanguageChange}
                  disabled={processing}
                  required
                  onBlur={() => setLanguageTouched(true)}
                  aria-required="true"
                  aria-invalid={languageTouched && !selectedLanguage ? "true" : "false"}
                >
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value} disabled={opt.value === ""}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                {languageTouched && !selectedLanguage && (
                  <span className="selector-error-msg" role="alert">
                    Please select a language
                  </span>
                )}
              </label>
              <div className="actions">
                <button
                  className="primary-button"
                  onClick={() => {
                    setLanguageTouched(true);
                    if (!selectedLanguage) return;
                    handleProcess();
                  }}
                  disabled={!canStartGeneration}
                >
                  {processing ? "Generating..." : "Start Generation"}
                </button>
                <button onClick={resetForm} disabled={processing}>
                  Reset
                </button>
              </div>
              {error && <div className="error-message">{error}</div>}
            </div>
          )}
        </section>
        {downloadUrl && (
          <section className="download-section" aria-live="polite">
            <a
              href={downloadUrl}
              download
              className="download-btn"
              target="_blank"
              rel="noopener noreferrer"
            >
              Download Corrected/Generated Subtitle
            </a>
          </section>
        )}
      </main>
      <footer className="app-footer">
        &copy; {new Date().getFullYear()} Subtitle Sync Platform &middot; Powered by LLMs
      </footer>
    </div>
  );
}

export default App;
