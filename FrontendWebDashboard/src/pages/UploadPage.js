import React, { useRef, useState } from "react";
import { uploadVideoAndSubtitle } from "../services/api";
import Notification from "../components/Notification";

/**
 * UploadPage lets users upload video and/or subtitle files.
 */
function UploadPage() {
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const fileForm = useRef();

  // PUBLIC_INTERFACE
  async function handleSubmit(e) {
    e.preventDefault();
    if (!videoFile && !subtitleFile) {
      setNotification({ type: "error", message: "Select a video and/or subtitle file." });
      return;
    }
    setLoading(true);
    try {
      await uploadVideoAndSubtitle(videoFile, subtitleFile);
      setNotification({ type: "success", message: "Upload successful, your request is queued for processing." });
      setVideoFile(null);
      setSubtitleFile(null);
      fileForm.current.reset();
    } catch (err) {
      setNotification({ type: "error", message: err?.message || "Upload failed." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="upload-section">
      <h2>Upload Video and/or Subtitle File</h2>
      <form onSubmit={handleSubmit} ref={fileForm}>
        <div>
          <label>
            Video File (.mp4, .mkv, etc):{" "}
            <input
              type="file"
              accept="video/mp4,video/x-mkv,video/*"
              onChange={e => setVideoFile(e.target.files[0])}
            />
          </label>
        </div>
        <div>
          <label>
            Subtitle File (.srt, .vtt, .ass, etc):{" "}
            <input
              type="file"
              accept=".srt,.vtt,.ass,.sub,.sbv"
              onChange={e => setSubtitleFile(e.target.files[0])}
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={loading}
          aria-busy={loading}
        >
          {loading ? "Uploading..." : "Upload"}
        </button>
      </form>
      {notification && (
        <Notification
          type={notification.type}
          message={notification.message}
          onClose={() => setNotification(null)}
        />
      )}
    </section>
  );
}

export default UploadPage;
