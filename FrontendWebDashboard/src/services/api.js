import axios from 'axios';

// Get base URL from environment variable with cloud-aware fallback
const getApiBaseUrl = () => {
  // If environment variable is set, use it
  if (process.env.REACT_APP_API_BASE_URL) {
    return process.env.REACT_APP_API_BASE_URL;
  }
  
  // Check if we're running in a cloud environment
  if (typeof window !== 'undefined' && window.location.hostname.includes('beta01.cloud.kavia.ai')) {
    // Extract the port from current URL and use port 3001 for backend
    const currentUrl = new URL(window.location.href);
    const backendUrl = `${currentUrl.protocol}//${currentUrl.hostname.replace(':3000', ':3001')}`;
    return backendUrl;
  }
  
  // Default to localhost for local development
  return 'http://localhost:3001';
};

const API_BASE_URL = getApiBaseUrl();

// Debug logging for API configuration
if (process.env.NODE_ENV === 'development') {
  console.log('API Configuration:', {
    baseURL: API_BASE_URL,
    timeout: 300000,
    environment: process.env.NODE_ENV,
    hostname: typeof window !== 'undefined' ? window.location.hostname : 'server',
    isCloudEnvironment: typeof window !== 'undefined' && window.location.hostname.includes('beta01.cloud.kavia.ai')
  });
}

// Test connectivity on initialization
const testConnectivity = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      timeout: 5000
    });
    if (response.ok) {
      console.log('✅ Backend connectivity verified');
    } else {
      console.warn('⚠️ Backend responded but with error:', response.status);
    }
  } catch (error) {
    console.error('❌ Backend connectivity failed:', error.message);
    console.error('Trying alternative URL configurations...');
    
    // Try alternative URLs if main one fails
    const alternatives = [
      'http://localhost:3001',
      `${window.location.protocol}//${window.location.hostname}:3001`,
      `https://${window.location.hostname.replace(':3000', ':3001')}`
    ];
    
    for (const altUrl of alternatives) {
      try {
        const altResponse = await fetch(`${altUrl}/`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
          timeout: 3000
        });
        if (altResponse.ok) {
          console.log(`✅ Alternative backend URL works: ${altUrl}`);
          break;
        }
      } catch (altError) {
        console.log(`❌ Alternative URL failed: ${altUrl}`);
      }
    }
  }
};

// Run connectivity test in browser environment
if (typeof window !== 'undefined') {
  testConnectivity();
}

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for file processing
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth tokens if needed
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Enhanced error logging for debugging
    console.error('API Error Details:', {
      message: error.message,
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      headers: error.response?.headers,
      config: {
        url: error.config?.url,
        method: error.config?.method,
        baseURL: error.config?.baseURL,
        timeout: error.config?.timeout
      },
      code: error.code,
      network: error.request ? 'Network request made but no response received' : 'Request setup failed'
    });
    
    // Add specific network error handling
    if (error.code === 'NETWORK_ERROR' || error.message.includes('Network Error')) {
      console.error('🔥 NETWORK ERROR DETECTED:');
      console.error('Current API_BASE_URL:', API_BASE_URL);
      console.error('Current window.location:', typeof window !== 'undefined' ? window.location.href : 'N/A');
      console.error('Suggested fixes:');
      console.error('1. Check if backend is running on the correct port');
      console.error('2. Verify CORS configuration');
      console.error('3. Check if URL is accessible from current domain');
    }
    
    // Temporarily disabled auth redirect
    return Promise.reject(error);
  }
);

// PUBLIC_INTERFACE
/**
 * Process video and/or subtitle files
 * @param {FormData} formData - Contains video and/or subtitle files
 * @returns {Promise} - API response with processed file
 */
export const processFiles = async (formData) => {
  try {
    const response = await api.post('/process', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      responseType: 'blob', // For file download
    });
    return response;
  } catch (error) {
    console.error('Error processing files:', error);
    throw error;
  }
};

// PUBLIC_INTERFACE
/**
 * Upload video file for subtitle generation
 * @param {File} videoFile - Video file to process
 * @param {string} language - Target language for subtitle generation
 * @returns {Promise} - API response with generated subtitles
 */
export const generateSubtitles = async (videoFile, language = 'en') => {
  const formData = new FormData();
  formData.append('video', videoFile);
  formData.append('language', language);
  
  return processFiles(formData);
};

// PUBLIC_INTERFACE
/**
 * Upload video and subtitle files for correction
 * @param {File} videoFile - Video file
 * @param {File} subtitleFile - Subtitle file to correct
 * @returns {Promise} - API response with corrected subtitles
 */
export const correctSubtitles = async (videoFile, subtitleFile) => {
  const formData = new FormData();
  formData.append('video', videoFile);
  formData.append('subtitle', subtitleFile);
  
  return processFiles(formData);
};

// PUBLIC_INTERFACE
/**
 * Get job status by ID
 * @param {string} jobId - Job identifier
 * @returns {Promise} - Job status information
 */
export const getJobStatus = async (jobId) => {
  try {
    const response = await api.get(`/jobs/${jobId}/status`);
    return response.data;
  } catch (error) {
    console.error('Error getting job status:', error);
    throw error;
  }
};

// PUBLIC_INTERFACE
/**
 * Get list of user's subtitle files
 * @returns {Promise} - List of subtitle files
 */
export const getSubtitleFiles = async () => {
  try {
    const response = await api.get('/subtitles');
    return response.data;
  } catch (error) {
    console.error('Error getting subtitle files:', error);
    throw error;
  }
};

// PUBLIC_INTERFACE
/**
 * Download subtitle file by ID
 * @param {string} fileId - File identifier
 * @returns {Promise} - File blob response
 */
export const downloadSubtitleFile = async (fileId) => {
  try {
    const response = await api.get(`/subtitles/${fileId}/download`, {
      responseType: 'blob',
    });
    return response;
  } catch (error) {
    console.error('Error downloading file:', error);
    throw error;
  }
};

// PUBLIC_INTERFACE
/**
 * Request translation of subtitle file
 * @param {string} fileId - Source file identifier
 * @param {string} targetLanguage - Target language code
 * @returns {Promise} - Translation job response
 */
export const requestTranslation = async (fileId, targetLanguage) => {
  try {
    const response = await api.post(`/subtitles/${fileId}/translate`, {
      target_language: targetLanguage,
    });
    return response.data;
  } catch (error) {
    console.error('Error requesting translation:', error);
    throw error;
  }
};

// PUBLIC_INTERFACE
/**
 * User authentication
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise} - Authentication response
 */
export const authenticateUser = async (email, password) => {
  try {
    const response = await api.post('/auth/login', {
      email,
      password,
    });
    return response.data;
  } catch (error) {
    console.error('Error during authentication:', error);
    throw error;
  }
};

// PUBLIC_INTERFACE
/**
 * User registration
 * @param {Object} userData - User registration data
 * @returns {Promise} - Registration response
 */
export const registerUser = async (userData) => {
  try {
    const response = await api.post('/auth/register', userData);
    return response.data;
  } catch (error) {
    console.error('Error during registration:', error);
    throw error;
  }
};

export default api;
