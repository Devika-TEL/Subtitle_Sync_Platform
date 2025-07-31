import React, { useState, useEffect, useRef } from "react";
import "./App.css";

/**
 * PUBLIC_INTERFACE
 * App Root for Subtitle Sync Platform Dashboard.
 * Provides UI to select between "Subtitle Correction" and "Subtitle Generation" workflows,
 * upload media/subtitle files, and apply branding color palette.
 */
function App() {
  // Theme toggle
  const [theme, setTheme] = useState("light");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () =>
    setTheme((prevTheme) => (prevTheme === "light" ? "dark" : "light"));

  // Workflow selection: "correction" or "generation"
  const [workflow, setWorkflow] = useState("correction");

  // Subtitle Correction State
  const [correctionVideo, setCorrectionVideo] = useState(null);
  const [correctionSub, setCorrectionSub] = useState(null);

  // Subtitle Generation State
  const [generationVideo, setGenerationVideo] = useState(null);
  const [generationLang, setGenerationLang] = useState("");

  // Dummy handler for submit buttons; API integration pending
  function handleCorrectionSubmit(e) {
    e.preventDefault();
    alert("Correction workflow submitted (API pending).");
  }
  function handleGenerationSubmit(e) {
    e.preventDefault();
    alert("Generation workflow submitted (API pending).");
  }

  // Brand color palette for inline styling and accents
  const brandPalette = {
    primaryBlue: "#20388F",
    accentPurple: "#A41E7E",
    secondaryPink: "#ED4C8B",
    accentYellow: "#FFC60B",
    neutralWhite: "#FFFFFF",
  };

  // List of available languages for generation
  const languageOptions = [
    { code: "en", label: "English" },
    { code: "es", label: "Spanish" },
    { code: "fr", label: "French" },
    { code: "de", label: "German" },
    { code: "zh", label: "Chinese" },
    { code: "ja", label: "Japanese" },
    // Add additional languages as required
  ];

  return (
    <div className="App" style={{ background: brandPalette.neutralWhite }}>
      <header
        className="dashboard-header"
        style={{
          background: `linear-gradient(92deg, ${brandPalette.primaryBlue} 55%, ${brandPalette.accentPurple} 100%)`,
          color: brandPalette.neutralWhite,
        }}
      >
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          style={{
            background: brandPalette.secondaryPink,
            color: brandPalette.neutralWhite,
          }}
        >
          {theme === "light" ? "🌙 Dark" : "☀️ Light"}
        </button>
        <h1 className="dashboard-title">
          Subtitle Sync Platform
        </h1>
        <p className="dashboard-description">
          AI-powered subtitle correction and generation for your videos. Start by selecting a workflow below.
        </p>
      </header>

      <main className="dashboard-main">
        {/* Workflow Selection Tabs */}
        <nav className="workflow-nav" aria-label="Workflow selection">
          <button
            className={`workflow-tab${workflow === "correction" ? " active" : ""}`}
            style={{
              background: workflow === "correction" ? brandPalette.primaryBlue : "transparent",
              color: workflow === "correction" ? brandPalette.neutralWhite : brandPalette.primaryBlue,
              borderColor: brandPalette.primaryBlue,
            }}
            onClick={() => setWorkflow("correction")}
            aria-selected={workflow === "correction"}
          >
            Subtitle Correction
          </button>
          <button
            className={`workflow-tab${workflow === "generation" ? " active" : ""}`}
            style={{
              background: workflow === "generation" ? brandPalette.accentPurple : "transparent",
              color: workflow === "generation" ? brandPalette.neutralWhite : brandPalette.accentPurple,
              borderColor: brandPalette.accentPurple,
            }}
            onClick={() => setWorkflow("generation")}
            aria-selected={workflow === "generation"}
          >
            Subtitle Generation
          </button>
        </nav>

        {/* Workflow Forms */}
        <section className="workflow-content" role="region" aria-labelledby={`${workflow}-tab`}>
          {workflow === "correction" && (
            <form className="workflow-form" onSubmit={handleCorrectionSubmit}>
              <h2 style={{ color: brandPalette.primaryBlue }}>Subtitle Correction</h2>
              <p>Upload your video and existing subtitle file. The system will correct and return a compliant subtitle file.</p>
              <FileUploader
                label="Video File"
                accept="video/*"
                onChange={setCorrectionVideo}
                value={correctionVideo}
                required
                brandColor={brandPalette.primaryBlue}
              />
              <FileUploader
                label="Subtitle File"
                accept=".srt,.vtt,.ass,.sub,.txt,.dfxp,.sbv"
                onChange={setCorrectionSub}
                value={correctionSub}
                required
                brandColor={brandPalette.accentPurple}
              />
              <button
                className="submit-btn"
                type="submit"
                style={{
                  background: brandPalette.secondaryPink,
                  color: brandPalette.neutralWhite,
                  marginTop: 24,
                }}
              >
                Submit for Correction
              </button>
            </form>
          )}

          {workflow === "generation" && (
            <form className="workflow-form" onSubmit={handleGenerationSubmit}>
              <h2 style={{ color: brandPalette.accentPurple }}>Subtitle Generation</h2>
              <p>Upload a video to generate subtitles. Select output language for translation.</p>
              <FileUploader
                label="Video File"
                accept="video/*"
                onChange={setGenerationVideo}
                value={generationVideo}
                required
                brandColor={brandPalette.accentPurple}
              />
              <div className="input-group">
                <label htmlFor="language-select" className="input-label" style={{ color: brandPalette.primaryBlue }}>
                  Language
                </label>
                <select
                  className="input-select"
                  id="language-select"
                  value={generationLang}
                  onChange={(e) => setGenerationLang(e.target.value)}
                  required
                  style={{
                    borderColor: brandPalette.primaryBlue,
                    color: brandPalette.primaryBlue,
                  }}
                >
                  <option value="" disabled>
                    -- Select Language --
                  </option>
                  {languageOptions.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                className="submit-btn"
                type="submit"
                style={{
                  background: brandPalette.accentYellow,
                  color: brandPalette.primaryBlue,
                  marginTop: 24,
                }}
              >
                Generate Subtitles
              </button>
            </form>
          )}
        </section>
      </main>

      <footer className="dashboard-footer" style={{ background: brandPalette.primaryBlue, color: brandPalette.neutralWhite }}>
        <span>
          © {new Date().getFullYear()} Subtitle Sync Platform &mdash; All Rights Reserved.
        </span>
      </footer>
    </div>
  );
}

/**
 * PUBLIC_INTERFACE
 * File uploader component for video and subtitle files.
 * Props:
 *   - label: string (display label)
 *   - accept: string (file MIME types)
 *   - onChange: function (called with selected file or null)
 *   - value: File | null (current file)
 *   - required: bool (optional)
 *   - brandColor: string (accent color for highlight)
 */
function FileUploader({ label, accept, onChange, value, required, brandColor }) {
  const inputRef = useRef();
  return (
    <div className="input-group">
      <label className="input-label" style={{ color: brandColor }}>
        {label} {required && <span style={{ color: "#ED4C8B" }}>*</span>}
      </label>
      <div className="custom-file-input">
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          style={{ display: "none" }}
          onChange={(e) => onChange(e.target.files?.[0] || null)}
          tabIndex={0}
        />
        <button
          type="button"
          className="file-btn"
          style={{
            borderColor: brandColor,
            color: brandColor,
            background: "transparent",
          }}
          onClick={() => inputRef.current?.click()}
        >
          {value ? `Selected: ${value.name}` : `Select ${label}`}
        </button>
        {value && (
          <button
            type="button"
            className="file-clear-btn"
            style={{
              color: "#A41E7E",
              border: "none",
              background: "transparent",
              marginLeft: 12,
              cursor: "pointer",
            }}
            tabIndex={0}
            title="Clear selected file"
            aria-label="Clear file"
            onClick={() => {
              onChange(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}

export default App;
