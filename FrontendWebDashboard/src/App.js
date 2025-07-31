import React, { useState, useRef } from "react";
import "./App.css";

// Language options for generation workflow
const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  // Add more as needed
];

// PUBLIC_INTERFACE
function App() {
  // App-level UI state
  const [workflow, setWorkflow] = useState("correction"); // 'correction' or 'generation'
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
  const [targetLang, setTargetLang] = useState(LANGUAGES[0].code);
  const [status, setStatus] = useState("");
  const [resultReady, setResultReady] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const videoInputRef = useRef();
  const subtitleInputRef = useRef();

  // Simulated backend call
  const handleProcess = () => {
    setStatus("Processing. This may take a while...");
    setTimeout(() => {
      setStatus("Success! Your subtitles are ready.");
      setResultReady(true);
    }, 2000);
  };

  // Handle combined upload panel logic
  const handleUpload = (e, isVideo = false) => {
    if (isVideo) {
      setVideoFile(e.target.files[0]);
    } else {
      setSubtitleFile(e.target.files[0]);
    }
  };

  const handleDownload = () => {
    setDownloading(true);
    setTimeout(() => {
      // Simulate trigger download
      setDownloading(false);
      setStatus("Downloaded successfully.");
      setResultReady(false);
    }, 1200);
  };

  // Reset all logic when workflow changes
  const switchWorkflow = (type) => {
    setWorkflow(type);
    setVideoFile(null);
    setSubtitleFile(null);
    setStatus("");
    setResultReady(false);
    setTargetLang(LANGUAGES[0].code);
    if (videoInputRef.current) videoInputRef.current.value = "";
    if (subtitleInputRef.current) subtitleInputRef.current.value = "";
  };

  // Branded header
  const BrandHeader = () => (
    <header className="app-header">
      <span className="brand-icon" role="img" aria-label="subtitle-sync">
        🎬
      </span>
      <span className="brand-title">Subtitle Sync Platform</span>
    </header>
  );

  // Workflow selection tabs/cards
  const WorkflowTabs = () => (
    <nav className="workflow-tabs">
      <button
        className={`workflow-tab${workflow === "correction" ? " active" : ""}`}
        onClick={() => switchWorkflow("correction")}
        aria-pressed={workflow === "correction"}
      >
        Subtitle Correction
      </button>
      <button
        className={`workflow-tab${workflow === "generation" ? " active" : ""}`}
        onClick={() => switchWorkflow("generation")}
        aria-pressed={workflow === "generation"}
      >
        Subtitle Generation
      </button>
    </nav>
  );

  // Upload/Input panel for each workflow
  const UploadPanel = () => (
    <section className="upload-card">
      <label className="upload-label">
        <span>Video File</span>
        <input
          type="file"
          accept="video/*"
          ref={videoInputRef}
          onChange={(e) => handleUpload(e, true)}
        />
        {videoFile && (
          <span className="upload-filename">{videoFile.name}</span>
        )}
      </label>
      {workflow === "correction" && (
        <label className="upload-label">
          <span>Subtitle File</span>
          <input
            type="file"
            accept=".srt,.vtt,.ass,.ssa"
            ref={subtitleInputRef}
            onChange={handleUpload}
          />
          {subtitleFile && (
            <span className="upload-filename">{subtitleFile.name}</span>
          )}
        </label>
      )}
      {workflow === "generation" && (
        <label className="upload-label">
          <span>Target Language</span>
          <select
            className="lang-select"
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
          >
            {LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.label}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        className="primary-btn"
        disabled={
          !videoFile ||
          (workflow === "correction" && !subtitleFile) ||
          status.startsWith("Processing")
        }
        onClick={handleProcess}
      >
        {workflow === "correction" ? "Validate & Correct" : "Generate Subtitles"}
      </button>
    </section>
  );

  // Status/Result panel
  const StatusCard = () =>
    status ? (
      <section className="status-card" aria-live="polite">
        <p className="status-msg">{status}</p>
        {resultReady && (
          <button
            className="download-btn"
            onClick={handleDownload}
            disabled={downloading}
            aria-disabled={downloading}
          >
            {downloading ? "Downloading..." : "Download Result"}
          </button>
        )}
      </section>
    ) : null;

  // Main dashboard render
  return (
    <div className="dashboard-bg">
      <BrandHeader />
      <main className="dashboard-main">
        <WorkflowTabs />
        <UploadPanel />
        <StatusCard />
      </main>
      <footer className="app-footer">
        &copy; {new Date().getFullYear()} Subtitle Sync Platform
      </footer>
    </div>
  );
}

export default App;
