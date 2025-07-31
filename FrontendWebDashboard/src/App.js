import React, { useState } from 'react';
import './App.css';

/**
 * Subtitle Sync Platform - updated for clear workflow selection and correct, minimal UI.
 * Two workflows: Correction (video+subtitle), Generation (video+language).
 * Provides minimal, accessible UI with basic status and inline errors.
 */

// Supported languages for generation
const languages = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Spanish' },
  { code: 'fr', label: 'French' },
  { code: 'de', label: 'German' },
  { code: 'hi', label: 'Hindi' },
];

// PUBLIC_INTERFACE
function App() {
  // Workflow: 'correction' or 'generation'
  const [workflow, setWorkflow] = useState('correction');
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null);
  const [language, setLanguage] = useState('en');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  // Reset files and status when workflow changes
  const handleWorkflowChange = (wf) => {
    setWorkflow(wf);
    setVideoFile(null);
    setSubtitleFile(null);
    setLanguage('en');
    setStatus('');
    setError('');
  };

  const handleVideoChange = (e) => setVideoFile(e.target.files[0]);
  const handleSubtitleChange = (e) => setSubtitleFile(e.target.files[0]);
  const handleLanguageChange = (e) => setLanguage(e.target.value);

  // PUBLIC_INTERFACE
  // Handle form submission: Correction (video+subtitle) or Generation (video+language).
  // Shows minimal inline status/error, processes directly and triggers download.
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setStatus('');

    // Validation
    if (workflow === 'correction' && (!videoFile || !subtitleFile)) {
      setError('Please select both a video file and a subtitle file.');
      return;
    }
    if (workflow === 'generation' && (!videoFile || !language)) {
      setError('Please select a video file and a target language.');
      return;
    }

    const formData = new FormData();
    formData.append('video', videoFile);
    if (workflow === 'correction') {
      formData.append('subtitle', subtitleFile);
    } else if (workflow === 'generation') {
      formData.append('target_language', language);
    }

    setStatus('Uploading and processing, please wait...');

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
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        setStatus('Subtitle output is ready. File download should start automatically.');
      } else {
        // Try to extract error
        let msg = 'Processing failed.';
        try {
          const err = await response.json();
          msg = err.detail || msg;
        } catch (_) {}
        setError(msg);
        setStatus('');
      }
    } catch (error) {
      setError('Error: ' + error.message);
      setStatus('');
    }
  };

  return (
    <div className="App">
      <h1>Subtitle Sync Platform</h1>
      <div style={{marginBottom:16}}>
        <button
          onClick={() => handleWorkflowChange('correction')}
          disabled={workflow === 'correction'}
          aria-pressed={workflow === 'correction'}
        >
          Subtitle Correction
        </button>
        <button
          onClick={() => handleWorkflowChange('generation')}
          disabled={workflow === 'generation'}
          aria-pressed={workflow === 'generation'}
          style={{marginLeft: 10}}
        >
          Subtitle Generation
        </button>
      </div>
      <h2>{workflow === 'correction' ? 'Subtitle Correction' : 'Subtitle Generation'}</h2>
      <form onSubmit={handleSubmit} style={{maxWidth:380,margin:'0 auto',display:'flex',flexDirection:'column',gap:12}}>
        <div>
          <label htmlFor="video">Video File:&nbsp;</label>
          <input
            type="file"
            id="video"
            accept="video/*"
            onChange={handleVideoChange}
            aria-label="video file"
          />
        </div>
        {workflow === 'correction' && (
          <div>
            <label htmlFor="subtitle">Subtitle File:&nbsp;</label>
            <input
              type="file"
              id="subtitle"
              accept=".srt,.vtt,.ass,.sub"
              onChange={handleSubtitleChange}
              aria-label="subtitle file"
            />
          </div>
        )}
        {workflow === 'generation' && (
          <div>
            <label htmlFor="lang-select">Target Language:&nbsp;</label>
            <select id="lang-select" onChange={handleLanguageChange} value={language} aria-label="target language">
              {languages.map(lang => (
                <option key={lang.code} value={lang.code}>{lang.label}</option>
              ))}
            </select>
          </div>
        )}
        <button type="submit">
          {workflow === 'correction' ? 'Submit Correction' : 'Generate Subtitles'}
        </button>
      </form>
      {error && <div role="alert" style={{color:'crimson',marginTop:12}}>{error}</div>}
      {status && <div style={{color:'green',marginTop:12}}>{status}</div>}
      {/* Minimal UI, no legacy controls or progress bars */}
    </div>
  );
}

export default App;
