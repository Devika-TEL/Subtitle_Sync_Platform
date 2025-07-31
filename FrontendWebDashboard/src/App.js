import React, { useState } from "react";
import "./App.css";

// PUBLIC_INTERFACE
function App() {
  // State for workflow switching
  const [activeWorkflow, setActiveWorkflow] = useState("correction"); // "correction" or "generation"
  // File upload states
  const [correctionVideoFile, setCorrectionVideoFile] = useState(null);
  const [correctionSubtitleFile, setCorrectionSubtitleFile] = useState(null);
  const [generationVideoFile, setGenerationVideoFile] = useState(null);
  // Status/result states (stub - replace with backend integration)
  const [jobStatus, setJobStatus] = useState("");
  const [jobResultUrl, setJobResultUrl] = useState(null);

  // Handlers for forms
  const handleCorrectionVideoChange = (e) => {
    setCorrectionVideoFile(e.target.files[0]);
  };
  const handleCorrectionSubtitleChange = (e) => {
    setCorrectionSubtitleFile(e.target.files[0]);
  };
  const handleGenerationVideoChange = (e) => {
    setGenerationVideoFile(e.target.files[0]);
  };

  // Submit handlers (TODO: call backend API)
  const handleCorrectionSubmit = (e) => {
    e.preventDefault();
    setJobStatus("Processing subtitle correction...");
    setTimeout(() => {
      setJobStatus("Subtitle correction completed!");
      setJobResultUrl("/download/corrected-subtitle.srt");
    }, 1500);
  };

  const handleGenerationSubmit = (e) => {
    e.preventDefault();
    setJobStatus("Generating new subtitles...");
    setTimeout(() => {
      setJobStatus("Subtitle generation completed!");
      setJobResultUrl("/download/generated-subtitle.srt");
    }, 1500);
  };

  // Renderers
  const CorrectionTab = (
    <form className="workflow-card" onSubmit={handleCorrectionSubmit} aria-label="Subtitle Correction Form">
      <h2 className="workflow-card-header">Subtitle Correction</h2>
      <label className="file-label" htmlFor="correction-video-upload">
        Video File <span aria-hidden="true">*</span>
      </label>
      <input
        id="correction-video-upload"
        type="file"
        accept="video/*"
        onChange={handleCorrectionVideoChange}
        required
      />
      <label className="file-label" htmlFor="correction-subtitle-upload">
        Subtitle File <span aria-hidden="true">*</span>
      </label>
      <input
        id="correction-subtitle-upload"
        type="file"
        accept=".srt,.vtt,.ass,.sub"
        onChange={handleCorrectionSubtitleChange}
        required
      />
      <button className="primary-button" type="submit">
        Start Correction
      </button>
    </form>
  );
  const GenerationTab = (
    <form className="workflow-card" onSubmit={handleGenerationSubmit} aria-label="Subtitle Generation Form">
      <h2 className="workflow-card-header">Subtitle Generation</h2>
      <label className="file-label" htmlFor="generation-video-upload">
        Video File <span aria-hidden="true">*</span>
      </label>
      <input
        id="generation-video-upload"
        type="file"
        accept="video/*"
        onChange={handleGenerationVideoChange}
        required
      />
      <button className="primary-button" type="submit">
        Start Generation
      </button>
    </form>
  );

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
          className={`tab-btn${activeWorkflow === "correction" ? " active" : ""}`}
          onClick={() => setActiveWorkflow("correction")}
          aria-selected={activeWorkflow === "correction"}
          aria-controls="correction-tab"
        >
          Subtitle Correction
        </button>
        <button
          className={`tab-btn${activeWorkflow === "generation" ? " active" : ""}`}
          onClick={() => setActiveWorkflow("generation")}
          aria-selected={activeWorkflow === "generation"}
          aria-controls="generation-tab"
        >
          Subtitle Generation
        </button>
      </nav>
      <main className="main-content">
        <section id="workflow-forms" aria-live="polite">
          {activeWorkflow === "correction" ? CorrectionTab : GenerationTab}
        </section>
        <section className="job-status-card" aria-live="polite">
          <h3 className="job-status-header">
            {jobStatus ? "Job Status" : "Status & Results"}
          </h3>
          <div className="job-status-details">
            {jobStatus ? (
              <span className="status-text">{jobStatus}</span>
            ) : (
              <span className="status-placeholder">No jobs running. Start a workflow above.</span>
            )}
            {jobResultUrl && (
              <a
                href={jobResultUrl}
                className="primary-button result-download"
                download
                aria-label="Download Result"
              >
                Download Result
              </a>
            )}
          </div>
        </section>
      </main>
      <footer className="app-footer">
        &copy; {new Date().getFullYear()} Subtitle Sync Platform &middot; Powered by LLMs
      </footer>
    </div>
  );
}

export default App;
