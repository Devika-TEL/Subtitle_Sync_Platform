import React, { useState } from "react";
import "./App.css";

/**
 * PUBLIC_INTERFACE
 * The main application layout for the Subtitle Sync Platform Dashboard.
 * Provides card containers for uploads, progress, and subtitle management,
 * with visually engaging UI components per branded design (see App.css).
 */
function App() {
  // State for file uploading and basic simulated progress for demonstration
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [progress, setProgress] = useState(0);
  // Simulated subtitle items
  const [subtitleList, setSubtitleList] = useState([
    {id: 1, name: "Episode1.en.srt", status: "Ready", lang: "en"},
    {id: 2, name: "Episode1.fr.srt", status: "In Progress", lang: "fr"},
  ]);

  // Simulate upload & progress for demo UI
  const handleUpload = (e) => {
    e.preventDefault();
    if (!videoFile || !subtitleFile) {
      setUploadStatus("Please select both video and subtitle files.");
      return;
    }
    setProgress(0);
    setUploadStatus("Uploading...");
    let progressStep = 0;
    const interval = setInterval(() => {
      progressStep += 20;
      setProgress(progressStep);
      if (progressStep >= 100) {
        clearInterval(interval);
        setUploadStatus("Upload complete! Starting subtitle analysis...");
        setTimeout(() => setUploadStatus("Processing complete. Subtitles ready."), 1800);
      }
    }, 450);
  };

  const handleFileChange = (type, e) => {
    const file = e.target.files[0];
    if (type === "video") setVideoFile(file);
    else setSubtitleFile(file);
  };

  // --- Dashboard
  return (
    <div>
      <header className="app-header">
        <h1>Subtitle Sync Platform</h1>
        <p>
          AI-powered workflow for subtitle-audio sync, QC, and fast multi-language subtitle generation.
        </p>
      </header>
      <div className="dashboard-container">
        <div className="dashboard-grid">
          <main className="dashboard-main">
            {/* Card: Upload panel */}
            <section className="dashboard-card" aria-labelledby="section-upload">
              <div className="section-title" id="section-upload">
                Upload Video &amp; Subtitle
              </div>
              <form onSubmit={handleUpload} autoComplete="off" style={{display:"flex", flexDirection:"column", gap:"1.15em"}}>
                <div className="form-group">
                  <label htmlFor="video-upload">Video File</label>
                  <input
                    id="video-upload"
                    type="file"
                    accept="video/*"
                    onChange={(e) => handleFileChange("video", e)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="subtitle-upload">Subtitle File</label>
                  <input
                    id="subtitle-upload"
                    type="file"
                    accept=".srt,.vtt,.ass,.sub"
                    onChange={(e) => handleFileChange("subtitle", e)}
                  />
                </div>
                <button
                  type="submit"
                  disabled={!videoFile || !subtitleFile || uploadStatus.includes("Uploading")}
                >
                  Upload &amp; Analyze
                </button>
                {uploadStatus && (
                  <div
                    className={`status-message ${
                      uploadStatus.toLowerCase().includes("complete")
                        ? "status-success"
                        : uploadStatus.toLowerCase().includes("error") || uploadStatus.toLowerCase().includes("please")
                        ? "status-danger"
                        : uploadStatus.toLowerCase().includes("uploading")
                        ? "status-warning"
                        : ""
                    }`}
                    style={{marginTop: ".5em"}}
                    aria-live="polite"
                  >
                    {uploadStatus}
                  </div>
                )}
                {progress > 0 && progress < 100 && (
                  <div className="progress-bar-container" aria-label="Upload Progress" aria-valuenow={progress}>
                    <div className="progress-bar" style={{ width: `${progress}%` }}></div>
                  </div>
                )}
              </form>
            </section>

            {/* Card: Subtitle workflow */}
            <section className="dashboard-card" aria-labelledby="section-subtitle">
              <div className="section-title" id="section-subtitle">
                Subtitle Files &amp; Management
              </div>
              <ul className="subtitle-list" style={{marginTop:'1em'}}>
                {subtitleList.map(sub => (
                  <li className="subtitle-item" key={sub.id}>
                    <div>
                      <span role="img" aria-label="Subtitle File">🗎</span> <strong>{sub.name}</strong>
                      <span style={{marginLeft:10, color:"var(--color-subtext)", fontSize:'.96em'}}>({sub.lang})</span>
                    </div>
                    <div className="subtitle-actions">
                      <span className={
                          sub.status === "Ready"
                            ? "status-success"
                            : sub.status === "In Progress"
                            ? "status-warning"
                            : ""
                        }>{sub.status}
                      </span>
                      <button className="button-like" style={{padding:'0.4em 1.4em', fontSize:'.98em'}}>Download</button>
                      <button
                        className="button-like"
                        style={{
                          padding:'0.4em 1.3em',
                          background: 'linear-gradient(90deg, #ffae42, #fffde4)',
                          color: '#b45d0c'
                        }}>Edit</button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          </main>
          <aside className="dashboard-side">
            {/* Card: Demo panel for future features */}
            <section className="dashboard-card" aria-labelledby="section-info">
              <div className="section-title" id="section-info">How it Works</div>
              <p>
                <strong>1.</strong> <b>Upload</b> your video and subtitle files.<br/>
                <strong>2.</strong> Our AI checks timing, format, compliance, and quality.<br/>
                <strong>3.</strong> Download or edit auto-corrected subtitles.<br/>
                <strong>4.</strong> Advanced: request translations, batch QC, or manual tweaks.
              </p>
              <p style={{fontSize:".92em", color:"var(--color-subtext)"}}>
                Need help? Contact <a href="mailto:support@subsync.ai" style={{color:"var(--color-primary)"}}>support@subsync.ai</a>
              </p>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default App;
