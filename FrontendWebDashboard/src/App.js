import React, { useState } from "react";
import "./App.css";

// Brand color palette
const COLORS = {
  primary: "#4953A6",
  secondary: "#6C73D0",
  accent: "#E8EAF6",
  background: "#F9FAFC",
  navActive: "#373F83",
  navInactive: "#ABADE3",
  border: "#C3C6E1",
  statusSuccess: "#8BC34A",
  statusWarning: "#FBC02D",
  statusError: "#E57373",
};

function App() {
  // State management for workflow selection and forms/results
  const [workflow, setWorkflow] = useState("correction"); // "correction" or "generation"
  const [correctionVideo, setCorrectionVideo] = useState(null);
  const [correctionSubtitle, setCorrectionSubtitle] = useState(null);
  const [generationVideo, setGenerationVideo] = useState(null);
  const [generationLanguage, setGenerationLanguage] = useState("");
  const [status, setStatus] = useState("");
  const [resultUrl, setResultUrl] = useState(null);

  // Supported languages for generation workflow
  const SUPPORTED_LANGUAGES = [
    "English",
    "Spanish",
    "French",
    "German",
    "Chinese",
    // Add more as required
  ];

  // Handlers for input changes
  const handleCorrectionVideoChange = (e) => {
    setCorrectionVideo(e.target.files[0]);
  };

  const handleCorrectionSubtitleChange = (e) => {
    setCorrectionSubtitle(e.target.files[0]);
  };

  const handleGenerationVideoChange = (e) => {
    setGenerationVideo(e.target.files[0]);
  };

  const handleGenerationLanguageChange = (e) => {
    setGenerationLanguage(e.target.value);
  };

  // Reset forms & result when changing workflow
  const handleWorkflowSelect = (wf) => {
    setWorkflow(wf);
    setStatus("");
    setResultUrl(null);
    setCorrectionVideo(null);
    setCorrectionSubtitle(null);
    setGenerationVideo(null);
    setGenerationLanguage("");
  };

  // Demo stub for API call (replace with real API integration)
  const fakeApiSubmit = (formData, endpoint) => {
    setStatus("Processing...");
    setTimeout(() => {
      setStatus("Success! Your file has been processed.");
      setResultUrl("/demo/subtitle_file.srt"); // Simulated download link
    }, 1800);
  };

  // Submission handlers
  const handleCorrectionSubmit = (e) => {
    e.preventDefault();
    if (!correctionVideo || !correctionSubtitle) {
      setStatus("Please upload both a video and a subtitle file.");
      return;
    }
    // Prepare FormData and make the actual API request in production
    const formData = new FormData();
    formData.append("video", correctionVideo);
    formData.append("subtitle", correctionSubtitle);
    fakeApiSubmit(formData, "/api/subtitle-correction");
  };

  const handleGenerationSubmit = (e) => {
    e.preventDefault();
    if (!generationVideo || !generationLanguage) {
      setStatus("Please upload a video and select a language.");
      return;
    }
    const formData = new FormData();
    formData.append("video", generationVideo);
    formData.append("language", generationLanguage);
    fakeApiSubmit(formData, "/api/subtitle-generation");
  };

  // Download handler (for demo)
  const handleDownload = (e) => {
    e.preventDefault();
    // handle download logic
    window.alert("Download would start here (demo).");
  };

  return (
    <div className="app-root" style={{ background: COLORS.background }}>
      <header className="app-header" style={{ background: COLORS.primary }}>
        <h1 className="app-title">Subtitle Sync Platform</h1>
      </header>
      {/* Workflow selection navigation */}
      <nav className="workflow-nav">
        <button
          className={`nav-btn${workflow === "correction" ? " active" : ""}`}
          style={workflow === "correction"
            ? { background: COLORS.navActive, color: "#fff", borderColor: COLORS.primary }
            : { background: COLORS.navInactive, color: "#222", borderColor: COLORS.border }
          }
          onClick={() => handleWorkflowSelect("correction")}
        >
          Subtitle Correction
        </button>
        <button
          className={`nav-btn${workflow === "generation" ? " active" : ""}`}
          style={workflow === "generation"
            ? { background: COLORS.navActive, color: "#fff", borderColor: COLORS.primary }
            : { background: COLORS.navInactive, color: "#222", borderColor: COLORS.border }
          }
          onClick={() => handleWorkflowSelect("generation")}
        >
          Subtitle Generation
        </button>
      </nav>
      {/* Main workflow sections */}
      <main className="workflow-container">
        {/* Subtitle Correction Workflow */}
        {workflow === "correction" && (
          <section className="workflow-panel">
            <h2>Subtitle Correction</h2>
            <form className="upload-form" onSubmit={handleCorrectionSubmit}>
              <div className="form-group">
                <label>Upload Video File</label>
                <input
                  type="file"
                  accept="video/*"
                  onChange={handleCorrectionVideoChange}
                />
              </div>
              <div className="form-group">
                <label>Upload Subtitle File</label>
                <input
                  type="file"
                  accept=".srt,.vtt,.ass"
                  onChange={handleCorrectionSubtitleChange}
                />
              </div>
              <button className="submit-btn" type="submit">
                Run Correction
              </button>
            </form>
          </section>
        )}
        {/* Subtitle Generation Workflow */}
        {workflow === "generation" && (
          <section className="workflow-panel">
            <h2>Subtitle Generation</h2>
            <form className="upload-form" onSubmit={handleGenerationSubmit}>
              <div className="form-group">
                <label>Upload Video File</label>
                <input
                  type="file"
                  accept="video/*"
                  onChange={handleGenerationVideoChange}
                />
              </div>
              <div className="form-group">
                <label>Select Subtitle Language</label>
                <select value={generationLanguage} onChange={handleGenerationLanguageChange}>
                  <option value="">--Select Language--</option>
                  {SUPPORTED_LANGUAGES.map((lang) => (
                    <option key={lang} value={lang}>{lang}</option>
                  ))}
                </select>
              </div>
              <button className="submit-btn" type="submit">
                Generate Subtitles
              </button>
            </form>
          </section>
        )}
        {/* Status / Result section */}
        <section className="status-section">
          {status && (
            <div
              className={`status-msg${status.toLowerCase().includes("success") ? " success"
                : status.toLowerCase().includes("processing") ? " loading" : " error"
              }`}
              style={
                status.toLowerCase().includes("success")
                  ? { color: COLORS.statusSuccess }
                  : status.toLowerCase().includes("processing")
                    ? { color: COLORS.primary }
                    : { color: COLORS.statusError }
              }
            >
              {status}
            </div>
          )}
          {resultUrl && (
            <button className="download-btn" onClick={handleDownload}>
              Download Result
            </button>
          )}
        </section>
      </main>
      <footer className="app-footer">
        <span>
          &copy; {new Date().getFullYear()} Subtitle Sync Platform
        </span>
      </footer>
    </div>
  );
}

export default App;
