// PUBLIC_INTERFACE
/**
 * Create and trigger download of a blob
 * @param {Blob} blob - File blob to download
 * @param {string} filename - Name for downloaded file
 */
export const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

// PUBLIC_INTERFACE
/**
 * Validate file type and size
 * @param {File} file - File to validate
 * @param {Array} allowedTypes - Array of allowed MIME types
 * @param {number} maxSize - Maximum file size in bytes
 * @returns {Object} - Validation result
 */
export const validateFile = (file, allowedTypes, maxSize = 100 * 1024 * 1024) => {
  const errors = [];
  
  if (!file) {
    errors.push('No file selected');
    return { isValid: false, errors };
  }
  
  // Check file type - be more flexible with subtitle files
  if (allowedTypes && allowedTypes.length > 0) {
    const isValidMimeType = allowedTypes.includes(file.type);
    const isSubtitleFile = allowedTypes === SUBTITLE_TYPES;
    
    if (!isValidMimeType) {
      if (isSubtitleFile) {
        // For subtitle files, also check file extension as browsers often report .srt as text/plain
        const fileExtension = getFileExtension(file.name).toLowerCase();
        const allowedExtensions = ['srt', 'vtt', 'ass', 'ssa', 'scc', 'sub', 'smi', 'sami'];
        
        if (!allowedExtensions.includes(fileExtension)) {
          errors.push(`Invalid file type. Supported subtitle formats: SRT, VTT, ASS, SSA, SCC, SUB, SMI, SAMI`);
        }
      } else {
        errors.push(`Invalid file type. Allowed types: ${allowedTypes.join(', ')}`);
      }
    } else if (isSubtitleFile) {
      // Even if MIME type matches, still validate extension for subtitle files to prevent false positives
      const fileExtension = getFileExtension(file.name).toLowerCase();
      const allowedExtensions = ['srt', 'vtt', 'ass', 'ssa', 'scc', 'sub', 'smi', 'sami'];
      
      if (!allowedExtensions.includes(fileExtension)) {
        errors.push(`Invalid file type. Supported subtitle formats: SRT, VTT, ASS, SSA, SCC, SUB, SMI, SAMI`);
      }
    }
  }
  
  if (file.size > maxSize) {
    const maxSizeMB = Math.round(maxSize / (1024 * 1024));
    errors.push(`File size too large. Maximum size: ${maxSizeMB}MB`);
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

// PUBLIC_INTERFACE
/**
 * Format file size for display
 * @param {number} bytes - File size in bytes
 * @returns {string} - Formatted file size
 */
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// PUBLIC_INTERFACE
/**
 * Get file extension from filename
 * @param {string} filename - File name
 * @returns {string} - File extension
 */
export const getFileExtension = (filename) => {
  return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2);
};

// Supported video formats
export const VIDEO_TYPES = [
  'video/mp4',
  'video/avi', 
  'video/mov',
  'video/wmv',
  'video/flv',
  'video/webm',
  'video/mkv'
];

// Supported subtitle formats
export const SUBTITLE_TYPES = [
  'text/plain', // .srt, .sub files often come as text/plain
  'application/x-subrip', // .srt
  'text/vtt', // .vtt
  'application/x-ass', // .ass
  'text/x-ssa', // .ssa
  'text/x-scc', // .scc
  'application/x-sub', // .sub
  'application/x-microdvd', // .sub
  'application/x-subviewer', // .sub
  'application/x-mpsub', // .sub
  'application/x-sami' // .smi, .sami
];

// Supported subtitle file extensions (for accept attribute)
export const SUBTITLE_EXTENSIONS = '.srt,.vtt,.ass,.ssa,.scc,.sub,.smi,.sami';
