import React, { useState } from 'react';
import './App.css';

function App() {
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);

  const handleVideoChange = (e) => {
    setVideoFile(e.target.files[0]);
  };

  const handleSubtitleChange = (e) => {
    setSubtitleFile(e.target.files[0]);
  };

  const handleUpload = (e) => {
    e.preventDefault();
    // Placeholder logic for uploading
    alert('Video and subtitle files uploaded!');
  };

  return (
    <div className="dashboard-container">
      <header>
        <h1>Audio-Subtitle Sync Dashboard</h1>
        <p>
          Quickly check, correct, and generate subtitles for your videos.
        </p>
      </header>
      <main>
        <form className="upload-form" onSubmit={handleUpload}>
          <div className="form-group">
            <label htmlFor="video-upload">Video File</label>
            <input
              id="video-upload"
              type="file"
              accept="video/*"
              onChange={handleVideoChange}
            />
          </div>
          <div className="form-group">
            <label htmlFor="subtitle-upload">Subtitle File</label>
            <input
              id="subtitle-upload"
              type="file"
              accept=".srt,.vtt,.ass"
              onChange={handleSubtitleChange}
            />
          </div>
          <button type="submit" className="upload-btn">
            Upload
          </button>
        </form>
        <section className="dashboard-description">
          <ul>
            <li>Monitor file processing and manage subtitle assets</li>
            <li>Automatically checks subtitle quality and performs corrections</li>
            <li>Generate and translate subtitles in various formats/languages</li>
          </ul>
        </section>
      </main>
    </div>
  );
}

export default App;
