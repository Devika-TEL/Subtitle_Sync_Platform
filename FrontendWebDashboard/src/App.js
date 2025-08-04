import React, { useState, useEffect } from 'react';
import './App.css';
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import DashboardHome from "./pages/DashboardHome";
import UploadPage from "./pages/UploadPage";
import JobsPage from "./pages/JobsPage";
import SubtitleManagerPage from "./pages/SubtitleManagerPage";
import AdminSystemMonitor from "./pages/AdminSystemMonitor";
import AdminComplianceReport from "./pages/AdminComplianceReport";
import Register from "./components/Register/Register";

/**
 * Role detection (stub).
 * In real app, extract from token/profile.
 */
function getUserRole() {
  return localStorage.getItem("role") || "user";
}

function App() {
  const [role, setRole] = useState(getUserRole());

  useEffect(() => {
    function handleStorage() {
      setRole(getUserRole());
    }
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  return (
    <BrowserRouter>
      <div className="App app-flex">
        <Sidebar role={role} />
        <main className="main-content" tabIndex="-1" aria-label="Main Content">
          <Routes>
            <Route path="/" element={<DashboardHome />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/subtitles" element={<SubtitleManagerPage />} />
            <Route path="/register" element={<Register />} />
            {role === "admin" && (
              <>
                <Route path="/admin/system" element={<AdminSystemMonitor />} />
                <Route path="/admin/compliance" element={<AdminComplianceReport />} />
              </>
            )}
            {/* 404 fallback */}
            <Route path="*" element={<DashboardHome />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
