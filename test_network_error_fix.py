#!/usr/bin/env python3
"""
Test script to verify network error fixes for large file uploads
"""

import requests
import os
import tempfile
import time
import json

BASE_URL = "http://localhost:8000"

def create_test_files():
    """Create test files of various sizes"""
    # Small subtitle file
    srt_content = """1
00:00:01,000 --> 00:00:05,000
This is a test subtitle for network error testing.

2
00:00:06,000 --> 00:00:10,000
Testing large file upload handling.

3
00:00:11,000 --> 00:00:15,000
Verifying async processing works correctly.
"""
    
    subtitle_file = tempfile.NamedTemporaryFile(suffix='.srt', delete=False)
    subtitle_file.write(srt_content.encode('utf-8'))
    subtitle_file.close()
    
    # Small video file (1MB)
    small_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    small_video.write(b'0' * (1024 * 1024))  # 1MB
    small_video.close()
    
    # Large video file (150MB to trigger async processing)
    large_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    large_video.write(b'0' * (150 * 1024 * 1024))  # 150MB
    large_video.close()
    
    return subtitle_file.name, small_video.name, large_video.name

def test_health_check():
    """Test health check endpoints"""
    print("Testing health check...")
    
    try:
        # Basic health check
        response = requests.get(f"{BASE_URL}/", timeout=10)
        print(f"Basic health: {response.status_code} - {response.json()}")
        
        # Detailed health check
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Detailed health: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"  Max file size: {health_data.get('max_file_size_mb', 'unknown')}MB")
            print(f"  Upload dir exists: {health_data.get('upload_dir_exists', False)}")
            
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    return True

def test_small_file_processing():
    """Test immediate processing of small files"""
    print("\nTesting small file processing...")
    
    subtitle_path, small_video_path, _ = create_test_files()
    
    try:
        # Test correction workflow
        with open(small_video_path, 'rb') as video_f, open(subtitle_path, 'rb') as subtitle_f:
            files = {
                'video': ('small_video.mp4', video_f, 'video/mp4'),
                'subtitle': ('test_subtitle.srt', subtitle_f, 'text/plain')
            }
            
            response = requests.post(f"{BASE_URL}/process", files=files, timeout=60)
            
            print(f"Small file correction - Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ Small file processing successful")
                print(f"Response size: {len(response.content)} bytes")
                return True
            else:
                print(f"❌ Small file processing failed: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Small file test error: {e}")
        return False
    finally:
        # Clean up
        for path in [subtitle_path, small_video_path]:
            try:
                os.unlink(path)
            except:
                pass

def test_large_file_processing():
    """Test async processing of large files"""
    print("\nTesting large file processing...")
    
    _, _, large_video_path = create_test_files()
    
    try:
        # Test generation workflow with large file
        with open(large_video_path, 'rb') as video_f:
            files = {'video': ('large_video.mp4', video_f, 'video/mp4')}
            data = {'language': 'en', 'async_processing': 'true'}
            
            response = requests.post(f"{BASE_URL}/process", files=files, data=data, timeout=120)
            
            print(f"Large file processing - Status: {response.status_code}")
            
            if response.status_code == 202:
                # Async processing started
                result = response.json()
                print("✅ Large file async processing started")
                print(f"Job ID: {result.get('job_id')}")
                print(f"Status URL: {result.get('check_status_url')}")
                
                # Test status checking
                job_id = result.get('job_id')
                if job_id:
                    return test_job_status(job_id)
                    
            elif response.status_code == 200:
                print("✅ Large file processed immediately")
                return True
            else:
                print(f"❌ Large file processing failed: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Large file test error: {e}")
        return False
    finally:
        # Clean up
        try:
            os.unlink(large_video_path)
        except:
            pass

def test_job_status(job_id):
    """Test job status tracking"""
    print(f"\nTesting job status for job {job_id}...")
    
    max_polls = 10
    poll_count = 0
    
    while poll_count < max_polls:
        try:
            response = requests.get(f"{BASE_URL}/jobs/{job_id}/status", timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                print(f"Job status: {status_data.get('status')} ({status_data.get('progress', 0)}%)")
                
                if status_data.get('status') == 'completed':
                    result_url = status_data.get('result_url')
                    if result_url:
                        print(f"✅ Job completed - Result: {result_url}")
                        return test_file_download(result_url)
                    else:
                        print("❌ Job completed but no result URL")
                        return False
                        
                elif status_data.get('status') == 'failed':
                    print("❌ Job failed")
                    return False
                    
            else:
                print(f"❌ Status check failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Status check error: {e}")
            return False
        
        poll_count += 1
        time.sleep(2)  # Wait 2 seconds between polls
    
    print("❌ Job status polling timed out")
    return False

def test_file_download(result_url):
    """Test downloading processed file"""
    print(f"\nTesting file download: {result_url}")
    
    try:
        response = requests.get(f"{BASE_URL}{result_url}", timeout=30)
        
        if response.status_code == 200:
            print(f"✅ File download successful - Size: {len(response.content)} bytes")
            print(f"Content-Type: {response.headers.get('content-type')}")
            return True
        else:
            print(f"❌ File download failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def test_error_conditions():
    """Test various error conditions"""
    print("\nTesting error conditions...")
    
    # Test unsupported file format
    try:
        unsupported_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        unsupported_file.write(b'not a video file')
        unsupported_file.close()
        
        with open(unsupported_file.name, 'rb') as f:
            files = {'video': ('test.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/process", files=files, timeout=30)
            
        print(f"Unsupported format test - Status: {response.status_code}")
        if response.status_code == 400:
            print("✅ Unsupported format properly rejected")
        else:
            print(f"❌ Expected 400, got {response.status_code}")
            
        os.unlink(unsupported_file.name)
        
    except Exception as e:
        print(f"❌ Error condition test failed: {e}")

def main():
    """Run all tests"""
    print("Network Error Fix Verification")
    print("=" * 50)
    
    # Test server availability
    if not test_health_check():
        print("❌ Server not available - start the backend first")
        return
    
    # Run tests
    tests = [
        ("Small File Processing", test_small_file_processing),
        ("Large File Processing", test_large_file_processing),
        ("Error Conditions", test_error_conditions),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\nOverall: {passed_count}/{total_count} tests passed")

if __name__ == "__main__":
    main()
