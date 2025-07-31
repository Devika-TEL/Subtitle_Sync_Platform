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
  authenticateUser
} from './services/api';

// Utils
import { downloadBlob, validateFile, formatFileSize, VIDEO_TYPES, SUBTITLE_TYPES } from './utils/fileUtils';

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
  const [activeTab, setActiveTab] = useState('correction');
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
      const response = await correctSubtitles(correctionFiles.video, correctionFiles.subtitle);
      
      // Handle direct file response from backend
      if (response.data instanceof Blob) {
        const filename = `corrected_${correctionFiles.subtitle.name}`;
        downloadBlob(response.data, filename);
        showNotification('Subtitle correction completed! File downloaded.', 'success');
        loadSubtitleFiles(); // Refresh file list
      } else {
        // Handle job-based response (if backend implements job tracking)
        setJobId(response.data.job_id);
        showNotification('Correction job started', 'info');
      }
    } catch (error) {
      console.error('Error processing correction:', error);
      showNotification(
        error.response?.data?.message || 'Failed to process correction. Please try again.',
        'error'
      );
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
      if (response.data instanceof Blob) {
        const filename = `generated_${generationLanguage}_${generationFile.name.replace(/\.[^/.]+$/, '.srt')}`;
        downloadBlob(response.data, filename);
        showNotification('Subtitle generation completed! File downloaded.', 'success');
        loadSubtitleFiles(); // Refresh file list
      } else {
        // Handle job-based response (if backend implements job tracking)
        setJobId(response.data.job_id);
        showNotification('Generation job started', 'info');
      }
    } catch (error) {
      console.error('Error processing generation:', error);
      showNotification(
        error.response?.data?.message || 'Failed to generate subtitles. Please try again.',
        'error'
      );
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
    <div className="dashboard-bg">
      {/* Notifications */}
      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onClose={hideNotification}
        />
      )}

      {/* Header */}
      <header className="dashboard-header">
        <div className="header-content">
          <img
            src="https://svgshare.com/i/148G.svg"
            alt="Subtitle Sync Platform"
            className="dashboard-logo"
          />
          <div className="header-titles">
            <h1 className="main-title">Subtitle Sync Platform</h1>
            <span className="subtitle">
              AI-Powered Subtitle Processing &amp; Translation
            </span>
          </div>
          <div className="header-actions">
            <button
              className="file-manager-btn"
              onClick={() => setShowFileManager(!showFileManager)}
            >
              {showFileManager ? 'Hide Files' : 'My Files'}
            </button>
            <button
              className="file-manager-btn logout-btn"
              onClick={() => {
                localStorage.removeItem('authToken');
                window.location.reload();
              }}
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="workflow-nav">
        <div className="workflow-tabs" role="tablist">
          <button
            className={`workflow-tab${activeTab === 'correction' ? ' active' : ''}`}
            onClick={() => {
              setActiveTab('correction');
              setJobId(null);
            }}
            role="tab"
            aria-selected={activeTab === 'correction'}
          >
            <span>Subtitle Correction</span>
          </button>
          <button
            className={`workflow-tab${activeTab === 'generation' ? ' active' : ''}`}
            onClick={() => {
              setActiveTab('generation');
              setJobId(null);
            }}
            role="tab"
            aria-selected={activeTab === 'generation'}
          >
            <span>Subtitle Generation</span>
          </button>
        </div>
      </nav>

      <main className="dashboard-content">
        {/* Job Progress Tracker */}
        {jobId && (
          <ProgressTracker
            jobId={jobId}
            onComplete={handleJobComplete}
            onError={handleJobError}
          />
        )}

        {/* File Manager */}
        {showFileManager && (
          <section className="file-manager-section">
            <div className="file-manager-card">
              <h2>My Subtitle Files</h2>
              {subtitleFiles.length === 0 ? (
                <p className="no-files-message">No subtitle files found. Process some videos to see files here.</p>
              ) : (
                <div className="file-list">
                  {subtitleFiles.map((file) => (
                    <div key={file.id} className="file-item">
                      <div className="file-info">
                        <h3 className="file-name">{file.filename}</h3>
                        <div className="file-details">
                          <span className="file-language">{file.language}</span>
                          <span className="file-size">{formatFileSize(file.size)}</span>
                          <span className="file-date">{new Date(file.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <div className="file-actions">
                        <button
                          className="download-btn"
                          onClick={() => handleDownloadFile(file.id, file.filename)}
                        >
                          Download
                        </button>
                        <select
                          className="translation-select"
                          onChange={(e) => {
                            if (e.target.value) {
                              handleRequestTranslation(file.id, e.target.value);
                              e.target.value = '';
                            }
                          }}
                          disabled={translationRequests[file.id]}
                        >
                          <option value="">Translate to...</option>
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

        {/* Workflow Panels */}
        <div className="dashboard-panel">
          {activeTab === 'correction' ? (
            <section className="workflow-section">
              <div className="workflow-card">
                <h2 className="workflow-title">
                  Subtitle-Audio Quality Check &amp; Correction
                </h2>
                <p className="workflow-description">
                  Upload a video and its corresponding subtitle file to automatically detect and correct 
                  synchronization issues, caption overlaps, and other quality problems.
                </p>
                
                <form className="upload-form" onSubmit={handleCorrectionSubmit}>
                  <div className="file-upload-group">
                    <label className="file-label">
                      <span>Video File</span>
                      <input
                        type="file"
                        name="video"
                        accept={VIDEO_TYPES.join(',')}
                        onChange={handleCorrectionUpload}
                        required
                        disabled={loading}
                      />
                      {correctionFiles.video && (
                        <div className="file-info">
                          <span className="file-name">{correctionFiles.video.name}</span>
                          <span className="file-size">({formatFileSize(correctionFiles.video.size)})</span>
                        </div>
                      )}
                    </label>
                    
                    <label className="file-label">
                      <span>Subtitle File (.srt, .vtt, .ass, etc.)</span>
                      <input
                        type="file"
                        name="subtitle"
                        accept=".srt,.vtt,.ass,.ssa,.sbv"
                        onChange={handleCorrectionUpload}
                        required
                        disabled={loading}
                      />
                      {correctionFiles.subtitle && (
                        <div className="file-info">
                          <span className="file-name">{correctionFiles.subtitle.name}</span>
                          <span className="file-size">({formatFileSize(correctionFiles.subtitle.size)})</span>
                        </div>
                      )}
                    </label>
                  </div>
                  
                  <button
                    className="action-btn"
                    type="submit"
                    disabled={loading || !correctionFiles.video || !correctionFiles.subtitle}
                  >
                    {loading ? 'Processing...' : 'Run Correction'}
                  </button>
                </form>
              </div>
            </section>
          ) : (
            <section className="workflow-section">
              <div className="workflow-card generation-card">
                <h2 className="workflow-title">
                  Subtitle Generation &amp; Translation
                </h2>
                <p className="workflow-description">
                  Upload a video file to automatically generate subtitles in the specified language 
                  using advanced AI speech recognition.
                </p>
                
                <form className="upload-form" onSubmit={handleGenerationSubmit}>
                  <div className="file-upload-group">
                    <label className="file-label">
                      <span>Video File</span>
                      <input
                        type="file"
                        name="video"
                        accept={VIDEO_TYPES.join(',')}
                        onChange={handleGenerationUpload}
                        required
                        disabled={loading}
                      />
                      {generationFile && (
                        <div className="file-info">
                          <span className="file-name">{generationFile.name}</span>
                          <span className="file-size">({formatFileSize(generationFile.size)})</span>
                        </div>
                      )}
                    </label>
                    
                    <label className="file-label">
                      <span>Target Language</span>
                      <select
                        className="language-dropdown"
                        value={generationLanguage}
                        onChange={(e) => setGenerationLanguage(e.target.value)}
                        disabled={loading}
                      >
                        {SUPPORTED_LANGUAGES.map((lang) => (
                          <option key={lang.code} value={lang.code}>
                            {lang.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  
                  <button
                    className="action-btn generation-btn"
                    type="submit"
                    disabled={loading || !generationFile}
                  >
                    {loading ? 'Processing...' : 'Generate Subtitles'}
                  </button>
                </form>
              </div>
            </section>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="dashboard-footer">
        <div className="footer-content">
          <span>
            &copy; {new Date().getFullYear()} Subtitle Sync Platform &mdash; AI-Powered Video Solutions
          </span>
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
