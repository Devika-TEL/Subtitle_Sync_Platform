/**
 * Test script to verify API connectivity after fixing the network error
 */

const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');

// Updated API base URL to use new deployment URL
const API_BASE_URL = process.env.API_BASE_URL || 'https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001';

console.log('Testing API connectivity with fixed configuration...');
console.log('API Base URL:', API_BASE_URL);

// Test 1: Health check
async function testHealthCheck() {
    console.log('\n=== Testing Health Check ===');
    try {
        const response = await axios.get(`${API_BASE_URL}/`);
        console.log('✅ Health check successful');
        console.log('Response:', response.data);
        return true;
    } catch (error) {
        console.log('❌ Health check failed');
        console.log('Error:', error.message);
        if (error.response) {
            console.log('Status:', error.response.status);
            console.log('Data:', error.response.data);
        }
        return false;
    }
}

// Test 2: Process endpoint (correction workflow)
async function testCorrectionWorkflow() {
    console.log('\n=== Testing Correction Workflow ===');
    
    // Check if sample files exist
    const videoPath = path.join(__dirname, 'assets', 'sample_video.mp4');
    const subtitlePath = path.join(__dirname, 'assets', 'sample_subtitle.srt');
    
    // Create dummy files if they don't exist
    if (!fs.existsSync(subtitlePath)) {
        const sampleSrt = `1
00:00:01,000 --> 00:00:05,000
Test subtitle content for correction workflow.

2
00:00:06,000 --> 00:00:10,000
This is a sample subtitle file for testing.
`;
        fs.writeFileSync(subtitlePath, sampleSrt);
        console.log('Created sample subtitle file');
    }
    
    try {
        const formData = new FormData();
        
        // Use existing subtitle file
        formData.append('subtitle', fs.createReadStream(subtitlePath));
        
        // Create a minimal dummy video file for testing
        const dummyVideoContent = Buffer.alloc(1024, 'dummy video content');
        formData.append('video', dummyVideoContent, {
            filename: 'test_video.mp4',
            contentType: 'video/mp4'
        });
        
        const response = await axios.post(`${API_BASE_URL}/process`, formData, {
            headers: {
                ...formData.getHeaders(),
            },
            timeout: 30000, // 30 second timeout
        });
        
        console.log('✅ Correction workflow test successful');
        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers['content-type']);
        return true;
        
    } catch (error) {
        console.log('❌ Correction workflow test failed');
        console.log('Error:', error.message);
        if (error.response) {
            console.log('Status:', error.response.status);
            console.log('Status Text:', error.response.statusText);
            console.log('Data:', error.response.data);
        }
        return false;
    }
}

// Test 3: Generation workflow
async function testGenerationWorkflow() {
    console.log('\n=== Testing Generation Workflow ===');
    
    try {
        const formData = new FormData();
        
        // Create a minimal dummy video file for testing
        const dummyVideoContent = Buffer.alloc(1024, 'dummy video content');
        formData.append('video', dummyVideoContent, {
            filename: 'test_video.mp4',
            contentType: 'video/mp4'
        });
        formData.append('language', 'en');
        
        const response = await axios.post(`${API_BASE_URL}/process`, formData, {
            headers: {
                ...formData.getHeaders(),
            },
            timeout: 30000, // 30 second timeout
        });
        
        console.log('✅ Generation workflow test successful');
        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers['content-type']);
        return true;
        
    } catch (error) {
        console.log('❌ Generation workflow test failed');
        console.log('Error:', error.message);
        if (error.response) {
            console.log('Status:', error.response.status);
            console.log('Status Text:', error.response.statusText);
            console.log('Data:', error.response.data);
        }
        return false;
    }
}

// Run all tests
async function runAllTests() {
    console.log('Starting API connectivity tests after network error fix...\n');
    
    const results = {
        healthCheck: await testHealthCheck(),
        correction: await testCorrectionWorkflow(),
        generation: await testGenerationWorkflow()
    };
    
    console.log('\n=== Test Results Summary ===');
    console.log('Health Check:', results.healthCheck ? '✅ PASS' : '❌ FAIL');
    console.log('Correction Workflow:', results.correction ? '✅ PASS' : '❌ FAIL');
    console.log('Generation Workflow:', results.generation ? '✅ PASS' : '❌ FAIL');
    
    const allPassed = Object.values(results).every(result => result);
    console.log('\nOverall Result:', allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED');
    
    if (allPassed) {
        console.log('\n🎉 Network error fix successful! Frontend should now work correctly.');
    } else {
        console.log('\n⚠️  Some issues remain. Check the backend server status and configuration.');
    }
}

// Execute tests
runAllTests().catch(console.error);
