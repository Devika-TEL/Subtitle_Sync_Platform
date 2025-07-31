import React, { useState, useEffect, useRef } from "react";
import "./App.css";

/**
 * PUBLIC_INTERFACE
 * App Root for Subtitle Sync Platform Dashboard.
 * Connects upload/workflow UI to FastAPI backend, manages uploads, job polling, and result/error display.
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

  // --- Correction State ---
  const [correctionVideo, setCorrectionVideo] = useState(null);
  const [correctionSub, setCorrectionSub] = useState(null);

  // --- Generation State ---
  const [generationVideo, setGenerationVideo] = useState(null);
  const [generationLang, setGenerationLang] = useState("");

  // --- UI/Status State ---
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // {status, message, progress, ...}
  const [downloadLink, setDownloadLink] = useState(null);
  const [error, setError] = useState(null);
  const [polling, setPolling] = useState(false);

  // Brand color palette for styling
  const brandPalette = {
    primaryBlue: "#20388F",
    accentPurple: "#A41E7E",
    secondaryPink: "#ED4C8B",
    accentYellow: "#FFC60B",
    neutralWhite: "#FFFFFF",
  };

  // Language options
  const languageOptions = [
    { code: "en", label: "English" },
    { code: "es", label: "Spanish" },
    { code: "fr", label: "French" },
    { code: "de", label: "German" },
    { code: "zh", label: "Chinese" },
    { code: "ja", label: "Japanese" },
    // Add more languages as needed
  ];

  // Reset workflow state
  function resetAllStates() {
    setJobId(null);
    setJobStatus(null);
    setDownloadLink(null);
    setError(null);
    setUploading(false);
    setPolling(false);
  }

  // Correction handler (video+subtitle)
  async function handleCorrectionSubmit(e) {
    e.preventDefault();
    resetAllStates();
    if (!correctionVideo || !correctionSub) {
      setError("Please select both video and subtitle files.");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("video_file", correctionVideo);
      formData.append("subtitle_file", correctionSub);

      const API_BASE = process.env.REACT_APP_API_BASE || "";
      const resp = await fetch(`${API_BASE}/api/correction`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        let msg = "Server error during upload";
        try {
          const data = await resp.json();
          msg = data.detail || JSON.stringify(data);
        } catch {} // fallback to generic
        throw new Error(msg);
      }
      const data = await resp.json();
      setJobId(data.job_id);
      setJobStatus({ status: data.status, message: data.message });
      setUploading(false);
      setPolling(true);
    } catch (err) {
      setUploading(false);
      setError(
        err?.message ||
          "Failed to upload files. Please try again or check network connection."
      );
    }
  }

  // Generation handler (video+lang)
  async function handleGenerationSubmit(e) {
    e.preventDefault();
    resetAllStates();
    if (!generationVideo || !generationLang) {
      setError("Please select a video and output language.");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("video_file", generationVideo);
      formData.append("language", generationLang);
      const API_BASE = process.env.REACT_APP_API_BASE || "";
      const resp = await fetch(`${API_BASE}/api/generation`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        let msg = "Server error during upload";
        try {
          const data = await resp.json();
          msg = data.detail || JSON.stringify(data);
        } catch {}
        throw new Error(msg);
      }
      const data = await resp.json();
      setJobId(data.job_id);
      setJobStatus({ status: data.status, message: data.message });
      setUploading(false);
      setPolling(true);
    } catch (err) {
      setUploading(false);
      setError(
        err?.message ||
          "Failed to upload file. Please try again or check network connection."
      );
    }
  }

  // Poll job status when jobId & polling
  useEffect(() => {
    let pollInt = null;
    const API_BASE = process.env.REACT_APP_API_BASE || "";
    if (jobId && polling) {
      // Start polling
      pollInt = setInterval(async () => {
        try {
          const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`);
          if (!resp.ok) throw new Error("Could not check job status");
          const job = await resp.json();
          setJobStatus(job);

          if (
            job.status === "success" ||
            job.status === "error" ||
            job.status === "cancelled"
          ) {
            setPolling(false);
            // For "success", try to get download url for output subtitle
            if (
              job.status === "success" &&
              job.output_subtitle_id &&
              job.output_subtitle_id !== null
            ) {
              // Try fetch subtitle record to get path/filename
              try {
                const subResp = await fetch(
                  `${API_BASE}/api/subtitles/${job.output_subtitle_id}`
                );
                if (subResp.ok) {
                  const sub = await subResp.json();
                  // For now, we do not have a direct static subtitle file serving path.
                  // Instead, we display a note and the subtitle's stored location.
                  setDownloadLink(null);
                }
              } catch {}
            }
          }
        } catch (e) {
          setError(
            "Error updating job status. Please refresh or try again later."
          );
          setPolling(false);
        }
      }, 1500);
    }
    return () => {
      if (pollInt) clearInterval(pollInt);
    };
    // eslint-disable-next-line
  }, [jobId, polling]);

  // Helper to extract filename from full path
  function getFileNameFromPath(path) {
    if (!path) return "";
    return path.split("/").pop();
  }

  // Notice - clear error if any state changes
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(null), 9000);
      return () => clearTimeout(t);
    }
  }, [error]);

  // Render upload/progress/result panel for workflows
  function renderStatusPanel() {
    // Error
    if (error)
      return (
        <div
          style={{
            margin: "20px 0 0 0",
            color: "#A41E7E",
            background: "#ffe3ed",
            border: "1.5px solid #ED4C8B",
            padding: "10px 16px",
            borderRadius: 9,
            fontWeight: 500,
          }}
        >
          Error: {error}
        </div>
      );
    if (uploading)
      return (
        <div style={{ margin: "20px 0 0 0", color: brandPalette.primaryBlue }}>
          Uploading... Please wait.
        </div>
      );
    if (jobId && jobStatus) {
      return (
        <div
          style={{
            marginTop: 20,
            background: "#f8f6fe",
            border: "1.2px solid #a3c2fe",
            borderRadius: 8,
            padding: "18px 13px 9px 13px",
          }}
        >
          <strong>
            Job Status:{" "}
            <span style={{ color: statusColor(jobStatus.status) }}>
              {jobStatus.status?.toUpperCase() || "loading..."}
            </span>
          </strong>
          <br />
          <span>
            {jobStatus.message ||
              (jobStatus.status === "success"
                ? "Complete"
                : "Processing...")}
          </span>
          {jobStatus.progress !== undefined &&
            jobStatus.status !== "success" && (
              <ProgressBar progress={jobStatus.progress || 10} />
            )}
          {downloadLink ? (
            <div style={{ marginTop: 14 }}>
              <a
                href={downloadLink}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: brandPalette.secondaryPink,
                  fontWeight: 600,
                  textDecoration: "underline",
                  fontSize: 17,
                }}
                download
              >
                Download Corrected/Generated Subtitle
              </a>
            </div>
          ) : (
            jobStatus &&
            jobStatus.status === "success" &&
            jobStatus.output_subtitle_id && (
              <div style={{
                color: brandPalette.primaryBlue,
                marginTop: 12,
                background: "#f0f1fc",
                borderRadius: 7,
                fontSize: 15,
                padding: "9px 11px"
              }}>
                Subtitle output is ready! <br />
                No direct download link is available yet.<br />
                Please contact your administrator, or check the backend storage for the final subtitle file.
              </div>
            )
          )}
        </div>
      );
    }
    return null;
  }

  // Color by job status
  function statusColor(status) {
    if (!status) return "#8c8ca6";
    if (status === "pending") return brandPalette.secondaryPink;
    if (status === "in_progress") return brandPalette.primaryBlue;
    if (status === "success") return "#20A664"; // green
    if (status === "error" || status === "cancelled") return "#A41E7E";
    return "#888";
  }

  // ProgressBar: Simple filling bar component
  function ProgressBar({ progress }) {
    return (
      <div
        style={{
          marginTop: 12,
          width: "98%",
          height: 14,
          background: "#e4eafd",
          borderRadius: 7,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: (progress || 1) + "%",
            height: "100%",
            background: brandPalette.primaryBlue,
            transition: "width 0.6s cubic-bezier(.6,.1,.46,1.5)",
          }}
        />
      </div>
    );
  }

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
        <h1 className="dashboard-title">Subtitle Sync Platform</h1>
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
            onClick={() => {
              setWorkflow("correction");
              resetAllStates();
              setCorrectionVideo(null); setCorrectionSub(null);
            }}
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
            onClick={() => {
              setWorkflow("generation");
              resetAllStates();
              setGenerationVideo(null); setGenerationLang("");
            }}
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
              <p>Upload your video and an existing subtitle file.<br />
                <span style={{fontSize:'0.93em',color:brandPalette.accentPurple}}>
                  Supported subtitle formats: SRT, VTT, ASS, SUB, TXT, DFXP, SBV.<br />
                  Recommended video format: MP4, MOV, AVI, MKV.<br />
                  Final output will match the uploaded subtitle's format.
                </span>
                <br />
                The system will correct and return a compliant subtitle file.
              </p>
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
                disabled={uploading}
              >
                Submit for Correction
              </button>
              {renderStatusPanel()}
            </form>
          )}

          {workflow === "generation" && (
            <form className="workflow-form" onSubmit={handleGenerationSubmit}>
              <h2 style={{ color: brandPalette.accentPurple }}>Subtitle Generation</h2>
              <p>
                Upload a video file to generate subtitles.
                <br />
                <span style={{fontSize:'0.93em',color:brandPalette.accentPurple}}>
                  Recommended video format: MP4, MOV, AVI, MKV.<br />
                  Subtitles will be generated using AI and translated if you choose a language different from the video language.<br />
                  Output will be in SRT format unless the backend determines otherwise.
                </span>
                <br />
                Select output language for translation.
              </p>
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
                disabled={uploading}
              >
                Generate Subtitles
              </button>
              {renderStatusPanel()}
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
