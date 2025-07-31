/**
 * Contains utility functions for API testing, including connectivity checks and file processing tests.
 */

import api from '../services/api';

// PUBLIC_INTERFACE
/**
 * Test API connectivity and endpoints
 * @returns {Promise<Object>} Test results
 */
export const testApiConnectivity = async () => {
  const results = {
    success: false,
    tests: {},
    errors: [],
    recommendations: []
  };

  console.log('🔍 Testing API connectivity...');

  // Test 1: Health check
  try {
    const response = await fetch(api.defaults.baseURL + '/', {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      timeout: 5000
    });
    
    if (response.ok) {
      const data = await response.json();
      results.tests.healthCheck = { success: true, data };
      console.log('✅ Health check passed:', data);
    } else {
      results.tests.healthCheck = { success: false, status: response.status, statusText: response.statusText };
      results.errors.push(`Health check failed: ${response.status} ${response.statusText}`);
    }
  } catch (error) {
    results.tests.healthCheck = { success: false, error: error.message };
    results.errors.push(`Health check error: ${error.message}`);
    console.error('❌ Health check failed:', error);
  }

  // Test 2: CORS preflight
  try {
    const response = await fetch(api.defaults.baseURL + '/process', {
      method: 'OPTIONS',
      headers: { 
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type'
      }
    });
    
    results.tests.corsCheck = { 
      success: response.ok, 
      status: response.status,
      headers: Object.fromEntries(response.headers.entries())
    };
    
    if (response.ok) {
      console.log('✅ CORS preflight passed');
    } else {
      results.errors.push(`CORS preflight failed: ${response.status}`);
    }
  } catch (error) {
    results.tests.corsCheck = { success: false, error: error.message };
    results.errors.push(`CORS preflight error: ${error.message}`);
    console.error('❌ CORS preflight failed:', error);
  }

  // Test 3: Endpoint availability
  const endpoints = ['/process', '/subtitles', '/jobs/1/status'];
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(api.defaults.baseURL + endpoint, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      
      results.tests[`endpoint_${endpoint.replace('/', '_')}`] = {
        success: response.status !== 404,
        status: response.status,
        available: response.status !== 404
      };
      
      if (response.status !== 404) {
        console.log(`✅ Endpoint ${endpoint} is available`);
      }
    } catch (error) {
      results.tests[`endpoint_${endpoint.replace('/', '_')}`] = {
        success: false,
        error: error.message
      };
    }
  }

  // Add recommendations based on test results
  if (results.errors.length > 0) {
    results.recommendations.push('Check if backend service is running');
    results.recommendations.push('Verify API base URL configuration');
    results.recommendations.push('Check network connectivity');
    results.recommendations.push('Verify CORS configuration on backend');
  }

  results.success = results.errors.length === 0;
  
  console.log('📊 API Connectivity Test Results:', results);
  return results;
};

// PUBLIC_INTERFACE
/**
 * Test file processing with mock data
 * @returns {Promise<Object>} Test results
 */
export const testFileProcessing = async () => {
  console.log('🧪 Testing file processing...');
  
  try {
    // Create a small test file
    const testContent = 'This is a test file for API connectivity';
    const testFile = new Blob([testContent], { type: 'text/plain' });
    const formData = new FormData();
    formData.append('test', testFile, 'test.txt');

    const response = await api.post('/process', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 10000
    });

    console.log('✅ File processing test passed');
    return { success: true, message: 'File processing test completed', response: response.status };
  } catch (error) {
    console.error('❌ File processing test failed:', error);
    return { 
      success: false, 
      message: 'File processing test failed', 
      error: error.message,
      details: {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      }
    };
  }
};

// PUBLIC_INTERFACE
/**
 * Run comprehensive API diagnostics
 * @returns {Promise<Object>} Diagnostic results
 */
export const runApiDiagnostics = async () => {
  console.log('🔧 Running comprehensive API diagnostics...');
  
  const diagnostics = {
    timestamp: new Date().toISOString(),
    environment: {
      baseURL: api.defaults.baseURL,
      hostname: typeof window !== 'undefined' ? window.location.hostname : 'unknown',
      protocol: typeof window !== 'undefined' ? window.location.protocol : 'unknown',
      port: typeof window !== 'undefined' ? window.location.port : 'unknown'
    },
    connectivity: null,
    processing: null,
    summary: {
      allTestsPassed: false,
      criticalIssues: [],
      recommendations: []
    }
  };

  // Run connectivity tests
  diagnostics.connectivity = await testApiConnectivity();
  
  // Run processing tests only if connectivity is OK
  if (diagnostics.connectivity.success) {
    diagnostics.processing = await testFileProcessing();
  } else {
    diagnostics.processing = { success: false, message: 'Skipped due to connectivity issues' };
  }

  // Generate summary
  diagnostics.summary.allTestsPassed = diagnostics.connectivity.success && diagnostics.processing.success;
  
  if (!diagnostics.connectivity.success) {
    diagnostics.summary.criticalIssues.push('API connectivity failed');
    diagnostics.summary.recommendations.push('Check backend service status');
    diagnostics.summary.recommendations.push('Verify network configuration');
  }
  
  if (!diagnostics.processing.success && diagnostics.connectivity.success) {
    diagnostics.summary.criticalIssues.push('File processing failed');
    diagnostics.summary.recommendations.push('Check /process endpoint implementation');
    diagnostics.summary.recommendations.push('Verify file upload handling');
  }

  console.log('📋 API Diagnostics Complete:', diagnostics);
  return diagnostics;
};

// Legacy functions for backward compatibility
export const testApiConnection = testApiConnectivity;
