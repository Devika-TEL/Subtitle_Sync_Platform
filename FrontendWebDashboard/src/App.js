import React, { useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
} from "react-router-dom";

/* File Upload (video/subtitles) */
function UploadFiles({ onUpload }) {
  const [video, setVideo] = useState(null);
  const [subtitle, setSubtitle] = useState(null);
  const [msg, setMsg] = useState("");
  const [progress, setProgress] = useState(0);

  // Dummy upload handler; replace with real API call
  function handleSubmit(e) {
    e.preventDefault();
    if (!video) {
      setMsg("Please choose a video file.");
      return;
    }
    setMsg("Uploading...");
    setProgress(0);
    // Simulate upload progress
    let step = 0;
    const interval = setInterval(() => {
      step += 20;
      setProgress(Math.min(step, 100));
      if (step >= 100) {
        clearInterval(interval);
        setMsg(
          `Uploaded: ${video.name}${subtitle ? " + " + subtitle.name : ""}`
        );
        onUpload && onUpload();
      }
    }, 200);
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <h3>Upload Video and/or Subtitle</h3>
      <input
        type="file"
        accept="video/*"
        onChange={(e) => setVideo(e.target.files[0])}
      />
      <input
        type="file"
        accept=".srt,.vtt,.ass,.ssa,.sub,.smi"
        onChange={(e) => setSubtitle(e.target.files[0])}
      />
      <button type="submit">Upload</button>
      {msg && (
        <div className="progress-msg">
          {msg}{" "}
          {progress > 0 && progress < 100 ? (
            <progress value={progress} max="100">{progress}%</progress>
          ) : null}
        </div>
      )}
    </form>
  );
}

/* Dummy Progress/Monitoring placeholder */
function ProgressPlaceholder() {
  return (
    <section className="progress-section">
      <h3>Job Progress</h3>
      <p>Monitor processing and jobs here. (To be implemented)</p>
    </section>
  );
}

/* Dashboard Page */
function Dashboard() {
  return (
    <div className="dashboard">
      <header>
        <h1>Subtitle Sync Platform</h1>
      </header>
      <nav>
        <Link to="/">Dashboard</Link> | <Link to="/upload">Upload Files</Link> |{" "}
        <Link to="/monitor">Processing/Monitoring</Link>
      </nav>
      <main>
        <Routes>
          <Route
            path="/upload"
            element={<UploadFiles />}
          />
          <Route
            path="/monitor"
            element={<ProgressPlaceholder />}
          />
          <Route
            path="/"
            element={
              <>
                <h2>Welcome!</h2>
                <p>
                  This dashboard allows you to upload videos and subtitle files, and monitor job progress.
                  Connect this app to your backend to enable real processing.
                </p>
                <UploadFiles />
              </>
            }
          />
        </Routes>
      </main>
      <footer style={{ marginTop: 60 }}>
        <small>
          &copy; {new Date().getFullYear()} Subtitle Sync Platform – Minimal Frontend
        </small>
      </footer>
    </div>
  );
}

/* Main App */
export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/*" element={<Dashboard />} />
      </Routes>
    </Router>
  );
}
