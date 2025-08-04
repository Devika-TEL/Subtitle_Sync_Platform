import React, { useEffect, useState } from "react";
import { getUserSubtitles, requestCorrection, requestTranslation, downloadSubtitle } from "../services/api";
import Notification from "../components/Notification";

/**
 * SubtitleManagerPage lets users manage subtitle files, corrections and translation requests.
 */
function SubtitleManagerPage() {
  const [subs, setSubs] = useState([]);
  const [selectedSubId, setSelectedSubId] = useState(null);
  const [translateTo, setTranslateTo] = useState("");
  const [notification, setNotification] = useState(null);

  // PUBLIC_INTERFACE
  async function loadSubs() {
    try {
      setSubs(await getUserSubtitles());
    } catch (e) {
      setNotification({ type: "error", message: "Failed to fetch subtitles." });
    }
  }

  useEffect(() => {
    loadSubs();
  }, []);

  async function handleDownload(subId) {
    try {
      await downloadSubtitle(subId);
    } catch (e) {
      setNotification({ type: "error", message: "Failed to download." });
    }
  }

  async function handleCorrection(subId) {
    try {
      await requestCorrection(subId);
      setNotification({ type: "success", message: "Correction requested." });
      loadSubs();
    } catch (e) {
      setNotification({ type: "error", message: "Error requesting correction." });
    }
  }

  async function handleTranslate(e) {
    e.preventDefault();
    if (!selectedSubId || !translateTo) {
      setNotification({ type: "error", message: "Select subtitle and target language." });
      return;
    }
    try {
      await requestTranslation(selectedSubId, translateTo);
      setNotification({ type: "success", message: "Translation requested." });
      loadSubs();
    } catch (e) {
      setNotification({ type: "error", message: "Error requesting translation." });
    }
  }

  return (
    <section className="subtitle-mgr-page">
      <h2>Subtitle Management</h2>
      <ul>
        {subs.map(s => (
          <li key={s.id}>
            <span>{s.file_name || s.language}</span>
            <button onClick={() => handleDownload(s.id)}>Download</button>
            <button onClick={() => handleCorrection(s.id)}>Request Correction</button>
          </li>
        ))}
      </ul>
      <form onSubmit={handleTranslate}>
        <label>
          Select Subtitle:&nbsp;
          <select value={selectedSubId || ""} onChange={e => setSelectedSubId(e.target.value)}>
            <option value="">Select</option>
            {subs.map(s => <option value={s.id} key={s.id}>{s.file_name || s.language}</option>)}
          </select>
        </label>
        <label>
          Target Language:&nbsp;
          <input
            type="text"
            placeholder="e.g., en, fr, es"
            value={translateTo}
            onChange={e => setTranslateTo(e.target.value)}
          />
        </label>
        <button type="submit">Request Translation</button>
      </form>
      {notification && (
        <Notification {...notification} onClose={() => setNotification(null)} />
      )}
    </section>
  );
}

export default SubtitleManagerPage;
