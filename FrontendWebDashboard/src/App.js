import React, { useState } from 'react';
import './App.css';

// PUBLIC_INTERFACE
function App() {
  /**
   * Subtitle Sync Dashboard App
   *
   * Renders workflow selection, upload forms, job progress, result/error UI.
   * Integrates with backend API for subtitle-audio correction/generation workflows.
   * Uses REACT_APP_API_BASE from env as the API server base URL.
   */

  const [workflow, setWorkflow] = useState('correction'); // 'correction' or 'generation'
  const [videoFile, setVideoFile] = useState(null);
  const [subtitleFile, setSubtitleFile] = useState(null); // only for correction
  const [language, setLanguage] = useState('en');
  const [isUploading, setIsUploading] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  const [progressText, setProgressText] = useState('');
  const [error, setError] = useState(null);

  const apiBase = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

  // PUBLIC_INTERFACE
  const handleWorkflowChange = (e) => {
    setWorkflow(e.target.value);
    setSubtitleFile(null); // reset
    setResultUrl(null);
    setProgressText('');
    setError(null);
    setJobId(null);
    setJobStatus(null);
  };

  // PUBLIC_INTERFACE
  const handleFileChange = (setFile) => (event) => {
    setFile(event.target.files[0]);
    setResultUrl(null);
    setError(null);
  };

  // PUBLIC_INTERFACE
  const handleLanguageChange = (e) => {
    setLanguage(e.target.value);
  };

  // PUBLIC_INTERFACE
  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setResultUrl(null);
    setJobStatus(null);
    setJobId(null);
    setProgressText('');
    setIsUploading(true);

    // Build the form data
    const formData = new FormData();
    if (!videoFile) {
      setError('Please select a video file.');
      setIsUploading(false);
      return;
    }
    formData.append('video', videoFile);

    if (workflow === 'correction') {
      if (!subtitleFile) {
        setError('Please upload a subtitle file for correction workflow.');
        setIsUploading(false);
        return;
      }
      formData.append('subtitle', subtitleFile);
    }
    formData.append('language', language);

    try {
      // Choose API endpoint
      let endpoint = '';
      if (workflow === 'correction') {
        endpoint = '/api/correct_subtitles';
      } else {
        endpoint = '/api/generate_subtitles';
      }

      setProgressText('Uploading files and initiating job...');
      const response = await fetch(`${apiBase}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Failed to start job (${response.status}): ${await response.text()}`);
      }

      const data = await response.json();
      if (!data.job_id) {
        throw new Error('Job submission failed: Missing job_id in response.');
      }

      setJobId(data.job_id);
      setIsUploading(false);
      setProgressText('Job started. Monitoring progress...');
      monitorJobProgress(data.job_id);
    } catch (err) {
      setError(`Submission Error: ${err.message}`);
      setIsUploading(false);
    }
  }

  // PUBLIC_INTERFACE
  async function monitorJobProgress(jobId) {
    // Poll for job status periodically
    let polling = true;
    let pollInterval = 2000;

    const statusEndpoint = `${apiBase}/api/job_status/${jobId}`;
    const resultEndpoint = `${apiBase}/api/job_result/${jobId}`;

    async function poll() {
      if (!polling) return;
      try {
        const resp = await fetch(statusEndpoint);
        if (!resp.ok) {
          throw new Error(`Failed to fetch job status`);
        }
        const statusData = await resp.json();
        setJobStatus(statusData.status || 'PENDING');
        setProgressText(statusData.detail || `Job status: ${statusData.status}`);

        if (statusData.status === 'COMPLETED') {
          // Fetch download link or result
          const resultResp = await fetch(resultEndpoint);
          if (resultResp.ok) {
            const resultObj = await resultResp.json();
            if (resultObj.result_url) {
              setResultUrl(resultObj.result_url.startsWith('http')
                ? resultObj.result_url
                : `${apiBase}${resultObj.result_url}`
              );
              setProgressText('Job completed! Download your result below.');
            } else if (resultObj.detail) {
              setResultUrl(null);
              setProgressText(resultObj.detail);
            }
          } else {
            setProgressText('Job completed, but failed to fetch result file.');
            setResultUrl(null);
          }
          polling = false;
        } else if (['FAILED', 'CANCELLED', 'ERROR'].includes(statusData.status)) {
          setError(`Job ${statusData.status}: ${statusData.detail || ''}`);
          polling = false;
        } else {
          setTimeout(poll, pollInterval);
        }
      } catch (err) {
        setError('Error checking job status: ' + err.message);
        polling = false;
      }
    }
    poll();
  }

  // PUBLIC_INTERFACE
  function renderUploadForm() {
    return (
      <form className="upload-form" onSubmit={handleSubmit}>
        <label>
          Video File:
          <input
            type="file"
            accept="video/*"
            onChange={handleFileChange(setVideoFile)}
            required
            disabled={isUploading || !!jobId}
          />
        </label>
        {workflow === 'correction' && (
          <label>
            Subtitle File:
            <input
              type="file"
              accept=".srt,.vtt,.ass,.sub"
              onChange={handleFileChange(setSubtitleFile)}
              required
              disabled={isUploading || !!jobId}
            />
          </label>
        )}
        <label>
          Language:
          <select value={language} onChange={handleLanguageChange} disabled={isUploading || !!jobId}>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="zh">Chinese</option>
            <option value="hi">Hindi</option>
            {/* Add more languages as needed */}
          </select>
        </label>
        <button type="submit" disabled={isUploading || !!jobId}>
          {workflow === 'correction' ? 'Start Correction' : 'Start Generation'}
        </button>
      </form>
    );
  }

  // PUBLIC_INTERFACE
  function renderWorkflowSelector() {
    return (
      <div className="workflow-selector">
        <label>
          <input
            type="radio"
            value="correction"
            checked={workflow === 'correction'}
            onChange={handleWorkflowChange}
            disabled={isUploading || !!jobId}
          />
          Subtitle Correction
        </label>
        <label>
          <input
            type="radio"
            value="generation"
            checked={workflow === 'generation'}
            onChange={handleWorkflowChange}
            disabled={isUploading || !!jobId}
          />
          Subtitle Generation
        </label>
      </div>
    );
  }

  // PUBLIC_INTERFACE
  function renderStatusAndResult() {
    return (
      <div className="status-section">
        {progressText && (
          <div className="progress-text">
            <strong>{progressText}</strong>
          </div>
        )}
        {jobStatus && <div>Job Status: <b>{jobStatus}</b></div>}
        {resultUrl && (
          <div className="result-link">
            <a href={resultUrl} target="_blank" rel="noopener noreferrer" download>
              Download Result Subtitle File
            </a>
          </div>
        )}
        {jobId && (
          <button
            onClick={() => window.location.reload()}
            className="reset-btn"
            aria-label="Start New Job"
          >
            New Job
          </button>
        )}
      </div>
    );
  }

  // PUBLIC_INTERFACE
  function renderError() {
    return (
      error && <div className="error-message" aria-live="assertive">{error}</div>
    );
  }

  return (
    <div className="App">
      <header>
        <h1>Subtitle Sync Platform Dashboard</h1>
        <p>
          Upload video (and subtitle) files to check and correct subtitle timing issues or to generate new subtitles.<br/>
          All processing is performed asynchronously. Monitor your job status below.
        </p>
      </header>
      <main>
        {renderWorkflowSelector()}
        {renderError()}
        {!jobId && renderUploadForm()}
        {jobId && renderStatusAndResult()}
      </main>
      <footer>
        <small>
          Powered by Audio-Subtitle-Sync LLM platform &copy; 2024. All rights reserved.
        </small>
      </footer>
    </div>
  );
}

export default App;
