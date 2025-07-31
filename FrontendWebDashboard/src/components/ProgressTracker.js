import React, { useState, useEffect } from 'react';
import { getJobStatus } from '../services/api';
import './ProgressTracker.css';

// PUBLIC_INTERFACE
/**
 * Progress tracker component for monitoring job status
 * @param {Object} props - Component props
 * @param {string} props.jobId - Job identifier to track
 * @param {Function} props.onComplete - Callback when job completes
 * @param {Function} props.onError - Callback when job fails
 */
const ProgressTracker = ({ jobId, onComplete, onError }) => {
  const [status, setStatus] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('Initializing...');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!jobId) return;

    const pollInterval = setInterval(async () => {
      try {
        const jobStatus = await getJobStatus(jobId);
        setStatus(jobStatus.status);
        setProgress(jobStatus.progress || 0);
        setMessage(jobStatus.message || 'Processing...');

        if (jobStatus.status === 'completed') {
          clearInterval(pollInterval);
          onComplete && onComplete(jobStatus);
        } else if (jobStatus.status === 'failed') {
          clearInterval(pollInterval);
          setError(jobStatus.error || 'Job failed');
          onError && onError(jobStatus.error);
        }
      } catch (err) {
        console.error('Error polling job status:', err);
        setError('Failed to get job status');
        clearInterval(pollInterval);
        onError && onError(err);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [jobId, onComplete, onError]);

  const getStatusIcon = () => {
    switch (status) {
      case 'completed':
        return '✓';
      case 'failed':
        return '✗';
      case 'processing':
        return '⟳';
      default:
        return '○';
    }
  };

  const getStatusClass = () => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'processing':
        return 'processing';
      default:
        return 'pending';
    }
  };

  if (error) {
    return (
      <div className="progress-tracker error">
        <div className="progress-header">
          <span className="progress-icon">✗</span>
          <span className="progress-title">Error</span>
        </div>
        <div className="progress-message">{error}</div>
      </div>
    );
  }

  return (
    <div className={`progress-tracker ${getStatusClass()}`}>
      <div className="progress-header">
        <span className="progress-icon">{getStatusIcon()}</span>
        <span className="progress-title">
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
        <span className="progress-percentage">{progress}%</span>
      </div>
      
      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${progress}%` }}
        />
      </div>
      
      <div className="progress-message">{message}</div>
    </div>
  );
};

export default ProgressTracker;
