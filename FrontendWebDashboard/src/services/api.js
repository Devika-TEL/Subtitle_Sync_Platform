const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

/**
 * PUBLIC_INTERFACE
 * Uploads video and/or subtitle file to backend.
 * @param {File|null} videoFile 
 * @param {File|null} subtitleFile 
 */
export async function uploadVideoAndSubtitle(videoFile, subtitleFile) {
  const formData = new FormData();
  if (videoFile) formData.append("video", videoFile);
  if (subtitleFile) formData.append("subtitle", subtitleFile);
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

/**
 * PUBLIC_INTERFACE
 * Fetch jobs belonging to the current user.
 */
export async function getJobs() {
  const res = await fetch(`${API_BASE}/jobs`, { credentials: "include" });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

/**
 * PUBLIC_INTERFACE
 * Get user's uploaded subtitle files
 */
export async function getUserSubtitles() {
  const res = await fetch(`${API_BASE}/subtitles`, { credentials: "include" });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

/**
 * PUBLIC_INTERFACE
 * Request correction for a subtitle id.
 */
export async function requestCorrection(subId) {
  const res = await fetch(`${API_BASE}/subtitles/${subId}/correct`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
}

/**
 * PUBLIC_INTERFACE
 * Request translation for a subtitle id to a target language.
 */
export async function requestTranslation(subId, targetLanguage) {
  const res = await fetch(`${API_BASE}/subtitles/${subId}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_language: targetLanguage }),
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
}

/**
 * PUBLIC_INTERFACE
 * Download subtitle file by id.
 */
export async function downloadSubtitle(subId) {
  const res = await fetch(`${API_BASE}/subtitles/${subId}/download`, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  // Download as file
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = (res.headers.get("Content-Disposition")?.split("filename=")[1]) || "subtitle.srt";
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  a.remove();
}

/**
 * PUBLIC_INTERFACE
 * Fetch specific job status by job id.
 */
export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/status`, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

/**
 * PUBLIC_INTERFACE
 * Register a new user.
 * @param {Object} userData - Must contain required registration fields
 */
export async function registerUser(userData) {
  const res = await fetch(`${API_BASE}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(userData),
    credentials: "include",
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}
