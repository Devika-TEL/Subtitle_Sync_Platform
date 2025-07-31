#!/usr/bin/env python3
"""
Test script to verify the correction workflow fix
"""

import requests
import os
import tempfile

# Test data
TEST_SRT_CONTENT = """1
00:00:01,000 --> 00:00:05,000
This is a test subtitle for correction.

2
00:00:06,000 --> 00:00:10,000
This subtitle will be processed by the backend.

3
00:00:11,000 --> 00:00:15,000
Testing the synchronization correction feature.
"""

TEST_VIDEO_CONTENT = b"fake video content for testing"

def test_correction_endpoint():
    """Test the /process endpoint with correction workflow"""
    print("Testing correction workflow...")
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as subtitle_file:
        subtitle_file.write(TEST_SRT_CONTENT.encode('utf-8'))
        subtitle_path = subtitle_file.name
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
        video_file.write(TEST_VIDEO_CONTENT)
        video_path = video_file.name
    
    try:
        # Prepare files for upload
        with open(video_path, 'rb') as video_f, open(subtitle_path, 'rb') as subtitle_f:
            files = {
                'video': ('test_video.mp4', video_f, 'video/mp4'),
                'subtitle': ('test_subtitle.srt', subtitle_f, 'text/plain')
            }
            
            # Make request to backend - use environment variable or default URL
            api_url = os.environ.get('API_BASE_URL', 'https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001')
            response = requests.post(
                f'{api_url}/process',
                files=files,
                timeout=30
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ Correction endpoint working!")
                print(f"Response content type: {response.headers.get('content-type', 'unknown')}")
                if 'application/octet-stream' in response.headers.get('content-type', ''):
                    print(f"✅ Received corrected file: {len(response.content)} bytes")
                else:
                    print(f"Response content: {response.text[:200]}...")
            else:
                print(f"❌ Request failed: {response.text}")
                
    except requests.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Test error: {e}")
    finally:
        # Clean up
        try:
            os.unlink(subtitle_path)
            os.unlink(video_path)
        except:
            pass

def test_generation_endpoint():
    """Test the /process endpoint with generation workflow"""
    print("\nTesting generation workflow...")
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_file:
        video_file.write(TEST_VIDEO_CONTENT)
        video_path = video_file.name
    
    try:
        with open(video_path, 'rb') as video_f:
            files = {
                'video': ('test_video.mp4', video_f, 'video/mp4')
            }
            data = {
                'language': 'en'
            }
            
            api_url = os.environ.get('API_BASE_URL', 'https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001')
            response = requests.post(
                f'{api_url}/process',
                files=files,
                data=data,
                timeout=30
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Generation endpoint working!")
                print(f"Response content type: {response.headers.get('content-type', 'unknown')}")
                if 'application/octet-stream' in response.headers.get('content-type', ''):
                    print(f"✅ Received generated file: {len(response.content)} bytes")
                else:
                    print(f"Response content: {response.text[:200]}...")
            else:
                print(f"❌ Request failed: {response.text}")
                
    except requests.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Test error: {e}")
    finally:
        try:
            os.unlink(video_path)
        except:
            pass

def test_health_check():
    """Test basic health check"""
    print("\nTesting health check...")
    
    try:
        api_url = os.environ.get('API_BASE_URL', 'https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001')
        response = requests.get(f'{api_url}/', timeout=5)
        if response.status_code == 200:
            print("✅ Backend is healthy")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")

if __name__ == "__main__":
    print("Testing Correction Workflow Fix")
    print("=" * 40)
    
    test_health_check()
    test_correction_endpoint()
    test_generation_endpoint()
    
    print("\n" + "=" * 40)
    print("Test completed!")
