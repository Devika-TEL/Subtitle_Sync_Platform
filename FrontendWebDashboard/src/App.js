import React, { useRef, useState } from "react";
import "./App.css";

// PUBLIC_INTERFACE
function App() {
  /**
   * Root application component for the Subtitle Sync Dashboard.
   * Provides UI for uploading videos/subtitles, monitoring progress, and accessing downloads.
   */

  const videoInputRef = useRef(null);
  const subtitleInputRef = useRef(null);

  // State for demo: track uploaded files and processing state
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [jobComplete, setJobComplete] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);

  // Simulate upload & processing (in real app, use API calls)
  const handleSelectVideo = () => videoInputRef.current.click();
  const handleSelectSubtitle = () => subtitleInputRef.current.click();

  const handleVideoChange = (event) => {
    const file = event.target.files[0];
    if (file) setVideoFile(file);
  };

  const handleSubtitleChange = (event) => {
    const file = event.target.files[0];
    if (file) setSubtitleFile(file);
  };

  // Simulate API Job Trigger
  const handleStartProcessing = () => {
    if (!videoFile || !subtitleFile) return;
    setProcessing(true);
    setJobComplete(false);
    // Simulate processing delay and completion
    setTimeout(() => {
      // Simulate processed file URL
      setDownloadUrl("/sample_processed_subtitle.srt");
      setProcessing(false);
      setJobComplete(true);
    }, 1800);
  };

  // Call-to-action supportive and accessible text
  const downloadSupportText = "Your file is ready! Click the button above to download your processed subtitles.";

  return (
    <div className="dashboard-root">
      <header className="dashboard-header">
        <h1>Subtitle Sync Platform</h1>
        <p>
          Streamline subtitle-audio synchronization and subtitle generation for your videos
        </p>
      </header>
      <main className="dashboard-content">
        <section className="upload-section">
          <h2>Upload Files</h2>
          <div className="uploader-controls">
            <button className="upload-btn" onClick={handleSelectVideo}>
              Upload Video
            </button>
            <input
              type="file"
              accept="video/*"
              ref={videoInputRef}
              style={{ display: "none" }}
              onChange={handleVideoChange}
              aria-label="Upload Video"
            />
            <button className="upload-btn" onClick={handleSelectSubtitle}>
              Upload Subtitle
            </button>
            <input
              type="file"
              accept=".srt,.vtt,.ass,.sub"
              ref={subtitleInputRef}
              style={{ display: "none" }}
              onChange={handleSubtitleChange}
              aria-label="Upload Subtitle File"
            />
            <button
              className="process-btn"
              onClick={handleStartProcessing}
              disabled={!videoFile || !subtitleFile || processing}
            >
              {processing ? "Processing..." : "Start"}
            </button>
          </div>
          <div className="hint-text">
            <small>
              Supported formats: SRT, VTT, ASS, SUB. Multiple languages and formats supported.
            </small>
          </div>
          <div style={{marginTop: "0.5rem", minHeight:"1.7em"}}>
            {videoFile && (
              <span>🎬 {videoFile.name}</span>
            )}
            {subtitleFile && (
              <span style={{marginLeft: "1.5em"}}>📝 {subtitleFile.name}</span>
            )}
          </div>
        </section>
        <section className="progress-section">
          <h2>Processing Progress</h2>
          {processing ? (
            <div className="progress-placeholder">
              <span className="spinner" aria-hidden="true"></span> Processing... Please wait.
            </div>
          ) : jobComplete ? (
            <div className="progress-placeholder complete">
              ✅ Processing complete!
            </div>
          ) : (
            <div className="progress-placeholder">
              No jobs currently processing.
            </div>
          )}
        </section>

        {/* Download section with prominent button */}
        <section className="download-section" aria-live="polite">
          <h2>Download Processed Subtitles</h2>
          {(jobComplete && downloadUrl) ? (
            <div className="download-result-area" role="region" aria-label="Download Processed Subtitle">
              <a
                href={downloadUrl}
                download
                className="cta-download-btn"
                role="button"
                aria-label="Download your processed subtitle file"
                tabIndex={0}
                autoFocus
              >
                <span className="cta-download-text">
                  <svg width="22" height="22" style={{verticalAlign:"middle",marginRight:"0.55em", marginTop:"-2px"}} fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24"><path d="M12 5v13m0 0l-5-5m5 5l5-5"></path></svg>
                  Download Subtitle File
                </span>
              </a>
              <div className="cta-support-text" id="cta-support">
                {downloadSupportText}
              </div>
            </div>
          ) : (
            <div className="download-placeholder">
              Processed subtitle files will appear here for download.
            </div>
          )}
        </section>
      </main>
      <footer className="dashboard-footer">
        <span>
          &copy; 2024 Subtitle Sync Platform. Powered by LLMs. All rights reserved.
        </span>
      </footer>
    </div>
  );
}

export default App;
