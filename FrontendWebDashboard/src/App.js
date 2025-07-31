import React, { useState } from 'react';
import './App.css';

/*
 * Subtitle Sync Platform - Streamlined UI
 * Legacy job status tracking, polling, multi-state UI/components, and unused styles/hooks have been removed.
 * Only minimal direct upload and download logic for correction/generation is present.
 */

// PUBLIC_INTERFACE
function App() {
  // State for uploaded files
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);

  // Handle video file selection
  const handleVideoChange = (e) => setVideoFile(e.target.files[0]);

  // Handle subtitle file selection
  const handleSubtitleChange = (e) => setSubtitleFile(e.target.files[0]);

  // PUBLIC_INTERFACE
  // Handle form submission: uploads files and triggers processing for correction/generation.
  // Upon success, triggers download of the processed file directly.
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!videoFile && !subtitleFile) return;

    const formData = new FormData();
    if (videoFile) formData.append('video', videoFile);
    if (subtitleFile) formData.append('subtitle', subtitleFile);

    try {
      const response = await fetch('http://localhost:8000/process', {
        method: 'POST',
        body: formData,
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        const disp = response.headers.get('Content-Disposition');
        a.download = disp?.split('filename=')[1] || 'result.srt';
        a.href = url;
        a.click();
        window.URL.revokeObjectURL(url);
      } else {
        alert('Processing failed.');
      }
    } catch (error) {
      alert('Error: ' + error.message);
    }
  };

  return (
    <div className="App">
      <h1>Subtitle Sync Platform</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="video">Video File:&nbsp;</label>
          <input type="file" id="video" accept="video/*" onChange={handleVideoChange} />
        </div>
        <div>
          <label htmlFor="subtitle">Subtitle File:&nbsp;</label>
          <input type="file" id="subtitle" accept=".srt,.vtt,.ass,.sub" onChange={handleSubtitleChange} />
        </div>
        <button type="submit">Process</button>
      </form>
      {/* No job status, polling, or legacy controls remain */}
    </div>
  );
}

export default App;
