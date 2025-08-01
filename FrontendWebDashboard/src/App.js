import React, { useState, useEffect, useCallback } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
} from "react-router-dom";
import {
  generateSubtitles,
  correctSubtitles,
  getSubtitleFiles,
  downloadSubtitleFile,
} from "./services/api";
import Notification from "./components/Notification";
import { downloadBlob } from "./utils/fileUtils";

// File extensions accepted for subtitles
const SUBTITLE_EXTENSIONS = ".srt,.vtt,.ass,.ssa,.sub,.smi,.sami";
const VIDEO_EXTENSIONS = "video/*";

/* File Upload (video/subtitles) -- Integrated with backend API */
function UploadFiles({ onUpload }) {
  const [video, setVideo] = useState(null);
  const [subtitle, setSubtitle] = useState(null);
  const [msg, setMsg] = useState("");
  const [progress, setProgress] = useState(0);
  const [notif, setNotif] = useState(null);
  const [processing, setProcessing] = useState(false);

  // Reset form state
  const reset = () => {
    setVideo(null);
    setSubtitle(null);
    setMsg("");
    setProgress(0);
    setProcessing(false);
  };

  async function handleSubmit(e) {
    e.preventDefault();
    setMsg("");
    setNotif(null);

    if (!video && !subtitle) {
      setMsg("Please select at least a video or subtitle file.");
      return;
    }
    if (!video) {
      setMsg("At least a video file is required.");
      return;
    }

    setMsg("Uploading...");
    setProcessing(true);
    setProgress(20);

    try {
      let apiResp;
      if (subtitle) {
        apiResp = await correctSubtitles(video, subtitle);
      } else {
        apiResp = await generateSubtitles(video, "en");
      }
      setProgress(70);

      // Expecting file download as response (Blob)
      if (
        apiResp &&
        apiResp.data &&
        apiResp.headers &&
        (apiResp.headers["content-type"]?.includes("octet-stream") ||
          apiResp.headers["content-type"]?.includes("text/plain") ||
          apiResp.headers["content-type"]?.includes("application/srt"))
      ) {
        // Figure out filename from header or fallback
        let filename = "subtitle_result.srt";
        const disp = apiResp.headers["content-disposition"];
        if (disp) {
          const match = disp.match(/filename="?([^"]+)"?/i);
          if (match) filename = match[1];
        }
        downloadBlob(apiResp.data, filename);
        setNotif({
          type: "success",
          message: `Success! Your processed subtitle file is downloaded.`,
        });
        setMsg("Upload successful! File downloaded.");
      } else if (apiResp && apiResp.data) {
        setNotif({
          type: "success",
          message: "Success! Result: " + JSON.stringify(apiResp.data),
        });
        setMsg("Upload complete!");
      } else {
        setNotif({
          type: "warning",
          message: "Unexpected response from backend.",
        });
        setMsg("Backend returned an unexpected response.");
      }
      setProgress(100);
      reset();
      onUpload && onUpload();
    } catch (err) {
      setProgress(0);
      let userMsg = "Upload failed. ";
      if (err.response) {
        // Backend responded with error status
        if (err.response.status === 413)
          userMsg += "File too large. Please upload smaller files.";
        else if (err.response.status === 400 || err.response.status === 422)
          userMsg += "Invalid file format or bad request.";
        else if (err.response.status === 500)
          userMsg += "Server error while processing your file.";
        else userMsg += "API error: " + (err.response.data?.detail || err.message);
      } else if (err.request) {
        userMsg += "Could not connect to backend. Check network.";
      } else {
        userMsg += err.message;
      }
      setNotif({ type: "error", message: userMsg });
      setMsg(userMsg);
    }
    setProcessing(false);
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <h3>Upload Video and/or Subtitle</h3>
      <input
        type="file"
        accept={VIDEO_EXTENSIONS}
        onChange={(e) => setVideo(e.target.files[0])}
        disabled={processing}
      />
      <input
        type="file"
        accept={SUBTITLE_EXTENSIONS}
        onChange={(e) => setSubtitle(e.target.files[0])}
        disabled={processing}
      />
      <button type="submit" disabled={processing}>
        {processing ? "Uploading..." : "Upload"}
      </button>
      {msg && (
        <div className="progress-msg">
          {msg}{" "}
          {processing && (
            <progress value={progress} max="100">
              {progress}%
            </progress>
          )}
        </div>
      )}
      {notif && (
        <Notification
          type={notif.type}
          message={notif.message}
          onClose={() => setNotif(null)}
        />
      )}
    </form>
  );
}

/* Dashboard file list (shows user's processed files) */
function FileListDashboard() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [notif, setNotif] = useState(null);

  const fetchFiles = useCallback(() => {
    setLoading(true);
    getSubtitleFiles()
      .then((resp) => {
        setFiles(resp.files || resp); // backend may return files:[] or bare array
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        setNotif({
          type: "error",
          message:
            "Failed to fetch files: " +
            (err.response?.data?.detail || err.message),
        });
      });
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleDownload = async (file) => {
    try {
      const resp = await downloadSubtitleFile(file.id || file.file_id || file.name);
      let filename = file.filename || file.name || "subtitle.srt";
      // 'content-disposition' header can provide filename
      const disp = resp.headers["content-disposition"];
      if (disp) {
        const match = disp.match(/filename="?([^"]+)"?/i);
        if (match) filename = match[1];
      }
      downloadBlob(resp.data, filename);
      setNotif({ type: "success", message: `Downloaded ${filename}` });
    } catch (err) {
      setNotif({
        type: "error",
        message: "Download error: " + (err.response?.data?.detail || err.message)
      });
    }
  };

  return (
    <div>
      <h3>Processed Subtitle Files</h3>
      {notif && (
        <Notification
          type={notif.type}
          message={notif.message}
          onClose={() => setNotif(null)}
        />
      )}
      <button onClick={fetchFiles} disabled={loading} style={{ marginBottom: 8 }}>
        Refresh
      </button>
      {loading ? (
        <p>Loading file list...</p>
      ) : files.length === 0 ? (
        <p>No files found.</p>
      ) : (
        <table border="1" style={{ width: "100%" }}>
          <thead>
            <tr>
              <th>File Name</th>
              <th>Language</th>
              <th>Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f, idx) => (
              <tr key={f.id || f.file_id || idx}>
                <td>{f.filename || f.name || "-"}</td>
                <td>{f.language || "-"}</td>
                <td>{f.created_at ? new Date(f.created_at).toLocaleString() : "-"}</td>
                <td>
                  <button onClick={() => handleDownload(f)}>Download</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
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

/* Dashboard Page (shows uploads, filelist, etc) */
function Dashboard() {
  return (
    <div className="dashboard">
      <header>
        <h1>Subtitle Sync Platform</h1>
      </header>
      <nav>
        <Link to="/">Dashboard</Link> |{" "}
        <Link to="/upload">Upload Files</Link> |{" "}
        <Link to="/files">My Files</Link> |{" "}
        <Link to="/monitor">Processing/Monitoring</Link>
      </nav>
      <main>
        <Routes>
          <Route path="/upload" element={<UploadFiles />} />
          <Route path="/files" element={<FileListDashboard />} />
          <Route path="/monitor" element={<ProgressPlaceholder />} />
          <Route
            path="/"
            element={
              <>
                <h2>Welcome!</h2>
                <p>
                  This dashboard allows you to upload videos and subtitle files, and monitor job progress.
                </p>
                <UploadFiles />
                <div style={{ margin: "32px 0" }}>
                  <FileListDashboard />
                </div>
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
