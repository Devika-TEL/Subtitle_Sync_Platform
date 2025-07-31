import React, { useRef, useState } from 'react';
import './App.css';

// PUBLIC_INTERFACE
function App() {
  /** 
   * Dashboard UI for uploading videos/subtitles, monitoring progress,
   * listing processed/corrected subtitle files, and providing download links.
   */
  const videoInputRef = useRef();
  const subtitleInputRef = useRef();
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processedFiles, setProcessedFiles] = useState([
    // Example prefilled; in real app, fetched from backend
    // { filename: "example_corrected.srt", url: "/downloads/example_corrected.srt" }
  ]);
  const [message, setMessage] = useState('');

  // PUBLIC_INTERFACE
  const handleUpload = async (e) => {
    e.preventDefault();
    setMessage('');
    if (!videoFile && !subtitleFile) {
      setMessage('Please select at least a video or subtitle file.');
      return;
    }
    setUploading(true);
    setProcessing(true);

    // --- Replace with real API call ---
    await new Promise((res) => setTimeout(res, 1500)); // Simulate upload delay
    setProcessing(false);

    // Mock: append new file to processedFiles
    if (subtitleFile) {
      // Make filename unique/demonstrative for the example
      const d = new Date();
      const correctedName = `corrected_${d.getTime()}_${subtitleFile.name}`;
      setProcessedFiles([
        ...processedFiles,
        {
          filename: correctedName,
          url: `#download-link-${correctedName}`,
        },
      ]);
      setMessage('Subtitle processed and ready for download.');
    } else {
      setMessage('File uploaded (no subtitles to process).');
    }

    setUploading(false);
    setVideoFile(null);
    setSubtitleFile(null);
    videoInputRef.current.value = '';
    subtitleInputRef.current.value = '';
  };

  return (
    <div className="dashboard-container">
      <header className="header">
        <h1>Subtitle Sync Platform Dashboard</h1>
        <p className="header-tag">
          Effortlessly synchronize, generate, and correct subtitles for your videos.
        </p>
      </header>

      <main className="main-content">
        <section className="upload-section card">
          <h2>Upload Video & Subtitle</h2>
          <form onSubmit={handleUpload} className="upload-form">
            <div className="form-group">
              <label htmlFor="video-upload">
                Video File:
                <input
                  id="video-upload"
                  type="file"
                  accept="video/*"
                  ref={videoInputRef}
                  onChange={(e) => setVideoFile(e.target.files[0])}
                  disabled={uploading}
                />
              </label>
            </div>
            <div className="form-group">
              <label htmlFor="subtitle-upload">
                Subtitle File:
                <input
                  id="subtitle-upload"
                  type="file"
                  accept=".srt,.vtt,.ass,.sub"
                  ref={subtitleInputRef}
                  onChange={(e) => setSubtitleFile(e.target.files[0])}
                  disabled={uploading}
                />
              </label>
            </div>
            <button
              className="upload-btn"
              disabled={uploading || (!videoFile && !subtitleFile)}
              type="submit"
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
          <div className="upload-info">
            <span>Supported Subtitle Formats: SRT, VTT, ASS, SUB</span>
            <span>Supported Video Formats: mp4, mkv, mov, avi, webm</span>
          </div>
          {message && <div className="msg">{message}</div>}
        </section>

        <section className="status-section card">
          <h2>Processing Status</h2>
          {processing ? (
            <div className="status-row">
              <div className="spinner"></div>
              <div className="status-text">Processing files, please wait...</div>
            </div>
          ) : (
            <div className="status-row">
              <div className="status-done">No jobs in progress.</div>
            </div>
          )}
        </section>

        <section className="downloads-section card">
          <h2>Processed Subtitles</h2>
          {processedFiles.length === 0 ? (
            <div>No processed subtitles yet. Upload to begin!</div>
          ) : (
            <ul className="downloads-list">
              {processedFiles.map((f, idx) => (
                <li key={idx}>
                  <span className="download-filename">{f.filename}</span>
                  <a
                    href={f.url}
                    className="download-link"
                    download={f.filename}
                  >
                    Download
                  </a>
                </li>
              ))}
            </ul>
          )}
          <div className="download-hint">
            <strong>Where to download corrected subtitles?</strong>
            <br />
            Download links for corrected subtitles are provided above. Click "Download" next to your processed file.
          </div>
        </section>
      </main>

      <footer className="footer">
        <span>&copy; {new Date().getFullYear()} Subtitle Sync Platform
          &nbsp;|&nbsp; Powered by LLM & OTT Technology
        </span>
      </footer>
    </div>
  );
}

export default App;
