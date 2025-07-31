#!/usr/bin/env node

const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');

// Test data
const TEST_SRT_CONTENT = `1
00:00:01,000 --> 00:00:05,000
This is a test subtitle for correction.

2
00:00:06,000 --> 00:00:10,000
This subtitle will be processed by the backend.

3
00:00:11,000 --> 00:00:15,000
Testing the synchronization correction feature.
`;

const TEST_VIDEO_CONTENT = Buffer.from('fake video content for testing');

async function testFrontendAPI() {
    console.log('Testing Frontend API Call Simulation...');
    console.log('='.repeat(50));

    // Create temporary files
    const tempDir = '/tmp';
    const videoPath = path.join(tempDir, 'test_video.mp4');
    const subtitlePath = path.join(tempDir, 'test_subtitle.srt');

    try {
        // Write test files
        fs.writeFileSync(videoPath, TEST_VIDEO_CONTENT);
        fs.writeFileSync(subtitlePath, TEST_SRT_CONTENT);

        // Create axios instance matching frontend config
        const api = axios.create({
            baseURL: process.env.API_BASE_URL || 'https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001',
            timeout: 300000, // 5 minutes
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Add request interceptor like frontend
        api.interceptors.request.use(
            (config) => {
                console.log(`Making request to: ${config.baseURL}${config.url}`);
                console.log(`Request headers:`, config.headers);
                return config;
            },
            (error) => {
                console.error('Request interceptor error:', error);
                return Promise.reject(error);
            }
        );

        // Add response interceptor like frontend
        api.interceptors.response.use(
            (response) => {
                console.log(`Response status: ${response.status}`);
                console.log(`Response headers:`, response.headers);
                return response;
            },
            (error) => {
                console.error('Response interceptor error:', error.response?.data || error.message);
                return Promise.reject(error);
            }
        );

        // Simulate the correctSubtitles function call
        console.log('\n--- Testing Correction Workflow ---');
        
        const formData = new FormData();
        formData.append('video', fs.createReadStream(videoPath), {
            filename: 'test_video.mp4',
            contentType: 'video/mp4'
        });
        formData.append('subtitle', fs.createReadStream(subtitlePath), {
            filename: 'test_subtitle.srt',
            contentType: 'text/plain'
        });

        try {
            const response = await api.post('/process', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                    ...formData.getHeaders()
                },
                responseType: 'blob', // For file download
            });

            console.log('✅ Correction request successful!');
            console.log(`Response type: ${typeof response.data}`);
            console.log(`Response size: ${response.data.length || 'unknown'} bytes`);
            
            // Check if it's a Blob-like response
            if (response.data instanceof Buffer) {
                console.log('✅ Received file data as Buffer');
                console.log(`File content preview: ${response.data.toString('utf8').substring(0, 100)}...`);
            } else {
                console.log('❌ Response is not file data');
                console.log(`Response data: ${response.data}`);
            }

        } catch (error) {
            console.error('❌ Correction request failed:');
            console.error(`Error type: ${error.constructor.name}`);
            console.error(`Error message: ${error.message}`);
            
            if (error.response) {
                console.error(`HTTP Status: ${error.response.status}`);
                console.error(`Response data: ${error.response.data}`);
                console.error(`Response headers:`, error.response.headers);
            } else if (error.request) {
                console.error('No response received');
                console.error(`Request config:`, error.config);
            }
            
            // Test the error handling path from frontend
            const frontendError = error.response?.data?.message || 'Failed to process correction. Please try again.';
            console.error(`Frontend would show: "${frontendError}"`);
        }

        // Test health check
        console.log('\n--- Testing Health Check ---');
        try {
            const healthResponse = await api.get('/');
            console.log('✅ Health check successful:', healthResponse.data);
        } catch (error) {
            console.error('❌ Health check failed:', error.message);
        }

    } catch (error) {
        console.error('❌ Test setup error:', error.message);
    } finally {
        // Cleanup
        try {
            fs.unlinkSync(videoPath);
            fs.unlinkSync(subtitlePath);
        } catch (e) {
            // Ignore cleanup errors
        }
    }
}

// Check if we're running this directly
if (require.main === module) {
    testFrontendAPI().then(() => {
        console.log('\n' + '='.repeat(50));
        console.log('Test completed!');
        process.exit(0);
    }).catch((error) => {
        console.error('Test failed:', error);
        process.exit(1);
    });
}

module.exports = { testFrontendAPI };
