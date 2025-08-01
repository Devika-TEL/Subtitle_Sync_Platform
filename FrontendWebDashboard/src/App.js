import React, { useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Link,
  useNavigate,
} from "react-router-dom";

/* Auth Form (Login/Register) */
function AuthForm({ mode = "login", onAuth }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const navigate = useNavigate();

  // Dummy handler (replace with API calls)
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      // TODO: Connect to backend
      // fetch("/auth/token" or "/auth/register")...
      setTimeout(() => {
        setLoading(false);
        localStorage.setItem(
          "authToken",
          "dummy-token-" +
            Math.random().toString(36).slice(2) +
            (mode === "register" ? "-r" : "")
        );
        onAuth();
        navigate("/");
      }, 600);
    } catch (e) {
      setErr("Authentication failed.");
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <h2>{mode === "login" ? "Login" : "Register"}</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button type="submit" disabled={loading}>
          {loading
            ? mode === "login"
              ? "Logging in..."
              : "Registering..."
            : mode === "login"
            ? "Login"
            : "Register"}
        </button>
        {err && (
          <div className="error" style={{ color: "red", marginTop: 10 }}>
            {err}
          </div>
        )}
      </form>
      <div style={{ marginTop: 12 }}>
        {mode === "login" ? (
          <span>
            No account?{" "}
            <button type="button" onClick={() => navigate("/register")}>
              Register
            </button>
          </span>
        ) : (
          <span>
            Have an account?{" "}
            <button type="button" onClick={() => navigate("/login")}>
              Login
            </button>
          </span>
        )}
      </div>
    </div>
  );
}

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
function Dashboard({ onLogout }) {
  return (
    <div className="dashboard">
      <header>
        <h1>Subtitle Sync Platform</h1>
        <button onClick={onLogout} style={{ float: "right" }}>
          Logout
        </button>
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
                  This dashboard allows you to authenticate, upload videos and subtitle files, and monitor job progress.
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
  const [authed, setAuthed] = useState(
    !!localStorage.getItem("authToken")
  );
  function onAuth() {
    setAuthed(true);
  }
  function onLogout() {
    localStorage.removeItem("authToken");
    setAuthed(false);
  }
  return (
    <Router>
      <Routes>
        <Route
          path="/login"
          element={authed ? <Navigate to="/" /> : <AuthForm mode="login" onAuth={onAuth} />}
        />
        <Route
          path="/register"
          element={authed ? <Navigate to="/" /> : <AuthForm mode="register" onAuth={onAuth} />}
        />
        <Route
          path="/*"
          element={authed ? <Dashboard onLogout={onLogout} /> : <Navigate to="/login" />}
        />
      </Routes>
    </Router>
  );
}
