"""
Subtitle Correction Module

This module provides comprehensive subtitle processing and correction functionality
for OTT platform compliance and quality assurance.

Dependencies:
- pysrt: For SRT file handling
- langdetect: For language detection
- spacy: For NLP tasks
- textblob: For spell checking
"""

import os
import re
from typing import Optional, Tuple, List, Dict
from enum import Enum
import pysrt
from langdetect import detect
from textblob import TextBlob
import spacy
from pathlib import Path

# Load spacy model for text analysis
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Download if not available
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

class SubtitleFormat(Enum):
    """Supported subtitle formats"""
    SRT = "srt"
    VTT = "vtt"
    SSA = "ssa"
    ASS = "ass"

class OTTStandards:
    """OTT platform compliance standards"""
    MAX_CHARS_PER_LINE = 42
    MAX_LINES_PER_SUBTITLE = 2
    MIN_DURATION_MS = 700  # minimum duration in milliseconds
    MAX_DURATION_MS = 7000  # maximum duration in milliseconds
    MAX_READING_SPEED_CPS = 20  # characters per second
    MIN_GAP_MS = 200  # minimum gap between subtitles

class SubtitleCorrector:
    """
    # PUBLIC_INTERFACE
    Main class for subtitle correction and validation
    """
    
    def __init__(self):
        self.current_format: Optional[SubtitleFormat] = None
        self.subtitles = None
        self.video_frame_rate: float = 23.976  # default frame rate
        
    def detect_format(self, file_path: str) -> SubtitleFormat:
        """
        # PUBLIC_INTERFACE
        Automatically detect subtitle format from file extension and content
        
        Args:
            file_path: Path to the subtitle file
            
        Returns:
            SubtitleFormat: Detected subtitle format
        """
        ext = Path(file_path).suffix.lower()[1:]
        try:
            return SubtitleFormat(ext)
        except ValueError:
            # Default to SRT if format cannot be determined
            return SubtitleFormat.SRT
            
    def load_subtitles(self, file_path: str) -> bool:
        """
        # PUBLIC_INTERFACE
        Load subtitles from file
        
        Args:
            file_path: Path to the subtitle file
            
        Returns:
            bool: True if loading successful
        """
        self.current_format = self.detect_format(file_path)
        try:
            if self.current_format == SubtitleFormat.SRT:
                self.subtitles = pysrt.open(file_path)
                return True
            # Add support for other formats here
            return False
        except Exception as e:
            print(f"Error loading subtitles: {str(e)}")
            return False
            
    def set_video_frame_rate(self, frame_rate: float):
        """
        # PUBLIC_INTERFACE
        Set video frame rate for timing calculations
        
        Args:
            frame_rate: Frame rate in fps
        """
        self.video_frame_rate = frame_rate
        
    def check_reading_speed(self, text: str, duration_ms: int) -> bool:
        """
        Check if subtitle reading speed is within acceptable limits
        
        Args:
            text: Subtitle text
            duration_ms: Duration in milliseconds
            
        Returns:
            bool: True if reading speed is acceptable
        """
        char_count = len(text.replace('\n', ''))
        reading_speed = (char_count * 1000) / duration_ms
        return reading_speed <= OTTStandards.MAX_READING_SPEED_CPS
        
    def check_line_length(self, text: str) -> bool:
        """
        Check if subtitle lines meet character count requirements
        
        Args:
            text: Subtitle text
            
        Returns:
            bool: True if line lengths are acceptable
        """
        lines = text.split('\n')
        return all(len(line) <= OTTStandards.MAX_CHARS_PER_LINE for line in lines)
        
    def check_line_count(self, text: str) -> bool:
        """
        Check if number of subtitle lines is acceptable
        
        Args:
            text: Subtitle text
            
        Returns:
            bool: True if line count is acceptable
        """
        return len(text.split('\n')) <= OTTStandards.MAX_LINES_PER_SUBTITLE
        
    def detect_language(self, text: str) -> str:
        """
        Detect language of subtitle text
        
        Args:
            text: Subtitle text
            
        Returns:
            str: Detected language code
        """
        try:
            return detect(text)
        except:
            return 'en'  # default to English
            
    def spell_check(self, text: str, lang: str = 'en') -> str:
        """
        Perform spell checking on subtitle text
        
        Args:
            text: Subtitle text
            lang: Language code
            
        Returns:
            str: Corrected text
        """
        if lang == 'en':
            blob = TextBlob(text)
            return str(blob.correct())
        return text
        
    def fix_timing(self, start_ms: int, end_ms: int) -> Tuple[int, int]:
        """
        Adjust timing to meet OTT standards
        
        Args:
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            
        Returns:
            Tuple[int, int]: Corrected start and end times
        """
        duration = end_ms - start_ms
        
        # Ensure minimum duration
        if duration < OTTStandards.MIN_DURATION_MS:
            end_ms = start_ms + OTTStandards.MIN_DURATION_MS
            
        # Ensure maximum duration
        if duration > OTTStandards.MAX_DURATION_MS:
            end_ms = start_ms + OTTStandards.MAX_DURATION_MS
            
        return start_ms, end_ms
        
    def correct_subtitle(self, subtitle) -> Dict:
        """
        Apply corrections to a single subtitle entry
        
        Args:
            subtitle: Subtitle object
            
        Returns:
            Dict: Correction results and modified subtitle
        """
        original_text = subtitle.text
        start_ms = subtitle.start.ordinal
        end_ms = subtitle.end.ordinal
        
        # Detect language
        lang = self.detect_language(original_text)
        
        # Spell check
        corrected_text = self.spell_check(original_text, lang)
        
        # Fix timing
        new_start_ms, new_end_ms = self.fix_timing(start_ms, end_ms)
        
        # Format text for line length and count
        lines = corrected_text.split('\n')
        formatted_lines = []
        current_line = ""
        
        for word in ' '.join(lines).split():
            if len(current_line + " " + word) <= OTTStandards.MAX_CHARS_PER_LINE:
                current_line = (current_line + " " + word).strip()
            else:
                if current_line:
                    formatted_lines.append(current_line)
                current_line = word
                
        if current_line:
            formatted_lines.append(current_line)
            
        # Ensure max two lines
        final_text = '\n'.join(formatted_lines[:OTTStandards.MAX_LINES_PER_SUBTITLE])
        
        # Update subtitle
        subtitle.text = final_text
        subtitle.start.ordinal = new_start_ms
        subtitle.end.ordinal = new_end_ms
        
        return {
            'original_text': original_text,
            'corrected_text': final_text,
            'language': lang,
            'timing_modified': (start_ms, end_ms) != (new_start_ms, new_end_ms),
            'text_modified': original_text != final_text
        }
        
    def process_file(self, input_file: str, output_file: str) -> List[Dict]:
        """
        # PUBLIC_INTERFACE
        Process entire subtitle file and apply corrections
        
        Args:
            input_file: Path to input subtitle file
            output_file: Path to save corrected subtitle file
            
        Returns:
            List[Dict]: List of correction results for each subtitle
        """
        if not self.load_subtitles(input_file):
            return []
            
        results = []
        previous_end = 0
        
        for i, subtitle in enumerate(self.subtitles):
            # Add gap between subtitles if needed
            if previous_end > 0:
                if subtitle.start.ordinal - previous_end < OTTStandards.MIN_GAP_MS:
                    subtitle.start.ordinal = previous_end + OTTStandards.MIN_GAP_MS
                    
            result = self.correct_subtitle(subtitle)
            results.append(result)
            previous_end = subtitle.end.ordinal
            
        # Save corrected subtitles
        self.subtitles.save(output_file, encoding='utf-8')
        return results
        
    def validate_burnt_in_overlap(self, video_regions: List[Dict]) -> List[Dict]:
        """
        # PUBLIC_INTERFACE
        Check for overlap between subtitles and burnt-in text regions
        
        Args:
            video_regions: List of dictionaries containing coordinates and timings of burnt-in text
            
        Returns:
            List[Dict]: List of overlap issues
        """
        if not self.subtitles:
            return []
            
        overlaps = []
        for subtitle in self.subtitles:
            for region in video_regions:
                if (subtitle.start.ordinal <= region['end_time'] and 
                    subtitle.end.ordinal >= region['start_time']):
                    overlaps.append({
                        'subtitle_index': subtitle.index,
                        'subtitle_text': subtitle.text,
                        'region': region
                    })
        return overlaps

# Example usage:
"""
corrector = SubtitleCorrector()
results = corrector.process_file('input.srt', 'output.srt')
"""
