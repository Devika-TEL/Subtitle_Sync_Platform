import React, { useState, useEffect, useRef } from "react";
import "./App.css";

/**
 * Main application component for the Subtitle Sync Frontend Dashboard.
 * Configured to use the backend API at REACT_APP_API_BASE (see .env).
 * 
 * Default backend endpoint: http://localhost:3001
 * 
 * If you encounter connection errors:
 * - Ensure the backend is running on port 3001 (`uvicorn main:app --reload --port 3001`)
 * - The backend should include CORS support for origin http://localhost:3000
 * - You can override the API base via .env or directly in your deployment.
 */

// PUBLIC_INTERFACE
function getApiBase() {
  let base = process.env.REACT_APP_API_BASE;
  if (!base || typeof base !== 'string' || !base.trim()) {
    base = "http://localhost:3001";
  }
  return base.replace(/\/+$/, "");
}

/**
 * PUBLIC_INTERFACE
 * Main application shell for Subtitle Sync Platform dashboard.
 * Shows basic UI and highlights configuration/bootstrap errors.
 */
function App() {
  const apiBase = getApiBase();
  // Basic state for any errors or config problems
  const [appError, setAppError] = useState(null);

  // Example check: Warn if API base URL is empty or malformed
  useEffect(() => {
    if (!apiBase || typeof apiBase !== "string" || !/^https?:\/\/.+/i.test(apiBase)) {
      setAppError("API base URL is missing or malformed. Please check REACT_APP_API_BASE in your .env or deployment.");
    }
  }, [apiBase]);

  // Render main dashboard UI or error
  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fb", color: "#222", padding: "2em" }}>
      <header>
        <h1>Subtitle Sync Platform Dashboard</h1>
        <div style={{ fontSize: "1rem", color: "#555" }}>
          Backend API: <strong>{apiBase}</strong>
        </div>
      </header>

      {appError ? (
        <div style={{ color: "red", margin: "2em 0", fontWeight: "bold", fontSize: "1.2em" }}>
          Startup Error: {appError}
        </div>
      ) : (
        <main style={{ marginTop: "2em" }}>
          {/* Replace this section with the main dashboard UI */}
          <p>
            Welcome to the Subtitle Sync Platform dashboard!
            <br />
            <em>This is a visible placeholder. If you see this message, the frontend is bootstrapping correctly.</em>
          </p>
        </main>
      )}
    </div>
  );
}

export default App;
