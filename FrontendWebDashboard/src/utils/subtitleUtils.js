// PUBLIC_INTERFACE
/**
 * Subtitle processing utilities for format detection, parsing, and validation
 * Supports multiple subtitle formats including SRT, VTT, ASS, SSA, and more
 */

// Supported subtitle formats
export const SUBTITLE_FORMATS = {
  SRT: 'srt',
  VTT: 'vtt',
  ASS: 'ass',
  SSA: 'ssa',
  SCC: 'scc',
  SUB: 'sub',
  SMI: 'smi',
  SAMI: 'sami'
};

// PUBLIC_INTERFACE
/**
 * Detect subtitle format from file content
 * @param {string} content - Subtitle file content
 * @returns {string} - Detected format or 'unknown'
 */
export const detectSubtitleFormat = (content) => {
  const contentLower = content.toLowerCase().trim();
  
  // WebVTT detection
  if (contentLower.startsWith('webvtt') || contentLower.includes('webvtt')) {
    return SUBTITLE_FORMATS.VTT;
  }
  
  // SRT detection - look for timestamp pattern
  if (content.match(/\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}/)) {
    return SUBTITLE_FORMATS.SRT;
  }
  
  // ASS/SSA detection
  if (contentLower.includes('[script info]') || contentLower.includes('[v4+ styles]')) {
    return contentLower.includes('scripttype: v4.00+') ? SUBTITLE_FORMATS.ASS : SUBTITLE_FORMATS.SSA;
  }
  
  // SCC detection
  if (content.match(/scenarist_scc v\d+\.\d+/i) || content.match(/\d{2}:\d{2}:\d{2}:\d{2}/)) {
    return SUBTITLE_FORMATS.SCC;
  }
  
  // SAMI detection
  if (contentLower.includes('<sami>') || contentLower.includes('<sync start=')) {
    return SUBTITLE_FORMATS.SMI;
  }
  
  // SUB detection (MicroDVD)
  if (content.match(/\{\d+\}\{\d+\}/)) {
    return SUBTITLE_FORMATS.SUB;
  }
  
  return 'unknown';
};

// PUBLIC_INTERFACE
/**
 * Parse SRT subtitle content into structured data
 * @param {string} content - SRT content
 * @returns {Array} - Array of subtitle objects
 */
export const parseSRT = (content) => {
  const blocks = content.trim().split(/\n\s*\n/);
  const subtitles = [];

  blocks.forEach((block, index) => {
    const lines = block.trim().split('\n');
    if (lines.length >= 3) {
      const sequenceMatch = lines[0].match(/^\d+$/);
      const timeMatch = lines[1].match(/(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})/);
      
      if (sequenceMatch && timeMatch) {
        const sequence = parseInt(lines[0]);
        const startTime = timeToSeconds(timeMatch[1]);
        const endTime = timeToSeconds(timeMatch[2]);
        const text = lines.slice(2).join('\n').trim();
        
        if (text) {
          subtitles.push({
            id: sequence,
            sequence,
            startTime,
            endTime,
            duration: endTime - startTime,
            text,
            rawText: text,
            wordCount: text.split(/\s+/).length,
            characterCount: text.length
          });
        }
      }
    }
  });

  return subtitles.sort((a, b) => a.startTime - b.startTime);
};

// PUBLIC_INTERFACE
/**
 * Parse WebVTT subtitle content
 * @param {string} content - WebVTT content
 * @returns {Array} - Array of subtitle objects
 */
export const parseVTT = (content) => {
  const lines = content.split('\n');
  const subtitles = [];
  let currentSubtitle = null;
  let sequence = 1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    // Skip WEBVTT header and notes
    if (line.startsWith('WEBVTT') || line.startsWith('NOTE')) {
      continue;
    }
    
    // Time pattern for WebVTT
    const timeMatch = line.match(/(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})/);
    
    if (timeMatch) {
      if (currentSubtitle) {
        subtitles.push(currentSubtitle);
      }
      
      const startTime = vttTimeToSeconds(timeMatch[1]);
      const endTime = vttTimeToSeconds(timeMatch[2]);
      
      currentSubtitle = {
        id: sequence++,
        sequence: sequence - 1,
        startTime,
        endTime,
        duration: endTime - startTime,
        text: '',
        rawText: '',
        wordCount: 0,
        characterCount: 0
      };
    } else if (currentSubtitle && line) {
      // Add text line to current subtitle
      if (currentSubtitle.text) {
        currentSubtitle.text += '\n' + line;
      } else {
        currentSubtitle.text = line;
      }
      currentSubtitle.rawText = currentSubtitle.text;
      currentSubtitle.wordCount = currentSubtitle.text.split(/\s+/).length;
      currentSubtitle.characterCount = currentSubtitle.text.length;
    } else if (!line && currentSubtitle) {
      // Empty line indicates end of subtitle
      subtitles.push(currentSubtitle);
      currentSubtitle = null;
    }
  }
  
  // Add last subtitle if exists
  if (currentSubtitle) {
    subtitles.push(currentSubtitle);
  }

  return subtitles.sort((a, b) => a.startTime - b.startTime);
};

// PUBLIC_INTERFACE
/**
 * Convert subtitle array to SRT format
 * @param {Array} subtitles - Array of subtitle objects
 * @returns {string} - SRT formatted string
 */
export const toSRT = (subtitles) => {
  return subtitles
    .sort((a, b) => a.startTime - b.startTime)
    .map((subtitle, index) => {
      const sequence = index + 1;
      const startTime = secondsToSRTTime(subtitle.startTime);
      const endTime = secondsToSRTTime(subtitle.endTime);
      return `${sequence}\n${startTime} --> ${endTime}\n${subtitle.text}\n`;
    }).join('\n');
};

// PUBLIC_INTERFACE
/**
 * Convert subtitle array to WebVTT format
 * @param {Array} subtitles - Array of subtitle objects
 * @returns {string} - WebVTT formatted string
 */
export const toVTT = (subtitles) => {
  let vtt = 'WEBVTT\n\n';
  
  subtitles
    .sort((a, b) => a.startTime - b.startTime)
    .forEach((subtitle) => {
      const startTime = secondsToVTTTime(subtitle.startTime);
      const endTime = secondsToVTTTime(subtitle.endTime);
      vtt += `${startTime} --> ${endTime}\n${subtitle.text}\n\n`;
    });
  
  return vtt;
};

// PUBLIC_INTERFACE
/**
 * Validate subtitle content and structure
 * @param {Array} subtitles - Array of subtitle objects
 * @returns {Object} - Validation result with issues and recommendations
 */
export const validateSubtitles = (subtitles) => {
  const issues = [];
  const warnings = [];
  const recommendations = [];
  let totalDuration = 0;
  let totalWords = 0;
  let totalCharacters = 0;

  // Check if subtitles exist
  if (!subtitles || subtitles.length === 0) {
    issues.push('No subtitles found');
    return { isValid: false, issues, warnings, recommendations, stats: {} };
  }

  subtitles.forEach((subtitle, index) => {
    const { id, startTime, endTime, text, duration } = subtitle;
    
    // Basic structure validation
    if (typeof startTime !== 'number' || startTime < 0) {
      issues.push(`Subtitle ${id}: Invalid start time`);
    }
    
    if (typeof endTime !== 'number' || endTime <= startTime) {
      issues.push(`Subtitle ${id}: Invalid end time`);
    }
    
    if (!text || text.trim().length === 0) {
      issues.push(`Subtitle ${id}: Empty text content`);
    }
    
    // Duration validation
    if (duration < 0.5) {
      warnings.push(`Subtitle ${id}: Very short duration (${duration.toFixed(1)}s)`);
    } else if (duration > 10) {
      warnings.push(`Subtitle ${id}: Very long duration (${duration.toFixed(1)}s)`);
    }
    
    // Text length validation
    const textLength = text ? text.length : 0;
    if (textLength > 120) {
      warnings.push(`Subtitle ${id}: Text too long (${textLength} characters)`);
    }
    
    // Reading speed validation (approximate)
    const words = text ? text.split(/\s+/).length : 0;
    const readingSpeed = words / duration * 60; // WPM
    
    if (readingSpeed > 200) {
      warnings.push(`Subtitle ${id}: Reading speed too fast (${readingSpeed.toFixed(0)} WPM)`);
    }
    
    // Overlap detection
    if (index > 0) {
      const prevSubtitle = subtitles[index - 1];
      if (startTime < prevSubtitle.endTime) {
        issues.push(`Subtitle ${id}: Overlaps with previous subtitle`);
      }
      
      // Gap detection
      const gap = startTime - prevSubtitle.endTime;
      if (gap > 5) {
        warnings.push(`Subtitle ${id}: Large gap (${gap.toFixed(1)}s) from previous subtitle`);
      }
    }
    
    // Accumulate stats
    totalDuration += duration;
    totalWords += words;
    totalCharacters += textLength;
  });

  // Generate recommendations
  const avgReadingSpeed = (totalWords / totalDuration) * 60;
  if (avgReadingSpeed > 180) {
    recommendations.push('Consider reducing text density or extending display times');
  }
  
  if (subtitles.length > 500) {
    recommendations.push('Large subtitle file - consider splitting for better performance');
  }
  
  const avgCharactersPerSubtitle = totalCharacters / subtitles.length;
  if (avgCharactersPerSubtitle > 80) {
    recommendations.push('Consider shorter subtitle text for better readability');
  }

  const stats = {
    totalSubtitles: subtitles.length,
    totalDuration: totalDuration,
    totalWords,
    totalCharacters,
    averageReadingSpeed: avgReadingSpeed,
    averageDuration: totalDuration / subtitles.length,
    averageCharactersPerSubtitle: avgCharactersPerSubtitle
  };

  return {
    isValid: issues.length === 0,
    issues,
    warnings,
    recommendations,
    stats
  };
};

// PUBLIC_INTERFACE
/**
 * Convert time string to seconds (SRT format: HH:MM:SS,mmm)
 * @param {string} timeStr - Time string
 * @returns {number} - Time in seconds
 */
export const timeToSeconds = (timeStr) => {
  const [time, ms] = timeStr.split(',');
  const [hours, minutes, seconds] = time.split(':').map(Number);
  return hours * 3600 + minutes * 60 + seconds + (parseInt(ms || 0) / 1000);
};

// PUBLIC_INTERFACE
/**
 * Convert VTT time string to seconds (HH:MM:SS.mmm)
 * @param {string} timeStr - VTT time string
 * @returns {number} - Time in seconds
 */
export const vttTimeToSeconds = (timeStr) => {
  const [time, ms] = timeStr.split('.');
  const [hours, minutes, seconds] = time.split(':').map(Number);
  return hours * 3600 + minutes * 60 + seconds + (parseInt(ms || 0) / 1000);
};

// PUBLIC_INTERFACE
/**
 * Convert seconds to SRT time format (HH:MM:SS,mmm)
 * @param {number} seconds - Time in seconds
 * @returns {string} - SRT formatted time string
 */
export const secondsToSRTTime = (seconds) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
};

// PUBLIC_INTERFACE
/**
 * Convert seconds to VTT time format (HH:MM:SS.mmm)
 * @param {number} seconds - Time in seconds
 * @returns {string} - VTT formatted time string
 */
export const secondsToVTTTime = (seconds) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
};

// PUBLIC_INTERFACE
/**
 * Auto-correct common subtitle issues
 * @param {Array} subtitles - Array of subtitle objects
 * @returns {Array} - Corrected subtitle array
 */
export const autoCorrectSubtitles = (subtitles) => {
  return subtitles.map((subtitle, index) => {
    let correctedText = subtitle.text;
    
    // Fix common formatting issues
    correctedText = correctedText
      .replace(/\s+/g, ' ') // Multiple spaces to single space
      .replace(/\s*\n\s*/g, '\n') // Clean line breaks
      .trim();
    
    // Fix duration issues
    let { startTime, endTime } = subtitle;
    const minDuration = 0.5;
    const maxDuration = 8;
    
    if (endTime - startTime < minDuration) {
      endTime = startTime + minDuration;
    } else if (endTime - startTime > maxDuration) {
      endTime = startTime + maxDuration;
    }
    
    // Fix overlaps with next subtitle
    if (index < subtitles.length - 1) {
      const nextSubtitle = subtitles[index + 1];
      if (endTime > nextSubtitle.startTime) {
        endTime = nextSubtitle.startTime - 0.1;
      }
    }
    
    return {
      ...subtitle,
      text: correctedText,
      endTime,
      duration: endTime - startTime,
      wordCount: correctedText.split(/\s+/).length,
      characterCount: correctedText.length
    };
  });
};

// PUBLIC_INTERFACE
/**
 * Merge subtitle lines that are too short
 * @param {Array} subtitles - Array of subtitle objects
 * @param {number} minDuration - Minimum duration in seconds
 * @returns {Array} - Merged subtitle array
 */
export const mergeShortSubtitles = (subtitles, minDuration = 1.0) => {
  const merged = [];
  let currentGroup = null;
  
  subtitles.forEach((subtitle) => {
    if (subtitle.duration < minDuration && currentGroup) {
      // Merge with current group
      currentGroup.text += ' ' + subtitle.text;
      currentGroup.endTime = subtitle.endTime;
      currentGroup.duration = currentGroup.endTime - currentGroup.startTime;
      currentGroup.wordCount += subtitle.wordCount;
      currentGroup.characterCount += subtitle.characterCount;
    } else if (subtitle.duration < minDuration) {
      // Start new group
      currentGroup = { ...subtitle };
    } else {
      // Add previous group if exists
      if (currentGroup) {
        merged.push(currentGroup);
        currentGroup = null;
      }
      // Add current subtitle
      merged.push(subtitle);
    }
  });
  
  // Add final group if exists
  if (currentGroup) {
    merged.push(currentGroup);
  }
  
  return merged;
};

export default {
  SUBTITLE_FORMATS,
  detectSubtitleFormat,
  parseSRT,
  parseVTT,
  toSRT,
  toVTT,
  validateSubtitles,
  timeToSeconds,
  vttTimeToSeconds,
  secondsToSRTTime,
  secondsToVTTTime,
  autoCorrectSubtitles,
  mergeShortSubtitles
};
