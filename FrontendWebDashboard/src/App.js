import React, { useState, useEffect, useRef } from "react";
import "./App.css";

/**
 * PUBLIC_INTERFACE
 * App Root for Subtitle Sync Platform Dashboard.
 * Connects upload/workflow UI to FastAPI backend, manages uploads, job polling, accessible feedback, and result/error display.
 */
function App() {
  // Theme toggle (accessible with ARIA & focus-visible)
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
  const [announce, setAnnounce] = useState(""); // For aria-live

  // Brand color palette for styling (aligned with extracted palette)
  const brandPalette = {
    primaryBlue: "#20388F",
    accentPurple: "#A41E7E",
    secondaryPink: "#ED4C8B",
    accentYellow: "#FFC60B",
    neutralWhite: "#FFFFFF",
  };

  // Language options (expandable)
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
    setAnnounce("");
  }

  // Correction handler (video+subtitle)
  async function handleCorrectionSubmit(e) {
    e.preventDefault();
    resetAllStates();
    if (!correctionVideo || !correctionSub) {
      setError("Please select both a video file and a subtitle file.");
      setAnnounce("File selection error.");
      // Focus first missing input
      setTimeout(() => {
        if (!correctionVideo) document.getElementById("video-file-correction")?.focus();
        else if (!correctionSub) document.getElementById("subtitle-file-correction")?.focus();
      }, 140);
      return;
    }
    setUploading(true);
    setAnnounce("Uploading files for correction.");
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
      setAnnounce("Subtitle correction job started.");
    } catch (err) {
      setUploading(false);
      setError(
        err?.message ||
          "Failed to upload files. Please try again or check network connection."
      );
      setAnnounce("Upload failed.");
    }
  }

  // Generation handler (video+lang)
  async function handleGenerationSubmit(e) {
    e.preventDefault();
    resetAllStates();
    if (!generationVideo || !generationLang) {
      setError("Please select a video and output language.");
      setAnnounce("File selection error.");
      // Focus first missing input
      setTimeout(() => {
        if (!generationVideo) document.getElementById("video-file-generation")?.focus();
        else if (!generationLang) document.getElementById("language-select")?.focus();
      }, 140);
      return;
    }
    setUploading(true);
    setAnnounce("Uploading file for generation.");
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
      setAnnounce("Subtitle generation job started.");
    } catch (err) {
      setUploading(false);
      setError(
        err?.message ||
          "Failed to upload file. Please try again or check network connection."
      );
      setAnnounce("Upload failed.");
    }
  }

  // Poll job status when jobId & polling
  useEffect(() => {
    let pollInt = null;
    const API_BASE = process.env.REACT_APP_API_BASE || "";
    if (jobId && polling) {
      pollInt = setInterval(async () => {
        try {
          const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`);
          if (!resp.ok) throw new Error("Could not check job status");
          const job = await resp.json();
          setJobStatus(job);

          // Announce status change for screen readers
          setAnnounce(
            job.status === "success"
              ? "Job completed successfully."
              : job.status === "error"
              ? "Job failed."
              : `Job status: ${job.status}.`
          );

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
                  // Optionally display a download link if backend supports static files
                  setDownloadLink(null);
                }
              } catch {}
            }
          }
        } catch (e) {
          setError(
            "Error updating job status. Please refresh or try again later."
          );
          setAnnounce("Error getting job status.");
          setPolling(false);
        }
      }, 1500);
    }
    return () => {
      if (pollInt) clearInterval(pollInt);
    };
    // eslint-disable-next-line
  }, [jobId, polling]);

  // Notice - clear error if any state changes and update aria-live
  useEffect(() => {
    if (error) {
      setAnnounce("Error: " + error);
      const t = setTimeout(() => setError(null), 9000);
      return () => clearTimeout(t);
    }
  }, [error]);

  // Focus management: announce live polite region to a11y users
  useEffect(() => {
    if (announce && announce.length > 2) {
      // Focus on status region for screenreader feedback
      const region = document.getElementById("status-announcement");
      if (region) region.focus();
    }
  }, [announce]);

  // Render upload/progress/result panel for workflows, with a11y enhancements, helpful status notes, and validation feedback
  function renderStatusPanel() {
    // Error with focus and bold style for a11y (role=alert)
    if (error)
      return (
        <div
          role="alert"
          aria-live="assertive"
          tabIndex={-1}
          style={{
            margin: "20px 0 0 0",
            color: "#A41E7E",
            background: "#ffe3ed",
            border: "1.5px solid #ED4C8B",
            padding: "10px 16px",
            borderRadius: 9,
            fontWeight: 600,
            outline: "2.5px solid #ED4C8B",
            boxShadow: "0 3px 10px 0 #ed4c8b33",
          }}
        >
          <span aria-hidden="true">❗</span> <b>Error:</b> {error}
        </div>
      );

    // Uploading with spinner and a11y
    if (uploading)
      return (
        <div
          role="status"
          aria-live="polite"
          style={{
            margin: "20px 0 0 0",
            color: brandPalette.primaryBlue,
            display: "flex",
            alignItems: "center",
            gap: 7,
            fontWeight: 500,
            background: "#f4f9fd",
            borderRadius: 8,
            padding: "7px 12px",
          }}
        >
          <span className="sr-only">Uploading in progress</span>
          <BusySpinner color={brandPalette.primaryBlue} size={16} />
          <span>Uploading... Please wait.</span>
        </div>
      );

    // Job status with details, progress and adaptive color
    if (jobId && jobStatus) {
      return (
        <div
          style={{
            marginTop: 20,
            background: "#f8f6fe",
            border: "1.2px solid #a3c2fe",
            borderRadius: 8,
            padding: "18px 13px 9px 13px",
            outline: jobStatus.status === "error" ? "2px solid #ED4C8B" : undefined,
            boxShadow: "0 2px 12px #a3c2fe18",
            fontWeight: 500,
          }}
          tabIndex={-1}
          id="status-announcement"
          aria-live="polite"
          aria-atomic="true"
        >
          <strong>
            Job Status:{" "}
            <span style={{ color: statusColor(jobStatus.status) }}>
              {jobStatus.status?.toUpperCase() || "loading..."}
            </span>
            {" "}
            {jobStatus.status === "success" && <span aria-label="success" style={{color:"#3cc878"}}>✔️</span>}
            {jobStatus.status === "error" && <span aria-label="failure" style={{color:"#ED4C8B"}}>❌</span>}
          </strong>
          <br />
          <span>
            {jobStatus.message ||
              (jobStatus.status === "success"
                ? "Complete"
                : "Processing...")}
          </span>
          {typeof jobStatus.progress === "number" &&
            jobStatus.status !== "success" && (
              <>
                <ProgressBar progress={jobStatus.progress || 10} />
                <span className="sr-only">
                  {`Job progress: ${Math.round(jobStatus.progress)} percent.`}
                </span>
              </>
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
                <span aria-hidden="true">✔️</span> <b>Subtitle output is ready!</b>
                <br />
                <span style={{ fontSize: "0.97em" }}>
                  No direct download link is available. <span className="sr-only"> Ask an administrator for access. </span>
                  <br />
                  Please contact your administrator or check backend storage for the final subtitle file.
                </span>
                <br />
                <span style={{ color: "#A41E7E" }}>
                  If something went wrong or output didn't arrive, <b>refresh</b> or <b>try again</b>.
                </span>
              </div>
            )
          )}
        </div>
      );
    }
    // Explanatory info about workflow below forms (now includes brand highlight and a11y-friendly tips)
    return (
      <div
        aria-live="polite"
        className="info-message"
        style={{
          marginTop: 16,
          fontSize: "1.07rem",
          color: "#22223A",
          background: "#fafbfd",
          border: "1px solid #e5e7ee",
          borderRadius: 8,
          padding: "11px 16px",
        }}
      >
        <strong style={{color: brandPalette.primaryBlue}}>Need help?</strong> &nbsp; 
        For best results:&nbsp;
        <span style={{ color: brandPalette.primaryBlue }}>
          Wait for your upload to finish, keep this tab open, and contact support if jobs fail multiple times.
        </span>
        <span className="sr-only">
          Screen reader tip: workflow actions and upload progress are announced in real time.
        </span>
      </div>
    );
  }

  // Spinner component for feedback during upload/wait
  function BusySpinner({ color, size = 18 }) {
    return (
      <svg
        width={size}
        height={size}
        style={{ margin: "0 3px -2px 0", verticalAlign: "middle" }}
        viewBox="0 0 38 38"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        focusable="false"
      >
        <g fill="none" fillRule="evenodd">
          <g transform="translate(1 1)" stroke={color} strokeWidth="3">
            <circle strokeOpacity=".3" cx="18" cy="18" r="18" />
            <path d="M36 18c0-9.94-8.06-18-18-18">
              <animateTransform
                attributeName="transform"
                type="rotate"
                from="0 18 18"
                to="360 18 18"
                dur="0.95s"
                repeatCount="indefinite"
              />
            </path>
          </g>
        </g>
      </svg>
    );
  }

  // Color by job status
  function statusColor(status) {
    if (!status) return "#8c8ca6";
    if (status === "pending") return brandPalette.secondaryPink;
    if (status === "in_progress") return brandPalette.primaryBlue;
    if (status === "success") return "#20A664";
    if (status === "error" || status === "cancelled") return "#A41E7E";
    return "#888";
  }

  // ProgressBar: Simple filling bar (a11y friendly)
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
        aria-label="Job progress"
        role="progressbar"
        aria-valuenow={progress || 1}
        aria-valuemin={0}
        aria-valuemax={100}
        tabIndex={-1}
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
          tabIndex={0}
          style={{
            background: brandPalette.secondaryPink,
            color: brandPalette.neutralWhite,
          }}
        >
          {theme === "light" ? "🌙 Dark" : "☀️ Light"}
        </button>
        <h1 className="dashboard-title" tabIndex={0}>
          Subtitle Sync Platform
        </h1>
        <p className="dashboard-description" tabIndex={0}>
          AI-powered subtitle correction and generation for your videos.
          Start by selecting a workflow below.
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
            tabIndex={0}
            id="correction-tab"
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
            tabIndex={0}
            id="generation-tab"
          >
            Subtitle Generation
          </button>
        </nav>

        {/* Workflow Forms */}
        <section
          className="workflow-content"
          role="region"
          aria-labelledby={`${workflow}-tab`}
          tabIndex={-1}
        >
          {workflow === "correction" && (
            <form
              className="workflow-form"
              onSubmit={handleCorrectionSubmit}
              noValidate
              aria-describedby="correction-desc"
            >
              <h2 style={{ color: brandPalette.primaryBlue }} id="correction-desc">
                Subtitle Correction
              </h2>
              <p>
                Upload your video and an existing subtitle file.
                <br />
                <span
                  style={{
                    fontSize: "0.93em",
                    color: brandPalette.accentPurple,
                  }}
                >
                  Supported subtitle formats: SRT, VTT, ASS, SUB, TXT, DFXP, SBV.<br />
                  Recommended video formats: MP4, MOV, AVI, MKV.<br />
                  Output will match the uploaded subtitle's format.
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
                id="video-file-correction"
              />
              <FileUploader
                label="Subtitle File"
                accept=".srt,.vtt,.ass,.sub,.txt,.dfxp,.sbv"
                onChange={setCorrectionSub}
                value={correctionSub}
                required
                brandColor={brandPalette.accentPurple}
                id="subtitle-file-correction"
              />
              <button
                className="submit-btn"
                type="submit"
                style={{
                  background: brandPalette.secondaryPink,
                  color: brandPalette.neutralWhite,
                  marginTop: 24,
                  outline: uploading ? "2px solid #ffc60b" : undefined,
                }}
                disabled={uploading}
                aria-disabled={uploading}
                aria-busy={uploading}
              >
                Submit for Correction
              </button>
              {renderStatusPanel()}
            </form>
          )}

          {workflow === "generation" && (
            <form
              className="workflow-form"
              onSubmit={handleGenerationSubmit}
              noValidate
              aria-describedby="generation-desc"
            >
              <h2 style={{ color: brandPalette.accentPurple }} id="generation-desc">
                Subtitle Generation
              </h2>
              <p>
                Upload a video file to generate subtitles.
                <br />
                <span style={{
                  fontSize: "0.93em",
                  color: brandPalette.accentPurple,
                }}>
                  Recommended video formats: MP4, MOV, AVI, MKV.<br />
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
                id="video-file-generation"
              />
              <div className="input-group">
                <label
                  htmlFor="language-select"
                  className="input-label"
                  style={{ color: brandPalette.primaryBlue }}
                >
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
                  tabIndex={0}
                  aria-required="true"
                  aria-label="Target Language"
                  aria-describedby="language-desc"
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
                <span className="sr-only" id="language-desc">Choose the target subtitle language.</span>
              </div>
              <button
                className="submit-btn"
                type="submit"
                style={{
                  background: brandPalette.accentYellow,
                  color: brandPalette.primaryBlue,
                  marginTop: 24,
                  outline: uploading ? "2px solid #A41E7E" : undefined,
                }}
                disabled={uploading}
                aria-disabled={uploading}
                aria-busy={uploading}
              >
                Generate Subtitles
              </button>
              {renderStatusPanel()}
            </form>
          )}
          {/* Aria-live region for screenreader announcements */}
          <div
            className="sr-only"
            aria-live="polite"
            aria-atomic="true"
            role="status"
            tabIndex={-1}
            style={{ position: "absolute", left: "-9999px" }}
            id="aria-status-region"
          >
            {announce}
          </div>
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
 * Accessible File uploader component for video and subtitle files.
 * Props:
 *   - label: string (display label)
 *   - accept: string (file MIME types)
 *   - onChange: function (called with selected file or null)
 *   - value: File | null (current file)
 *   - required: bool (optional)
 *   - brandColor: string (accent color for highlight)
 *   - id: string (optional, for a11y/label)
 */
function FileUploader({ label, accept, onChange, value, required, brandColor, id }) {
  const inputRef = useRef();
  // Ensure proper aria-label and describedby for improved accessibility
  return (
    <div className="input-group">
      <label
        className="input-label"
        style={{ color: brandColor }}
        htmlFor={id}
        id={id ? `${id}-label` : undefined}
      >
        {label} {required && <span style={{ color: "#ED4C8B" }}>*</span>}
      </label>
      <div className="custom-file-input">
        <input
          id={id}
          aria-labelledby={id ? `${id}-label` : undefined}
          ref={inputRef}
          type="file"
          accept={accept}
          style={{ display: "none" }}
          onChange={(e) => onChange(e.target.files?.[0] || null)}
          tabIndex={0}
          aria-required={required}
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
          aria-label={value ? `Selected: ${value.name}` : `Select ${label}`}
          tabIndex={0}
          onKeyDown={e => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
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

// Offscreen (screen-reader only) style class to use for live regions (add this also in App.css)
export default App;
