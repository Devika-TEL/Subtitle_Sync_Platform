import React, { useState, useRef } from "react";
import "./App.css";

/**
 * Subtitle Sync Platform Main Dashboard (No polling, synchronous processing).
 * After the user uploads and starts correction/generation, the file is sent to the backend, 
 * which immediately returns the corrected/generated file or its download URL. The download 
 * button or link is shown as soon as the API responds.
 */
// PUBLIC_INTERFACE
function App() {
  // UI state
  const [isCorrectionMode, setIsCorrectionMode] = useState(true);
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
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

  const handleSubtitleChange = (e) => {
    setSubtitleFile(e.target.files[0]);
    setDownloadUrl("");
    setError("");
  };

  // PUBLIC_INTERFACE
  const handleProcess = async () => {
    /**
     * Uploads files to backend, waits for result, and reveals download as soon as processing is done (synchronous pattern).
     */
    setProcessing(true);
    setError("");
    setDownloadUrl("");

    const formData = new FormData();

    if (videoFile) formData.append("video", videoFile);
    if (isCorrectionMode && subtitleFile) {
      formData.append("subtitle", subtitleFile);
    }

    try {
      // Use environment variable for API endpoint base
      const endpoint = isCorrectionMode
        ? `${process.env.REACT_APP_API_BASE}/subtitle/correct`
        : `${process.env.REACT_APP_API_BASE}/subtitle/generate`;

      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Processing failed. Please try again.");
      }

      // Accept either blob (file) or JSON { download_url: ... }
      const contentType = response.headers.get("Content-Type") || "";
      let url = "";
      if (contentType.includes("application/json")) {
        const data = await response.json();
        url = data.download_url;
        if (!url) throw new Error("No download URL in response.");
      } else {
        // File (blob)
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
    setDownloadUrl("");
    setError("");
    setProcessing(false);
    if (videoInputRef.current) videoInputRef.current.value = null;
    if (subtitleInputRef.current) subtitleInputRef.current.value = null;
  };

  return (
    <div className="App">
      <header className="app-header" role="banner">
        <div className="brand-logo-container">
          <span className="brand-logo">🎬</span>
          <span className="brand-title">Subtitle Sync Platform</span>
        </div>
        <div className="brand-subtitle">AI-powered Subtitle Correction & Generation</div>
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
                  disabled={
                    processing ||
                    !videoFile ||
                    !subtitleFile
                  }
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
              <div className="actions">
                <button
                  className="primary-button"
                  onClick={handleProcess}
                  disabled={processing || !videoFile}
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

        {/* Download button shown as soon as backend responds */}
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
