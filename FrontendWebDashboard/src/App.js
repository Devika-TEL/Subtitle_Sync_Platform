import React, { useState } from "react";
import "./App.css";

// Example color palette: Adapt as needed to match extracted branding
const COLORS = {
  primary: "#4638E0",
  accent: "#FF9B4B",
  secondary: "#EFEFFA",
  success: "#5FC979",
  error: "#DF3549",
  background: "#F6F7FC",
  card: "#FFFFFF",
  lightText: "#7C81A1",
  darkText: "#23234B",
  border: "#E1E3ED"
};

const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "zh", name: "Chinese" },
];

function App() {
  const [workflow, setWorkflow] = useState("correction");
  const [correctionFiles, setCorrectionFiles] = useState({ video: null, subtitle: null });
  const [generationFile, setGenerationFile] = useState(null);
  const [generationLang, setGenerationLang] = useState("en");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Event handlers for each workflow
  const handleCorrectionUpload = (e) => {
    const { name, files } = e.target;
    setCorrectionFiles((prev) => ({ ...prev, [name]: files[0] }));
  };

  const handleGenerationUpload = (e) => {
    setGenerationFile(e.target.files[0]);
  };

  // Language selector for generation
  const handleLanguageChange = (e) => {
    setGenerationLang(e.target.value);
  };

  // Submission Handler
  const handleCorrectionSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    // TODO: Connect to API endpoint for correction workflow
    setTimeout(() => {
      setLoading(false);
      setResult({
        url: "#",
        filename: "Corrected_Subtitle.srt",
        message: "The subtitle file has been auto-corrected and is ready to download!"
      });
    }, 1600);
  };

  const handleGenerationSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    // TODO: Connect to API endpoint for generation workflow
    setTimeout(() => {
      setLoading(false);
      setResult({
        url: "#",
        filename: `Generated_${generationLang.toUpperCase()}.srt`,
        message: `Subtitle generated in ${SUPPORTED_LANGUAGES.find(l => l.code === generationLang).name}.`
      });
    }, 1600);
  };

  // Download button
  const handleDownload = () => {
    if (result && result.url !== "#") {
      window.open(result.url, "_blank");
    } else {
      alert("Download endpoint is not set up yet.");
    }
  };

  // Render forms for workflows
  return (
    <div className="dashboard-bg" style={{ background: COLORS.background, minHeight: "100vh" }}>
      {/* Header */}
      <header className="dashboard-header" style={{ background: COLORS.primary, color: "#FFF" }}>
        <div className="header-content">
          <img
            src="https://svgshare.com/i/148G.svg"
            alt="Subtitle Sync Platform"
            className="dashboard-logo"
            style={{ height: 34, marginRight: 15 }}
          />
          <div className="header-titles">
            <h1 className="main-title" style={{ color: "#FFF" }}>
              Subtitle Sync Platform
            </h1>
            <span className="subtitle" style={{ color: COLORS.accent }}>
              Streamlined AI-Powered Subtitle Correction & Generation
            </span>
          </div>
        </div>
      </header>
      {/* Navigation Tabs */}
      <nav className="workflow-nav">
        <div className="workflow-tabs" role="tablist">
          <button
            className={`workflow-tab${workflow === "correction" ? " active" : ""}`}
            style={{
              background: workflow === "correction" ? COLORS.primary : COLORS.secondary,
              color: workflow === "correction" ? "#FFF" : COLORS.primary,
              borderColor: workflow === "correction" ? COLORS.primary : COLORS.secondary
            }}
            onClick={() => {
              setWorkflow("correction");
              setResult(null);
            }}
            role="tab"
            aria-selected={workflow === "correction"}
          >
            <span style={{ fontWeight: 600 }}>
              Correction
            </span>
          </button>
          <button
            className={`workflow-tab${workflow === "generation" ? " active" : ""}`}
            style={{
              background: workflow === "generation" ? COLORS.accent : COLORS.secondary,
              color: workflow === "generation" ? "#FFF" : COLORS.primary,
              borderColor: workflow === "generation" ? COLORS.accent : COLORS.secondary
            }}
            onClick={() => {
              setWorkflow("generation");
              setResult(null);
            }}
            role="tab"
            aria-selected={workflow === "generation"}
          >
            <span style={{ fontWeight: 600 }}>
              Generation
            </span>
          </button>
        </div>
      </nav>
      {/* Workflow Panels */}
      <main className="dashboard-content">
        <div className="dashboard-panel" aria-labelledby={workflow + "-tab"}>
          {workflow === "correction" ? (
            <section className="workflow-section">
              <div className="workflow-card">
                <h2 className="workflow-title" style={{ color: COLORS.primary }}>
                  Subtitle-Audio Quality Check & Correction
                </h2>
                <form className="upload-form" onSubmit={handleCorrectionSubmit}>
                  <label className="file-label" style={{ color: COLORS.darkText }}>
                    <span>Video File</span>
                    <input
                      type="file"
                      name="video"
                      accept="video/*"
                      onChange={handleCorrectionUpload}
                      required
                    />
                  </label>
                  <label className="file-label" style={{ color: COLORS.darkText }}>
                    <span>Subtitle File (.srt, .vtt, etc.)</span>
                    <input
                      type="file"
                      name="subtitle"
                      accept=".srt,.vtt,.ass,.sbv"
                      onChange={handleCorrectionUpload}
                      required
                    />
                  </label>
                  <button
                    className="action-btn"
                    style={{
                      background: COLORS.primary,
                      color: "#FFF",
                      marginTop: 20
                    }}
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? "Processing..." : "Run Correction"}
                  </button>
                </form>
              </div>
            </section>
          ) : (
            <section className="workflow-section">
              <div className="workflow-card">
                <h2 className="workflow-title" style={{ color: COLORS.accent }}>
                  Subtitle Generation & Translation
                </h2>
                <form className="upload-form" onSubmit={handleGenerationSubmit}>
                  <label className="file-label" style={{ color: COLORS.darkText }}>
                    <span>Video File</span>
                    <input
                      type="file"
                      name="generation"
                      accept="video/*"
                      onChange={handleGenerationUpload}
                      required
                    />
                  </label>
                  <label className="file-label" style={{ color: COLORS.darkText }}>
                    <span>Language</span>
                    <select
                      className="language-dropdown"
                      value={generationLang}
                      onChange={handleLanguageChange}
                      style={{
                        background: COLORS.secondary,
                        color: COLORS.darkText,
                        marginLeft: 12,
                        borderRadius: 5,
                        border: `1px solid ${COLORS.border}`,
                        height: 32,
                        fontWeight: 500
                      }}
                    >
                      {SUPPORTED_LANGUAGES.map((lang) => (
                        <option key={lang.code} value={lang.code}>
                          {lang.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="action-btn"
                    style={{
                      background: COLORS.accent,
                      color: "#FFF",
                      marginTop: 20
                    }}
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? "Processing..." : "Generate Subtitles"}
                  </button>
                </form>
              </div>
            </section>
          )}
          {/* Result - Prominent card/section */}
          <section className="result-section">
            {result && (
              <div className="result-card" style={{ background: COLORS.card, borderColor: COLORS.primary }}>
                <h3 className="result-heading" style={{ color: COLORS.primary, fontWeight: 700 }}>
                  {workflow === "correction" ? "Correction Result" : "Generation Result"}
                </h3>
                <p style={{ color: COLORS.darkText, marginBottom: 10 }}>
                  {result.message}
                </p>
                <button
                  className="download-btn"
                  onClick={handleDownload}
                  style={{
                    background: workflow === "correction" ? COLORS.primary : COLORS.accent,
                    color: "#FFF",
                    border: "none",
                    padding: "0.8em 2.1em",
                    borderRadius: 6,
                    fontSize: 18,
                    fontWeight: 600,
                    marginTop: 6
                  }}
                  disabled={loading}
                >
                  Download {result.filename}
                </button>
              </div>
            )}
          </section>
        </div>
      </main>
      {/* Footer */}
      <footer className="dashboard-footer" style={{ background: "#fff", color: COLORS.lightText }}>
        <div className="footer-content">
          <span>
            &copy; {new Date().getFullYear()} Subtitle Sync Platform &mdash; AI Subtitle Solutions
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
