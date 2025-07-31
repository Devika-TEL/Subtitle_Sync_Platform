import React, { useRef, useState } from "react";
import "./App.css";

// PUBLIC_INTERFACE
function App() {
  /** The main dashboard application for Subtitle Sync Platform. Provides UI for video & subtitle uploads, job tracking, and file downloads. */
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [downloadLinks, setDownloadLinks] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const videoInputRef = useRef();
  const subtitleInputRef = useRef();

  // PUBLIC_INTERFACE
  const handleVideoChange = (e) => {
    setVideoFile(e.target.files[0]);
    setError("");
  };

  // PUBLIC_INTERFACE
  const handleSubtitleChange = (e) => {
    setSubtitleFile(e.target.files[0]);
    setError("");
  };

  // PUBLIC_INTERFACE
  const handleJobStatusPoll = async (currentJobId = jobId) => {
    if (!currentJobId) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${process.env.REACT_APP_API_BASE}/job_status/${currentJobId}`
      );
      if (!res.ok) throw new Error("Could not fetch job status.");
      const data = await res.json();
      setJobStatus(data.status);
      if (data.status === "completed" && data.downloads) {
        setDownloadLinks(data.downloads);
      }
      if (data.status === "error") {
        setError("An error occurred processing your files.");
      }
    } catch (err) {
      setError("Failed to check job status.");
    }
    setLoading(false);
  };

  // PUBLIC_INTERFACE
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setDownloadLinks([]);
    setJobStatus(null);
    setJobId(null);

    if (!videoFile || !subtitleFile) {
      setError("Both video and subtitle files are required.");
      return;
    }
    setLoading(true);

    const formData = new FormData();
    formData.append("video", videoFile);
    formData.append("subtitle", subtitleFile);

    try {
      const res = await fetch(`${process.env.REACT_APP_API_BASE}/process`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Server error uploading files.");
      const data = await res.json();
      setJobId(data.job_id);
      setJobStatus("processing");
      // Start polling job status
      setTimeout(() => handleJobStatusPoll(data.job_id), 2000);
    } catch (err) {
      setError("Error uploading files.");
    }
    setLoading(false);
  };

  // POLL for updates if job is still in progress
  React.useEffect(() => {
    let pollInterval = null;
    if (jobStatus === "processing" && jobId) {
      pollInterval = setInterval(handleJobStatusPoll, 3000);
    }
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
    // eslint-disable-next-line
  }, [jobStatus, jobId]);

  // PUBLIC_INTERFACE
  const handleReset = () => {
    setVideoFile(null);
    setSubtitleFile(null);
    setJobId(null);
    setJobStatus(null);
    setDownloadLinks([]);
    setError("");
    if (videoInputRef.current) videoInputRef.current.value = "";
    if (subtitleInputRef.current) subtitleInputRef.current.value = "";
  };

  return (
    <div className="dashboard-root">
      <header className="dashboard-header">
        <h1>Subtitle Sync Platform</h1>
        <h2>
          Streamline subtitle-audio synchronization & subtitle generation for
          your videos.
        </h2>
      </header>
      <main className="dashboard-main">
        {!jobId && (
          <form className="upload-form" onSubmit={handleSubmit}>
            <div className="form-row">
              <label>
                Video File:
                <input
                  ref={videoInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleVideoChange}
                  disabled={loading}
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Subtitle File:
                <input
                  ref={subtitleInputRef}
                  type="file"
                  accept=".srt,.vtt,.ass,.ssa"
                  onChange={handleSubtitleChange}
                  disabled={loading}
                />
              </label>
            </div>
            <button
              className="submit-btn"
              type="submit"
              disabled={loading || !videoFile || !subtitleFile}
            >
              {loading ? "Uploading..." : "Start Processing"}
            </button>
            {error && <div className="error-message">{error}</div>}
          </form>
        )}

        {!!jobId && (
          <div className="job-status-section">
            <div>
              <strong>Job ID:</strong> {jobId}
            </div>
            <div>
              <strong>Status:</strong>{" "}
              <span
                className={
                  jobStatus === "completed"
                    ? "status-completed"
                    : jobStatus === "error"
                    ? "status-error"
                    : "status-processing"
                }
              >
                {jobStatus}
              </span>
            </div>
            {loading && <div className="job-loading">Checking status...</div>}
            {jobStatus === "completed" && !!downloadLinks.length && (
              <div className="downloads-block">
                <h3>Download Corrected Subtitles:</h3>
                <ul>
                  {downloadLinks.map((link, idx) => (
                    <li key={idx}>
                      <a
                        className="download-link"
                        href={link.url}
                        download={link.filename}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {link.label || link.filename}
                      </a>
                    </li>
                  ))}
                </ul>
                <div>
                  <button className="reset-btn" onClick={handleReset}>
                    Process Another File
                  </button>
                </div>
              </div>
            )}
            {jobStatus === "processing" && (
              <div className="job-progress-message">
                Your files are being analyzed and processed. This may take a
                couple of minutes.&nbsp;
                <span className="polling-indicator" aria-label="Polling">⏳</span>
              </div>
            )}
            {jobStatus === "error" && (
              <div className="error-message">
                There was an error processing your files. Please try again.
                <div>
                  <button className="reset-btn" onClick={handleReset}>
                    Try Again
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
      <footer className="dashboard-footer">
        <div>
          &copy; {new Date().getFullYear()} Subtitle Sync Platform &mdash; Fast.
          Accurate. Accessible.
        </div>
      </footer>
    </div>
  );
}

export default App;
