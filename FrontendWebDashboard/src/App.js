import React, { useState } from "react";
import "./App.css";

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

  // Event handlers
  const handleCorrectionUpload = (e) => {
    const { name, files } = e.target;
    setCorrectionFiles((prev) => ({ ...prev, [name]: files[0] }));
  };

  const handleGenerationUpload = (e) => {
    setGenerationFile(e.target.files[0]);
  };

  const handleLanguageChange = (e) => {
    setGenerationLang(e.target.value);
  };

  const handleCorrectionSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    // Simulate workflow
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
    setTimeout(() => {
      setLoading(false);
      setResult({
        url: "#",
        filename: `Generated_${generationLang.toUpperCase()}.srt`,
        message: `Subtitle generated in ${SUPPORTED_LANGUAGES.find(l => l.code === generationLang).name}.`
      });
    }, 1600);
  };

  const handleDownload = () => {
    if (result && result.url !== "#") {
      window.open(result.url, "_blank");
    } else {
      alert("Download endpoint is not set up yet.");
    }
  };

  return (
    <div className="dashboard-bg">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-content">
          <img
            src="https://svgshare.com/i/148G.svg"
            alt="Subtitle Sync Platform"
            className="dashboard-logo"
          />
          <div className="header-titles">
            <h1 className="main-title">Subtitle Sync Platform</h1>
            <span className="subtitle">
              Streamlined AI-Powered Subtitle Correction &amp; Generation
            </span>
          </div>
        </div>
      </header>
      {/* Navigation Tabs */}
      <nav className="workflow-nav">
        <div className="workflow-tabs" role="tablist">
          <button
            className={`workflow-tab${workflow === "correction" ? " active" : ""}`}
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
                <h2 className="workflow-title">
                  Subtitle-Audio Quality Check & Correction
                </h2>
                <form className="upload-form" onSubmit={handleCorrectionSubmit}>
                  <label className="file-label">
                    <span>Video File</span>
                    <input
                      type="file"
                      name="video"
                      accept="video/*"
                      onChange={handleCorrectionUpload}
                      required
                    />
                  </label>
                  <label className="file-label">
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
              <div className="workflow-card" style={{background: "var(--evp-pink)", borderColor: "var(--evp-yellow)"}}>
                <h2 className="workflow-title" style={{color: "var(--evp-yellow)"}}>
                  Subtitle Generation &amp; Translation
                </h2>
                <form className="upload-form" onSubmit={handleGenerationSubmit}>
                  <label className="file-label">
                    <span>Video File</span>
                    <input
                      type="file"
                      name="generation"
                      accept="video/*"
                      onChange={handleGenerationUpload}
                      required
                    />
                  </label>
                  <label className="file-label">
                    <span>Language</span>
                    <select
                      className="language-dropdown"
                      value={generationLang}
                      onChange={handleLanguageChange}
                      style={{
                        marginLeft: 12
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
                    style={{background:"var(--evp-yellow)", color:"var(--evp-blue)"}}
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
              <div className="result-card">
                <h3 className="result-heading">
                  {workflow === "correction" ? "Correction Result" : "Generation Result"}
                </h3>
                <p style={{ marginBottom: 10 }}>
                  {result.message}
                </p>
                <button
                  className="download-btn"
                  onClick={handleDownload}
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
      <footer className="dashboard-footer">
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
