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
  // Language/validation states for Subtitle Generation workflow
  const [languages] = useState([
    { code: "", name: "Select Language" },
    { code: "en", name: "English" },
    { code: "es", name: "Spanish" },
    { code: "fr", name: "French" },
    { code: "de", name: "German" },
    { code: "zh", name: "Chinese" },
    { code: "hi", name: "Hindi" },
    // Add more as needed
  ]);
  const [selectedLanguage, setSelectedLanguage] = useState("");
  const [languageTouched, setLanguageTouched] = useState(false);

  // Status/result states (could be shared across workflows)
  const [jobStatus, setJobStatus] = useState("");
  const [jobResultUrl, setJobResultUrl] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  // Handlers for forms
  const handleCorrectionVideoChange = (e) => {
    setCorrectionVideoFile(e.target.files[0]);
  };
  const handleCorrectionSubtitleChange = (e) => {
    setCorrectionSubtitleFile(e.target.files[0]);
  };
  const handleGenerationVideoChange = (e) => {
    setGenerationVideoFile(e.target.files[0]);
    setError("");
  };

  // Language selection
  const handleLanguageChange = (e) => {
    setSelectedLanguage(e.target.value);
    setLanguageTouched(true);
    setError("");
  };

  // PUBLIC_INTERFACE
  const handleCorrectionSubmit = (e) => {
    e.preventDefault();
    setJobStatus("Processing subtitle correction...");
    setJobResultUrl(null);
    setTimeout(() => {
      setJobStatus("Subtitle correction completed!");
      setJobResultUrl("/download/corrected-subtitle.srt");
    }, 1500);
  };

  // PUBLIC_INTERFACE
  const handleGenerationSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLanguageTouched(true);

    if (!generationVideoFile) {
      setError("Please select a video file to upload.");
      return;
    }
    if (!selectedLanguage) {
      setError("Please select a language before submitting.");
      return;
    }

    setUploading(true);
    setJobStatus("Generating new subtitles...");
    setJobResultUrl(null);

    try {
      const formData = new FormData();
      formData.append("video", generationVideoFile);
      formData.append("language", selectedLanguage);

      // Replace below with actual backend call!
      // const response = await fetch('/api/generate_subtitles', {
      //   method: 'POST',
      //   body: formData,
      // });
      // if (!response.ok) throw new Error('Subtitle generation failed.');
      // const data = await response.json();
      // setJobStatus("Subtitle generation completed!");
      // setJobResultUrl(data.subtitle_url);

      // For demo/stub:
      setTimeout(() => {
        setUploading(false);
        setJobStatus("Subtitle generation completed!");
        setJobResultUrl("/download/generated-subtitle.srt");
      }, 1500);

    } catch (err) {
      setError(err.message || "An error occurred");
      setUploading(false);
      setJobStatus("");
    }
  };

  // Helper for language selector CSS
  const languageSelectorClass =
    languageTouched && !selectedLanguage ? "language-invalid" : "";

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
      <label className="file-label" htmlFor="generation-language-selector" style={{ marginBottom: '0.1rem' }}>
        Choose Language <span style={{ color: "red" }}>*</span>
      </label>
      <select
        id="generation-language-selector"
        value={selectedLanguage}
        onChange={handleLanguageChange}
        onBlur={() => setLanguageTouched(true)}
        className={languageSelectorClass}
        data-testid="language-selector"
        required
      >
        {languages.map((lang) => (
          <option key={lang.code} value={lang.code} disabled={lang.code === ""}>
            {lang.name}
          </option>
        ))}
      </select>
      {languageTouched && !selectedLanguage && (
        <div
          style={{ color: "red", fontSize: "0.95em", marginTop: "4px" }}
          data-testid="language-required-message"
        >
          Language is required.
        </div>
      )}
      <button
        className="primary-button"
        type="submit"
        disabled={uploading}
        style={{ marginTop: '0.5rem' }}
        data-testid="generate-btn"
      >
        {uploading ? "Generating..." : "Generate Subtitles"}
      </button>
      {error && <div className="error-message" data-testid="error-message">{error}</div>}
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
