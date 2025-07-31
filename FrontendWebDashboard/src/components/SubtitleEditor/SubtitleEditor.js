import React, { useState, useRef, useEffect } from 'react';
import './SubtitleEditor.css';

// PUBLIC_INTERFACE
/**
 * SubtitleEditor - In-browser subtitle editor with video playback synchronization
 * Provides comprehensive subtitle editing capabilities with real-time video preview
 */
const SubtitleEditor = ({ 
  videoFile, 
  subtitleFile, 
  onSave, 
  onClose,
  initialSubtitles = null 
}) => {
  const [subtitles, setSubtitles] = useState([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedSubtitle, setSelectedSubtitle] = useState(null);
  const [editingSubtitle, setEditingSubtitle] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const videoRef = useRef(null);
  const subtitleListRef = useRef(null);

  // Initialize video and subtitles
  useEffect(() => {
    if (videoFile) {
      const url = URL.createObjectURL(videoFile);
      setVideoUrl(url);
      
      return () => {
        URL.revokeObjectURL(url);
      };
    }
  }, [videoFile]);

  useEffect(() => {
    if (initialSubtitles) {
      setSubtitles(initialSubtitles);
      setLoading(false);
    } else if (subtitleFile) {
      loadSubtitleFile();
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subtitleFile, initialSubtitles]);

  // PUBLIC_INTERFACE
  /**
   * Load and parse subtitle file
   */
  const loadSubtitleFile = async () => {
    try {
      setLoading(true);
      const text = await subtitleFile.text();
      const parsedSubtitles = parseSubtitles(text);
      setSubtitles(parsedSubtitles);
    } catch (err) {
      setError('Failed to load subtitle file');
      console.error('Error loading subtitle file:', err);
    } finally {
      setLoading(false);
    }
  };

  // PUBLIC_INTERFACE
  /**
   * Parse SRT subtitle format
   */
  const parseSubtitles = (text) => {
    const blocks = text.trim().split(/\n\s*\n/);
    const subtitles = [];

    blocks.forEach((block, index) => {
      const lines = block.trim().split('\n');
      if (lines.length >= 3) {
        const timeMatch = lines[1].match(/(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})/);
        if (timeMatch) {
          const startTime = timeToSeconds(timeMatch[1]);
          const endTime = timeToSeconds(timeMatch[2]);
          const text = lines.slice(2).join('\n');
          
          subtitles.push({
            id: index + 1,
            startTime,
            endTime,
            text,
            originalText: text
          });
        }
      }
    });

    return subtitles;
  };

  // PUBLIC_INTERFACE
  /**
   * Convert timestamp to seconds
   */
  const timeToSeconds = (timeStr) => {
    const [time, ms] = timeStr.split(',');
    const [hours, minutes, seconds] = time.split(':').map(Number);
    return hours * 3600 + minutes * 60 + seconds + parseInt(ms) / 1000;
  };

  // PUBLIC_INTERFACE
  /**
   * Convert seconds to timestamp string
   */
  const secondsToTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
  };

  // Video control functions
  const handlePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const time = videoRef.current.currentTime;
      setCurrentTime(time);
      
      // Find current subtitle
      const current = subtitles.find(sub => 
        time >= sub.startTime && time <= sub.endTime
      );
      
      if (current && current.id !== selectedSubtitle?.id) {
        setSelectedSubtitle(current);
        scrollToSubtitle(current.id);
      }
    }
  };

  const seekToTime = (time) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const scrollToSubtitle = (subtitleId) => {
    const element = document.getElementById(`subtitle-${subtitleId}`);
    if (element && subtitleListRef.current) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  // Subtitle editing functions
  const handleSubtitleClick = (subtitle) => {
    setSelectedSubtitle(subtitle);
    seekToTime(subtitle.startTime);
  };

  const handleEditSubtitle = (subtitle) => {
    setEditingSubtitle({ ...subtitle });
  };

  const handleSaveEdit = () => {
    if (editingSubtitle) {
      const updatedSubtitles = subtitles.map(sub =>
        sub.id === editingSubtitle.id ? editingSubtitle : sub
      );
      setSubtitles(updatedSubtitles);
      setEditingSubtitle(null);
    }
  };

  const handleCancelEdit = () => {
    setEditingSubtitle(null);
  };

  const handleDeleteSubtitle = (subtitleId) => {
    if (window.confirm('Are you sure you want to delete this subtitle?')) {
      const updatedSubtitles = subtitles.filter(sub => sub.id !== subtitleId);
      setSubtitles(updatedSubtitles);
      if (selectedSubtitle?.id === subtitleId) {
        setSelectedSubtitle(null);
      }
    }
  };

  const handleAddSubtitle = () => {
    const newId = Math.max(...subtitles.map(s => s.id), 0) + 1;
    const newSubtitle = {
      id: newId,
      startTime: currentTime,
      endTime: currentTime + 3,
      text: 'New subtitle',
      originalText: 'New subtitle'
    };
    
    const updatedSubtitles = [...subtitles, newSubtitle].sort((a, b) => a.startTime - b.startTime);
    setSubtitles(updatedSubtitles);
    setEditingSubtitle(newSubtitle);
  };

  // Export subtitle in SRT format
  const exportSubtitles = () => {
    const srtContent = subtitles
      .sort((a, b) => a.startTime - b.startTime)
      .map((sub, index) => {
        return `${index + 1}\n${secondsToTime(sub.startTime)} --> ${secondsToTime(sub.endTime)}\n${sub.text}\n`;
      }).join('\n');
    
    return srtContent;
  };

  const handleSave = () => {
    const exportedContent = exportSubtitles();
    onSave(exportedContent);
  };

  if (loading) {
    return (
      <div className="subtitle-editor-loading">
        <div className="loading-spinner"></div>
        <p>Loading subtitle editor...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="subtitle-editor-error">
        <p>{error}</p>
        <button onClick={onClose}>Close</button>
      </div>
    );
  }

  return (
    <div className="subtitle-editor">
      <div className="editor-header">
        <h2>Subtitle Editor</h2>
        <div className="editor-actions">
          <button className="btn secondary" onClick={handleAddSubtitle}>
            <span>➕</span> Add Subtitle
          </button>
          <button className="btn primary" onClick={handleSave}>
            <span>💾</span> Save Changes
          </button>
          <button className="btn secondary" onClick={onClose}>
            <span>✕</span> Close
          </button>
        </div>
      </div>

      <div className="editor-content">
        <div className="video-panel">
          <div className="video-container">
            {videoUrl ? (
              <video
                ref={videoRef}
                src={videoUrl}
                onTimeUpdate={handleTimeUpdate}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                controls
                className="video-player"
              />
            ) : (
              <div className="video-placeholder">
                <p>No video file provided</p>
              </div>
            )}
          </div>

          <div className="video-controls">
            <button onClick={handlePlayPause} className="play-pause-btn">
              {isPlaying ? '⏸️' : '▶️'}
            </button>
            <div className="time-display">
              {secondsToTime(currentTime)}
            </div>
            {selectedSubtitle && (
              <div className="current-subtitle-display">
                {selectedSubtitle.text}
              </div>
            )}
          </div>
        </div>

        <div className="subtitle-panel">
          <div className="subtitle-list" ref={subtitleListRef}>
            {subtitles.map((subtitle) => (
              <div
                key={subtitle.id}
                id={`subtitle-${subtitle.id}`}
                className={`subtitle-item ${selectedSubtitle?.id === subtitle.id ? 'selected' : ''} ${
                  currentTime >= subtitle.startTime && currentTime <= subtitle.endTime ? 'current' : ''
                }`}
                onClick={() => handleSubtitleClick(subtitle)}
              >
                <div className="subtitle-header">
                  <span className="subtitle-index">#{subtitle.id}</span>
                  <span className="subtitle-timing">
                    {secondsToTime(subtitle.startTime)} → {secondsToTime(subtitle.endTime)}
                  </span>
                  <div className="subtitle-actions">
                    <button
                      className="btn-icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditSubtitle(subtitle);
                      }}
                      title="Edit subtitle"
                    >
                      ✏️
                    </button>
                    <button
                      className="btn-icon delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSubtitle(subtitle.id);
                      }}
                      title="Delete subtitle"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
                <div className="subtitle-text">
                  {subtitle.text}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      {editingSubtitle && (
        <div className="edit-modal-overlay">
          <div className="edit-modal">
            <h3>Edit Subtitle #{editingSubtitle.id}</h3>
            <div className="edit-form">
              <div className="timing-inputs">
                <div className="time-input-group">
                  <label>Start Time</label>
                  <input
                    type="text"
                    value={secondsToTime(editingSubtitle.startTime)}
                    onChange={(e) => {
                      const seconds = timeToSeconds(e.target.value);
                      setEditingSubtitle({
                        ...editingSubtitle,
                        startTime: seconds
                      });
                    }}
                  />
                </div>
                <div className="time-input-group">
                  <label>End Time</label>
                  <input
                    type="text"
                    value={secondsToTime(editingSubtitle.endTime)}
                    onChange={(e) => {
                      const seconds = timeToSeconds(e.target.value);
                      setEditingSubtitle({
                        ...editingSubtitle,
                        endTime: seconds
                      });
                    }}
                  />
                </div>
              </div>
              <div className="text-input-group">
                <label>Subtitle Text</label>
                <textarea
                  value={editingSubtitle.text}
                  onChange={(e) => setEditingSubtitle({
                    ...editingSubtitle,
                    text: e.target.value
                  })}
                  rows={3}
                />
              </div>
              <div className="modal-actions">
                <button className="btn secondary" onClick={handleCancelEdit}>
                  Cancel
                </button>
                <button className="btn primary" onClick={handleSaveEdit}>
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SubtitleEditor;
