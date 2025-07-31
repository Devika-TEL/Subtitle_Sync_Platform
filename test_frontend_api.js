/**
 * Test script to verify frontend API connectivity
 * Run with: node test_frontend_api.js
 */

const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');

// Test configuration - use environment variable or default to new URL
const API_BASE_URL = process.env.API_BASE_URL || 'https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001';
const TEST_SRT_CONTENT = `1
00:00:01,000 --> 00:00:05,000
This is a test subtitle for frontend connectivity.

2
00:00:06,000 --> 00:00:10,000
Testing the correction workflow from frontend.

3
00:00:11,000 --> 00:00:15,000
Verifying the API integration works correctly.
`;

const TEST_VIDEO_CONTENT = Buffer.from('fake video content for testing');

async function testHealthCheck() {
    console.log('Testing backend health check...');
    try {
        const response = await axios.get(`${API_BASE_URL}/`);
        console.log('✅ Backend is healthy:', response.data);
        return true;
    } catch (error) {
        console.log('❌ Backend health check failed:', error.message);
        return false;
    }
}

async function testCorrectionWorkflow() {
    console.log('\nTesting correction workflow...');
    
    try {
        // Create temporary files
        const videoPath = path.join(__dirname, 'temp_test_video.mp4');
        const subtitlePath = path.join(__dirname, 'temp_test_subtitle.srt');
        
        fs.writeFileSync(videoPath, TEST_VIDEO_CONTENT);
        fs.writeFileSync(subtitlePath, TEST_SRT_CONTENT);
        
        // Create FormData
        const form = new FormData();
        form.append('video', fs.createReadStream(videoPath), {
            filename: 'test_video.mp4',
            contentType: 'video/mp4'
        });
        form.append('subtitle', fs.createReadStream(subtitlePath), {
            filename: 'test_subtitle.srt',
            contentType: 'text/plain'
        });
        
        // Make request
        const response = await axios.post(`${API_BASE_URL}/process`, form, {
            headers: {
                ...form.getHeaders(),
            },
            responseType: 'arraybuffer',
            timeout: 30000
        });
        
        console.log('✅ Correction workflow successful!');
        console.log(`   Status: ${response.status}`);
        console.log(`   Content-Type: ${response.headers['content-type']}`);
        console.log(`   Content-Length: ${response.data.length} bytes`);
        
        // Clean up
        fs.unlinkSync(videoPath);
        fs.unlinkSync(subtitlePath);
        
        return true;
        
    } catch (error) {
        console.log('❌ Correction workflow failed:', error.message);
        if (error.response) {
            console.log(`   Status: ${error.response.status}`);
            console.log(`   Response: ${error.response.data.toString().substring(0, 200)}...`);
        }
        return false;
    }
}

async function testGenerationWorkflow() {
    console.log('\nTesting generation workflow...');
    
    try {
        // Create temporary video file
        const videoPath = path.join(__dirname, 'temp_test_video_gen.mp4');
        fs.writeFileSync(videoPath, TEST_VIDEO_CONTENT);
        
        // Create FormData
        const form = new FormData();
        form.append('video', fs.createReadStream(videoPath), {
            filename: 'test_video.mp4',
            contentType: 'video/mp4'
        });
        form.append('language', 'en');
        
        // Make request
        const response = await axios.post(`${API_BASE_URL}/process`, form, {
            headers: {
                ...form.getHeaders(),
            },
            responseType: 'arraybuffer',
            timeout: 30000
        });
        
        console.log('✅ Generation workflow successful!');
        console.log(`   Status: ${response.status}`);
        console.log(`   Content-Type: ${response.headers['content-type']}`);
        console.log(`   Content-Length: ${response.data.length} bytes`);
        
        // Clean up
        fs.unlinkSync(videoPath);
        
        return true;
        
    } catch (error) {
        console.log('❌ Generation workflow failed:', error.message);
        if (error.response) {
            console.log(`   Status: ${error.response.status}`);
            console.log(`   Response: ${error.response.data.toString().substring(0, 200)}...`);
        }
        return false;
    }
}

async function testCorsConfiguration() {
    console.log('\nTesting CORS configuration...');
    
    try {
        const response = await axios.options(`${API_BASE_URL}/process`, {
            headers: {
                'Origin': 'https://vscode-internal-33546-beta.beta01.cloud.kavia.ai:3000',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type'
            }
        });
        
        console.log('✅ CORS preflight successful!');
        console.log(`   Access-Control-Allow-Origin: ${response.headers['access-control-allow-origin']}`);
        console.log(`   Access-Control-Allow-Methods: ${response.headers['access-control-allow-methods']}`);
        
        return true;
        
    } catch (error) {
        console.log('❌ CORS test failed:', error.message);
        return false;
    }
}

async function runTests() {
    console.log('Frontend-Backend API Connectivity Test');
    console.log('=====================================\n');
    
    const results = {
        health: await testHealthCheck(),
        correction: await testCorrectionWorkflow(),
        generation: await testGenerationWorkflow(),
        cors: await testCorsConfiguration()
    };
    
    console.log('\n=====================================');
    console.log('Test Results Summary:');
    console.log(`Health Check: ${results.health ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Correction: ${results.correction ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Generation: ${results.generation ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`CORS Config: ${results.cors ? '✅ PASS' : '❌ FAIL'}`);
    
    const allPassed = Object.values(results).every(result => result);
    console.log(`\nOverall: ${allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED'}`);
    
    if (allPassed) {
        console.log('\n🎉 The correction workflow fix is working correctly!');
        console.log('The frontend should now be able to successfully process corrections.');
    } else {
        console.log('\n⚠️  Some issues remain. Check the failed tests above.');
    }
}

// Run tests
runTests().catch(console.error);
