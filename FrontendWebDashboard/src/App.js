import React, { useRef } from "react";
import "./App.css";

// PUBLIC_INTERFACE
function App() {
  /**
   * Root application component for the Subtitle Sync Dashboard.
   * Provides UI for uploading videos/subtitles, monitoring progress, and accessing downloads.
   */
  const videoInputRef = useRef(null);
  const subtitleInputRef = useRef(null);

  // Handler for upload button click - triggers file input
  const handleSelectVideo = () => videoInputRef.current.click();
  const handleSelectSubtitle = () => subtitleInputRef.current.click();

  // Handler for when a file is selected
  const handleVideoChange = (event) => {
    // TODO: implement logic to handle video file upload
    // e.g.: set video in state, send to backend, show progress indicator, etc.
  };

  const handleSubtitleChange = (event) => {
    // TODO: implement logic to handle subtitle file upload
    // e.g.: set subtitle in state, send to backend, show progress indicator, etc.
  };

  return (
    <div className="dashboard-root">
      <header className="dashboard-header">
        <h1>Subtitle Sync Platform</h1>
        <p>Streamline subtitle-audio synchronization and subtitle generation for your videos</p>
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
          </div>
          <div className="hint-text">
            <small>Supported formats: SRT, VTT, ASS, SUB. Multiple languages and formats supported.</small>
          </div>
        </section>
        <section className="progress-section">
          <h2>Processing Progress</h2>
          {/* TODO: Insert dynamic progress tracker (spinner, progress bar, etc.) */}
          <div className="progress-placeholder">
            No jobs currently processing.
          </div>
        </section>
        <section className="download-section">
          <h2>Download Processed Subtitles</h2>
          {/* TODO: Dynamically list processed subtitles with download buttons */}
          <div className="download-placeholder">
            Processed subtitle files will appear here for download.
          </div>
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
