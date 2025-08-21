import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import './App.css';

// Components
import Notification from './components/Notification';
import ProgressTracker from './components/ProgressTracker';
import Register from './components/Register/Register';

// Services
import { 
  generateSubtitles, 
  correctSubtitles,
  getSubtitleFiles,
  downloadSubtitleFile,
  requestTranslation,
  authenticateUser,
  testBackend
} from './services/api';

// Utils
import { downloadBlob, validateFile, formatFileSize, VIDEO_TYPES, SUBTITLE_TYPES, SUBTITLE_EXTENSIONS } from './utils/fileUtils';

const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ru', name: 'Russian' },
];

// Main Dashboard Component
const Dashboard = () => {
  // State management
  const [activeTab, setActiveTab] = useState('generation');
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [jobId, setJobId] = useState(null);
  
  // Correction workflow state
  const [correctionFiles, setCorrectionFiles] = useState({ video: null, subtitle: null });
  
  // Generation workflow state
  const [generationFile, setGenerationFile] = useState(null);
  const [generationLanguage, setGenerationLanguage] = useState('en');
  
  // File management state
  const [subtitleFiles, setSubtitleFiles] = useState([]);
  const [showFileManager, setShowFileManager] = useState(false);
  
  // Translation state
  const [translationRequests, setTranslationRequests] = useState({});
  
  // Debug state for development
  const [debugInfo, setDebugInfo] = useState(null);
  const [showDebug, setShowDebug] = useState(process.env.NODE_ENV === 'development');

  // Load subtitle files on component mount
  useEffect(() => {
    loadSubtitleFiles();
  }, []);

  // Notification helper
  const showNotification = (message, type = 'info') => {
    setNotification({ message, type, id: Date.now() });
  };

  const hideNotification = () => {
    setNotification(null);
  };

  // PUBLIC_INTERFACE
  /**
   * Load user's subtitle files from backend
   */
  const loadSubtitleFiles = async () => {
    try {
      const files = await getSubtitleFiles();
      setSubtitleFiles(files);
    } catch (error) {
      console.error('Error loading subtitle files:', error);
      // Don't show error notification for this as it might be expected (no auth, etc.)
    }
  };

  // File upload handlers
  const handleCorrectionUpload = (e) => {
    const { name, files } = e.target;
    const file = files[0];
    
    if (!file) return;
    
    const allowedTypes = name === 'video' ? VIDEO_TYPES : SUBTITLE_TYPES;
    const validation = validateFile(file, allowedTypes);
    
    if (!validation.isValid) {
      showNotification(validation.errors.join(', '), 'error');
      return;
    }
    
    setCorrectionFiles(prev => ({ ...prev, [name]: file }));
    showNotification(`${name} file selected: ${file.name}`, 'success');
  };

  const handleGenerationUpload = (e) => {
    const file = e.target.files[0];
    
    if (!file) return;
    
    const validation = validateFile(file, VIDEO_TYPES);
    
    if (!validation.isValid) {
      showNotification(validation.errors.join(', '), 'error');
      return;
    }
    
    setGenerationFile(file);
    showNotification(`Video file selected: ${file.name}`, 'success');
  };

  // Workflow submission handlers
  const handleCorrectionSubmit = async (e) => {
    e.preventDefault();
    
    if (!correctionFiles.video || !correctionFiles.subtitle) {
      showNotification('Please select both video and subtitle files', 'error');
      return;
    }
    
    setLoading(true);
    setJobId(null);
    
    try {
      setDebugInfo({ action: 'Starting correction', files: { video: correctionFiles.video.name, subtitle: correctionFiles.subtitle.name } });
      const response = await correctSubtitles(correctionFiles.video, correctionFiles.subtitle);
      setDebugInfo({ action: 'Correction response received', responseType: typeof response.data, responseSize: response.data?.length || 'unknown' });
      
      // Handle direct file response from backend
      if (response.data instanceof Blob || (response.data && typeof response.data === 'string' && response.data.includes('-->'))) {
        const filename = `corrected_${correctionFiles.subtitle.name}`;
        
        // Handle both Blob and text responses
        if (response.data instanceof Blob) {
          downloadBlob(response.data, filename);
        } else {
          // Create blob from text response
          const blob = new Blob([response.data], { type: 'text/plain' });
          downloadBlob(blob, filename);
        }
        
        showNotification('Subtitle correction completed! File downloaded.', 'success');
        loadSubtitleFiles(); // Refresh file list
      } else {
        // Handle job-based response (if backend implements job tracking)
        setJobId(response.data.job_id);
        showNotification('Correction job started', 'info');
      }
    } catch (error) {
      const errorDetails = {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        headers: error.response?.headers,
        code: error.code,
        config: {
          url: error.config?.url,
          method: error.config?.method,
          baseURL: error.config?.baseURL,
          timeout: error.config?.timeout
        }
      };
      
      console.error('Correction Error Details:', errorDetails);
      setDebugInfo({ action: 'Correction error', error: errorDetails });
      
      // Enhanced error message construction
      let errorMessage = 'Failed to process correction. Please try again.';
      
      if (error.response) {
        // Server responded with error status
        if (error.response.status === 400) {
          errorMessage = error.response.data?.detail || error.response.data?.message || 'Invalid file format or request data.';
        } else if (error.response.status === 413) {
          errorMessage = 'File size too large. Please use smaller files.';
        } else if (error.response.status === 422) {
          errorMessage = 'Invalid file format. Please check your video and subtitle files.';
        } else if (error.response.status === 500) {
          errorMessage = 'Server processing error. Please try again or contact support.';
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        } else if (error.response.data?.message) {
          errorMessage = error.response.data.message;
        } else {
          errorMessage = `Server error (${error.response.status}): ${error.response.statusText}`;
        }
      } else if (error.request) {
        // Network error
        errorMessage = 'Network error. Please check your connection and try again.';
      } else if (error.code === 'ECONNABORTED') {
        // Timeout error
        errorMessage = 'Request timeout. The processing is taking too long. Please try with smaller files.';
      }
      
      showNotification(errorMessage, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerationSubmit = async (e) => {
    e.preventDefault();
    
    if (!generationFile) {
      showNotification('Please select a video file', 'error');
      return;
    }
    
    setLoading(true);
    setJobId(null);
    
    try {
      const response = await generateSubtitles(generationFile, generationLanguage);
      
      // Handle direct file response from backend
      if (response.data instanceof Blob || (response.data && typeof response.data === 'string' && response.data.includes('-->'))) {
        const filename = `generated_${generationLanguage}_${generationFile.name.replace(/\.[^/.]+$/, '.srt')}`;
        
        // Handle both Blob and text responses
        if (response.data instanceof Blob) {
          downloadBlob(response.data, filename);
        } else {
          // Create blob from text response
          const blob = new Blob([response.data], { type: 'text/plain' });
          downloadBlob(blob, filename);
        }
        
        showNotification('Subtitle generation completed! File downloaded.', 'success');
        loadSubtitleFiles(); // Refresh file list
      } else {
        // Handle job-based response (if backend implements job tracking)
        setJobId(response.data.job_id);
        showNotification('Generation job started', 'info');
      }
    } catch (error) {
      console.error('Generation Error Details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        headers: error.response?.headers,
        stack: error.stack
      });
      
      // Enhanced error message construction
      let errorMessage = 'Failed to generate subtitles. Please try again.';
      
      if (error.response) {
        // Server responded with error status
        if (error.response.status === 400) {
          errorMessage = error.response.data?.detail || error.response.data?.message || 'Invalid video file or request data.';
        } else if (error.response.status === 413) {
          errorMessage = 'Video file too large. Please use a smaller file.';
        } else if (error.response.status === 422) {
          errorMessage = 'Invalid video format. Please check your video file.';
        } else if (error.response.status === 500) {
          errorMessage = 'Server processing error. Please try again or contact support.';
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        } else if (error.response.data?.message) {
          errorMessage = error.response.data.message;
        } else {
          errorMessage = `Server error (${error.response.status}): ${error.response.statusText}`;
        }
      } else if (error.request) {
        // Network error
        errorMessage = 'Network error. Please check your connection and try again.';
      } else if (error.code === 'ECONNABORTED') {
        // Timeout error
        errorMessage = 'Request timeout. The processing is taking too long. Please try with a smaller file.';
      }
      
      showNotification(errorMessage, 'error');
    } finally {
      setLoading(false);
    }
  };

  // File management handlers
  const handleDownloadFile = async (fileId, filename) => {
    try {
      const response = await downloadSubtitleFile(fileId);
      downloadBlob(response.data, filename);
      showNotification(`Downloaded ${filename}`, 'success');
    } catch (error) {
      console.error('Error downloading file:', error);
      showNotification('Failed to download file', 'error');
    }
  };

  const handleRequestTranslation = async (fileId, targetLanguage) => {
    try {
      setTranslationRequests(prev => ({ ...prev, [fileId]: true }));
      const result = await requestTranslation(fileId, targetLanguage);
      
      if (result.job_id) {
        showNotification(`Translation to ${targetLanguage} started`, 'info');
      } else {
        showNotification(`Translation request submitted`, 'info');
      }
      
      setTimeout(() => loadSubtitleFiles(), 1000); // Refresh after a delay
    } catch (error) {
      console.error('Error requesting translation:', error);
      showNotification('Failed to request translation', 'error');
    } finally {
      setTranslationRequests(prev => ({ ...prev, [fileId]: false }));
    }
  };

  // Job completion handlers
  const handleJobComplete = (jobStatus) => {
    showNotification('Processing completed successfully!', 'success');
    setJobId(null);
    loadSubtitleFiles();
  };

  const handleJobError = (error) => {
    showNotification('Processing failed. Please try again.', 'error');
    setJobId(null);
  };

  return (
    <div className="dashboard-container">
      {/* Notifications */}
      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onClose={hideNotification}
        />
      )}

      {/* Debug Panel */}
      {showDebug && debugInfo && (
        <div style={{
          position: 'fixed',
          top: '10px',
          right: '10px',
          background: '#f0f0f0',
          border: '1px solid #ccc',
          padding: '10px',
          borderRadius: '5px',
          maxWidth: '400px',
          fontSize: '12px',
          zIndex: 1000
        }}>
          <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>Debug Info:</div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {JSON.stringify(debugInfo, null, 2)}
          </pre>
          <button 
            onClick={() => setDebugInfo(null)}
            style={{ marginTop: '5px', fontSize: '10px' }}
          >
            Clear
          </button>
        </div>
      )}

      {/* Header */}
      <header className="dashboard-header">
        <div className="container">
          <div className="header-content">
            <div className="brand-section">
              <div className="brand-icon">
                <div className="icon-gradient">🎬</div>
              </div>
              <div className="brand-text">
                <h1 className="brand-title">SubtitleSync</h1>
                <p className="brand-tagline">AI-Powered Subtitle Processing</p>
              </div>
            </div>
            
            <div className="header-actions">
              <button
                className={`header-btn files-btn ${showFileManager ? 'active' : ''}`}
                onClick={() => setShowFileManager(!showFileManager)}
              >
                <span className="btn-icon">📁</span>
                <span>My Files</span>
                {subtitleFiles.length > 0 && (
                  <span className="file-count">{subtitleFiles.length}</span>
                )}
              </button>
              <button
                className="header-btn files-btn"
                onClick={async () => {
                  try {
                    const data = await testBackend();
                    // Show result as alert for quick visibility
                    alert(`Backend says: ${data?.message ?? 'no message'}`);
                  } catch (e) {
                    alert('Backend test failed. Check console for details.');
                    console.error('Test Backend error:', e);
                  }
                }}
                aria-label="Test Backend"
                title="Test Backend"
              >
                <span className="btn-icon">🧪</span>
                <span>Test Backend</span>
              </button>
              <button
                className="header-btn logout-btn"
                onClick={() => {
                  localStorage.removeItem('authToken');
                  window.location.reload();
                }}
              >
                <span className="btn-icon">🚪</span>
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="container">
          <div className="hero-content">
            <h2 className="hero-title">Transform Your Videos with AI</h2>
            <p className="hero-subtitle">Generate, correct, and translate subtitles with cutting-edge AI technology</p>
            
            {/* Enhanced Navigation Tabs */}
            <div className="feature-tabs">
              <button
                className={`feature-tab ${activeTab === 'generation' ? 'active' : ''}`}
                onClick={() => {
                  setActiveTab('generation');
                  setJobId(null);
                }}
              >
                <div className="tab-icon">✨</div>
                <div className="tab-content">
                  <div className="tab-title">AI Generation</div>
                  <div className="tab-description">Create subtitles from scratch</div>
                </div>
              </button>
              
              <button
                className={`feature-tab ${activeTab === 'correction' ? 'active' : ''}`}
                onClick={() => {
                  setActiveTab('correction');
                  setJobId(null);
                }}
              >
                <div className="tab-icon">🔧</div>
                <div className="tab-content">
                  <div className="tab-title">Smart Correction</div>
                  <div className="tab-description">Fix timing and quality issues</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </section>

      <main className="main-content">
        <div className="container">
          {/* Job Progress Tracker */}
          {jobId && (
            <div className="progress-section">
              <ProgressTracker
                jobId={jobId}
                onComplete={handleJobComplete}
                onError={handleJobError}
              />
            </div>
          )}

          {/* File Manager */}
          {showFileManager && (
            <section className="file-manager-section">
              <div className="section-card">
                <div className="section-header">
                  <h3 className="section-title">
                    <span className="title-icon">📂</span>
                    Your Subtitle Library
                  </h3>
                  <span className="file-count-badge">{subtitleFiles.length} files</span>
                </div>
                
                {subtitleFiles.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">📭</div>
                    <h4>No files yet</h4>
                    <p>Process some videos to see your subtitle files here</p>
                  </div>
                ) : (
                  <div className="file-grid">
                    {subtitleFiles.map((file) => (
                      <div key={file.id} className="file-card">
                        <div className="file-header">
                          <div className="file-icon">📄</div>
                          <div className="file-meta">
                            <h4 className="file-name">{file.filename}</h4>
                            <div className="file-details">
                              <span className="language-tag">{file.language}</span>
                              <span className="file-size">{formatFileSize(file.size)}</span>
                              <span className="file-date">{new Date(file.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="file-actions">
                          <button
                            className="action-btn primary"
                            onClick={() => handleDownloadFile(file.id, file.filename)}
                          >
                            <span>📥</span>
                            Download
                          </button>
                          <select
                            className="translate-select"
                            onChange={(e) => {
                              if (e.target.value) {
                                handleRequestTranslation(file.id, e.target.value);
                                e.target.value = '';
                              }
                            }}
                            disabled={translationRequests[file.id]}
                          >
                            <option value="">🌐 Translate...</option>
                            {SUPPORTED_LANGUAGES
                              .filter(lang => lang.code !== file.language)
                              .map(lang => (
                                <option key={lang.code} value={lang.code}>
                                  {lang.name}
                                </option>
                              ))}
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Workflow Sections */}
          <section className="workflow-section">
            {activeTab === 'generation' ? (
              <div className="workflow-card generation-workflow">
                <div className="workflow-header">
                  <div className="workflow-icon">✨</div>
                  <div className="workflow-info">
                    <h3 className="workflow-title">AI Subtitle Generation</h3>
                    <p className="workflow-description">
                      Upload your video and let our AI create accurate subtitles in your chosen language
                    </p>
                  </div>
                </div>
                
                <form className="upload-form" onSubmit={handleGenerationSubmit}>
                  <div className="form-section">
                    <h4 className="form-section-title">📹 Video Upload</h4>
                    <div className="upload-area">
                      <input
                        type="file"
                        id="generation-video"
                        accept={VIDEO_TYPES.join(',')}
                        onChange={handleGenerationUpload}
                        required
                        disabled={loading}
                        className="file-input"
                      />
                      <label htmlFor="generation-video" className="upload-label">
                        {generationFile ? (
                          <div className="file-selected">
                            <div className="file-preview">
                              <span className="file-icon">🎥</span>
                              <div className="file-info">
                                <span className="file-name">{generationFile.name}</span>
                                <span className="file-size">({formatFileSize(generationFile.size)})</span>
                              </div>
                            </div>
                            <button 
                              type="button"
                              className="remove-file"
                              onClick={() => setGenerationFile(null)}
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <div className="upload-placeholder">
                            <div className="upload-icon">📤</div>
                            <div className="upload-text">
                              <strong>Choose your video file</strong>
                              <span>or drag and drop it here</span>
                            </div>
                          </div>
                        )}
                      </label>
                    </div>
                  </div>
                  
                  <div className="form-section">
                    <h4 className="form-section-title">🌍 Language Selection</h4>
                    <div className="language-grid">
                      {SUPPORTED_LANGUAGES.map((lang) => (
                        <label key={lang.code} className={`language-option ${generationLanguage === lang.code ? 'selected' : ''}`}>
                          <input
                            type="radio"
                            name="language"
                            value={lang.code}
                            checked={generationLanguage === lang.code}
                            onChange={(e) => setGenerationLanguage(e.target.value)}
                            disabled={loading}
                          />
                          <span className="language-name">{lang.name}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  
                  <div className="form-actions">
                    <button
                      className="submit-btn generation-btn"
                      type="submit"
                      disabled={loading || !generationFile}
                    >
                      {loading ? (
                        <>
                          <span className="loading-spinner"></span>
                          Generating...
                        </>
                      ) : (
                        <>
                          <span>✨</span>
                          Generate Subtitles
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <div className="workflow-card correction-workflow">
                <div className="workflow-header">
                  <div className="workflow-icon">🔧</div>
                  <div className="workflow-info">
                    <h3 className="workflow-title">Smart Subtitle Correction</h3>
                    <p className="workflow-description">
                      Upload your video and subtitle files to automatically fix timing, overlaps, and quality issues
                    </p>
                  </div>
                </div>
                
                <form className="upload-form" onSubmit={handleCorrectionSubmit}>
                  <div className="upload-grid">
                    <div className="form-section">
                      <h4 className="form-section-title">📹 Video File</h4>
                      <div className="upload-area">
                        <input
                          type="file"
                          id="correction-video"
                          accept={VIDEO_TYPES.join(',')}
                          onChange={handleCorrectionUpload}
                          name="video"
                          required
                          disabled={loading}
                          className="file-input"
                        />
                        <label htmlFor="correction-video" className="upload-label">
                          {correctionFiles.video ? (
                            <div className="file-selected">
                              <div className="file-preview">
                                <span className="file-icon">🎥</span>
                                <div className="file-info">
                                  <span className="file-name">{correctionFiles.video.name}</span>
                                  <span className="file-size">({formatFileSize(correctionFiles.video.size)})</span>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div className="upload-placeholder">
                              <div className="upload-icon">📤</div>
                              <div className="upload-text">
                                <strong>Choose video file</strong>
                              </div>
                            </div>
                          )}
                        </label>
                      </div>
                    </div>
                    
                    <div className="form-section">
                      <h4 className="form-section-title">📄 Subtitle File</h4>
                      <div className="upload-area">
                        <input
                          type="file"
                          id="correction-subtitle"
                          accept={SUBTITLE_EXTENSIONS}
                          onChange={handleCorrectionUpload}
                          name="subtitle"
                          required
                          disabled={loading}
                          className="file-input"
                        />
                        <label htmlFor="correction-subtitle" className="upload-label">
                          {correctionFiles.subtitle ? (
                            <div className="file-selected">
                              <div className="file-preview">
                                <span className="file-icon">📄</span>
                                <div className="file-info">
                                  <span className="file-name">{correctionFiles.subtitle.name}</span>
                                  <span className="file-size">({formatFileSize(correctionFiles.subtitle.size)})</span>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div className="upload-placeholder">
                              <div className="upload-icon">📤</div>
                              <div className="upload-text">
                                <strong>Choose subtitle file</strong>
                                <span>SRT, VTT, ASS, SSA, SCC, SUB, SMI</span>
                              </div>
                            </div>
                          )}
                        </label>
                      </div>
                    </div>
                  </div>
                  
                  <div className="form-actions">
                    <button
                      className="submit-btn correction-btn"
                      type="submit"
                      disabled={loading || !correctionFiles.video || !correctionFiles.subtitle}
                    >
                      {loading ? (
                        <>
                          <span className="loading-spinner"></span>
                          Processing...
                        </>
                      ) : (
                        <>
                          <span>🔧</span>
                          Fix Subtitles
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="dashboard-footer">
        <div className="container">
          <div className="footer-content">
            <p>&copy; {new Date().getFullYear()} SubtitleSync - Powered by AI</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

// Wrapper components to use navigation hooks
const LoginWrapper = ({ onLogin }) => {
  const navigate = useNavigate();
  
  return (
    <LoginForm 
      onLogin={onLogin}
      onSwitchToRegister={() => navigate('/register')}
    />
  );
};

const RegisterWrapper = ({ onRegisterSuccess }) => {
  const navigate = useNavigate();
  
  return (
    <Register 
      onRegisterSuccess={onRegisterSuccess}
      onSwitchToLogin={() => navigate('/login')}
    />
  );
};

// Auth Components
const LoginForm = ({ onLogin, onSwitchToRegister }) => {
  const [credentials, setCredentials] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const result = await authenticateUser(credentials.email, credentials.password);
      localStorage.setItem('authToken', result.token);
      onLogin(result.user);
    } catch (err) {
      setError('Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h2>Login</h2>
        {error && <div className="auth-error">{error}</div>}
        <input
          type="email"
          placeholder="Email"
          value={credentials.email}
          onChange={(e) => setCredentials({...credentials, email: e.target.value})}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={credentials.password}
          onChange={(e) => setCredentials({...credentials, password: e.target.value})}
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
        <div className="auth-footer">
          <p>
            Don't have an account?{' '}
            <button
              type="button"
              className="link-button"
              onClick={onSwitchToRegister}
              disabled={loading}
            >
              Sign Up
            </button>
          </p>
        </div>
      </form>
    </div>
  );
};

// Main App Component
const App = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing auth token
    const token = localStorage.getItem('authToken');
    if (token) {
      // In a real app, verify the token with the backend
      setUser({ token });
    }
    setLoading(false);
  }, []);

  const handleLogin = (userData) => {
    setUser(userData);
  };

  const handleRegisterSuccess = (userData) => {
    // Auto-login after successful registration
    setUser(userData);
  };

  if (loading) {
    return <div className="loading-spinner">Loading...</div>;
  }

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route 
            path="/" 
            element={<Dashboard />} 
          />
          <Route 
            path="/login" 
            element={<Navigate to="/" replace />} 
          />
          <Route 
            path="/register" 
            element={<Navigate to="/" replace />} 
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
};

export default App;
