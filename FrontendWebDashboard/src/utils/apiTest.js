// PUBLIC_INTERFACE
/**
 * Test API connectivity and basic functionality
 * This utility can be used to verify frontend-backend integration
 */
export const testApiConnection = async () => {
  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  
  try {
    // Test basic connectivity
    const response = await fetch(`${API_BASE_URL}/openapi.json`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const openapi = await response.json();
    console.log('✅ Backend API is accessible');
    console.log('📋 API Title:', openapi.info?.title);
    console.log('📄 API Version:', openapi.info?.version);
    console.log('🔗 Available endpoints:', Object.keys(openapi.paths || {}));
    
    return {
      success: true,
      title: openapi.info?.title,
      version: openapi.info?.version,
      endpoints: Object.keys(openapi.paths || {})
    };
  } catch (error) {
    console.error('❌ Backend API connection failed:', error.message);
    return {
      success: false,
      error: error.message
    };
  }
};

// PUBLIC_INTERFACE
/**
 * Test file processing endpoint with mock data
 */
export const testFileProcessing = async () => {
  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  
  try {
    // Create a simple test file
    const testContent = "1\n00:00:01,000 --> 00:00:03,000\nTest subtitle\n\n";
    const testFile = new Blob([testContent], { type: 'text/plain' });
    
    const formData = new FormData();
    formData.append('subtitle', testFile, 'test.srt');
    
    const response = await fetch(`${API_BASE_URL}/process`, {
      method: 'POST',
      body: formData
    });
    
    if (response.ok) {
      console.log('✅ File processing endpoint is working');
      return { success: true };
    } else {
      console.log('⚠️ File processing endpoint returned:', response.status);
      return { success: false, status: response.status };
    }
  } catch (error) {
    console.error('❌ File processing test failed:', error.message);
    return { success: false, error: error.message };
  }
};
