"""
Subtitle processing utilities for format detection, validation, correction, and translation
"""

import re
import os
import asyncio
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SubtitleFormat(Enum):
    """Supported subtitle formats"""
    SRT = "srt"
    WEBVTT = "webvtt" 
    ASS = "ass"
    SSA = "ssa"
    SCC = "scc"
    UNKNOWN = "unknown"

@dataclass
class TimestampRange:
    """Represents a subtitle timestamp range"""
    start_ms: int
    end_ms: int
    
    @classmethod
    def from_srt_timestamp(cls, timestamp_str: str) -> 'TimestampRange':
        """Parse SRT timestamp format (00:01:23,456 --> 00:01:27,890)"""
        parts = timestamp_str.split(' --> ')
        if len(parts) != 2:
            raise ValueError(f"Invalid timestamp format: {timestamp_str}")
        
        start_ms = cls._parse_srt_time(parts[0].strip())
        end_ms = cls._parse_srt_time(parts[1].strip())
        
        return cls(start_ms, end_ms)
    
    @staticmethod
    def _parse_srt_time(time_str: str) -> int:
        """Parse SRT time format to milliseconds"""
        # Format: HH:MM:SS,mmm
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if not match:
            raise ValueError(f"Invalid time format: {time_str}")
        
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
    
    def to_srt_timestamp(self) -> str:
        """Convert to SRT timestamp format"""
        def ms_to_srt_time(ms: int) -> str:
            hours = ms // 3600000
            minutes = (ms % 3600000) // 60000
            seconds = (ms % 60000) // 1000
            milliseconds = ms % 1000
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        
        return f"{ms_to_srt_time(self.start_ms)} --> {ms_to_srt_time(self.end_ms)}"

@dataclass
class SubtitleEntry:
    """Represents a single subtitle entry"""
    sequence: int
    timestamp: TimestampRange
    text: str
    
    def duration_ms(self) -> int:
        """Get duration in milliseconds"""
        return self.timestamp.end_ms - self.timestamp.start_ms
    
    def reading_speed_wpm(self) -> float:
        """Calculate reading speed in words per minute"""
        word_count = len(self.text.split())
        duration_minutes = self.duration_ms() / 60000
        return word_count / duration_minutes if duration_minutes > 0 else 0

@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    severity: str  # "error", "warning", "info"
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None

@dataclass
class ValidationResult:
    """Subtitle validation results"""
    is_valid: bool
    format_type: SubtitleFormat
    issues: List[ValidationIssue]
    statistics: Dict[str, any]

class SubtitleProcessor:
    """Main subtitle processing class"""
    
    def __init__(self):
        self.supported_formats = [
            SubtitleFormat.SRT,
            SubtitleFormat.WEBVTT,
            SubtitleFormat.ASS,
            SubtitleFormat.SSA
        ]
    
    # PUBLIC_INTERFACE
    def detect_format(self, content: str) -> SubtitleFormat:
        """
        Detect subtitle format from content
        
        Args:
            content: Subtitle file content
            
        Returns:
            Detected SubtitleFormat
        """
        content_lower = content.lower().strip()
        
        # WebVTT detection
        if content_lower.startswith("webvtt") or "webvtt" in content_lower[:50]:
            return SubtitleFormat.WEBVTT
        
        # SRT detection - look for sequence number and timestamp pattern
        srt_pattern = r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}'
        if re.search(srt_pattern, content, re.MULTILINE):
            return SubtitleFormat.SRT
        
        # ASS/SSA detection
        if "[script info]" in content_lower or "[v4+ styles]" in content_lower:
            return SubtitleFormat.ASS if "ass" in content_lower else SubtitleFormat.SSA
        
        # SCC detection (timecode format)
        if re.search(r'\d{2}:\d{2}:\d{2}:\d{2}', content):
            return SubtitleFormat.SCC
        
        return SubtitleFormat.UNKNOWN
    
    # PUBLIC_INTERFACE
    def parse_srt(self, content: str) -> List[SubtitleEntry]:
        """
        Parse SRT subtitle content into structured entries
        
        Args:
            content: SRT file content
            
        Returns:
            List of SubtitleEntry objects
        """
        entries = []
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            try:
                # Parse sequence number
                sequence = int(lines[0].strip())
                
                # Parse timestamp
                timestamp = TimestampRange.from_srt_timestamp(lines[1])
                
                # Join text lines
                text = '\n'.join(lines[2:]).strip()
                
                entries.append(SubtitleEntry(sequence, timestamp, text))
                
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse SRT block: {e}")
                continue
        
        return entries
    
    # PUBLIC_INTERFACE
    def validate_subtitles(self, content: str) -> ValidationResult:
        """
        Comprehensive subtitle validation
        
        Args:
            content: Subtitle file content
            
        Returns:
            ValidationResult with issues and statistics
        """
        format_type = self.detect_format(content)
        issues = []
        statistics = {}
        
        # Basic format validation
        if format_type == SubtitleFormat.UNKNOWN:
            issues.append(ValidationIssue(
                "error", 
                "Unknown or unsupported subtitle format",
                suggestion="Ensure file is in SRT, WebVTT, ASS, or SSA format"
            ))
            return ValidationResult(False, format_type, issues, statistics)
        
        # Format-specific validation
        if format_type == SubtitleFormat.SRT:
            entries = self.parse_srt(content)
            issues.extend(self._validate_srt_entries(entries))
            statistics = self._calculate_statistics(entries)
        elif format_type == SubtitleFormat.WEBVTT:
            issues.extend(self._validate_webvtt(content))
            statistics = self._calculate_webvtt_statistics(content)
        
        # General content validation
        issues.extend(self._validate_general_content(content))
        
        is_valid = not any(issue.severity == "error" for issue in issues)
        
        return ValidationResult(is_valid, format_type, issues, statistics)
    
    def _validate_srt_entries(self, entries: List[SubtitleEntry]) -> List[ValidationIssue]:
        """Validate SRT subtitle entries"""
        issues = []
        
        for i, entry in enumerate(entries):
            # Check sequence order
            if entry.sequence != i + 1:
                issues.append(ValidationIssue(
                    "warning",
                    f"Sequence number {entry.sequence} expected {i + 1}",
                    line_number=i + 1,
                    suggestion="Renumber sequences sequentially"
                ))
            
            # Check timestamp validity
            if entry.timestamp.start_ms >= entry.timestamp.end_ms:
                issues.append(ValidationIssue(
                    "error",
                    f"Invalid timestamp: start >= end at sequence {entry.sequence}",
                    line_number=i + 1
                ))
            
            # Check duration
            duration_ms = entry.duration_ms()
            if duration_ms < 500:  # Less than 0.5 seconds
                issues.append(ValidationIssue(
                    "warning",
                    f"Very short duration ({duration_ms}ms) at sequence {entry.sequence}",
                    suggestion="Consider extending display time"
                ))
            elif duration_ms > 10000:  # More than 10 seconds
                issues.append(ValidationIssue(
                    "warning",
                    f"Very long duration ({duration_ms}ms) at sequence {entry.sequence}",
                    suggestion="Consider splitting long subtitles"
                ))
            
            # Check reading speed
            reading_speed = entry.reading_speed_wpm()
            if reading_speed > 200:
                issues.append(ValidationIssue(
                    "warning",
                    f"Fast reading speed ({reading_speed:.1f} WPM) at sequence {entry.sequence}",
                    suggestion="Consider reducing text or extending time"
                ))
            
            # Check text length
            if len(entry.text) > 84:  # Netflix standard
                issues.append(ValidationIssue(
                    "info",
                    f"Long text ({len(entry.text)} chars) at sequence {entry.sequence}",
                    suggestion="Consider splitting into multiple lines"
                ))
            
            # Check for overlapping timestamps
            if i > 0:
                prev_entry = entries[i - 1]
                if entry.timestamp.start_ms < prev_entry.timestamp.end_ms:
                    issues.append(ValidationIssue(
                        "warning",
                        f"Overlapping timestamps at sequences {prev_entry.sequence}-{entry.sequence}",
                        suggestion="Adjust timestamps to avoid overlap"
                    ))
        
        return issues
    
    def _validate_webvtt(self, content: str) -> List[ValidationIssue]:
        """Validate WebVTT format"""
        issues = []
        lines = content.split('\n')
        
        # Check WebVTT signature
        if not lines[0].strip().startswith("WEBVTT"):
            issues.append(ValidationIssue(
                "error",
                "WebVTT files must start with 'WEBVTT'",
                line_number=1
            ))
        
        # Check for proper cue format
        cue_pattern = r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}'
        if not re.search(cue_pattern, content):
            issues.append(ValidationIssue(
                "warning",
                "No valid WebVTT cues found",
                suggestion="Check timestamp format (HH:MM:SS.mmm)"
            ))
        
        return issues
    
    def _validate_general_content(self, content: str) -> List[ValidationIssue]:
        """General content validation"""
        issues = []
        
        # Check encoding
        try:
            content.encode('utf-8')
        except UnicodeEncodeError:
            issues.append(ValidationIssue(
                "error",
                "Content contains invalid UTF-8 characters",
                suggestion="Ensure file is saved with UTF-8 encoding"
            ))
        
        # Check for common issues
        if '\r\n' in content:
            issues.append(ValidationIssue(
                "info",
                "File uses Windows line endings (CRLF)",
                suggestion="Consider using Unix line endings (LF)"
            ))
        
        # Check file size
        if len(content) > 1000000:  # 1MB
            issues.append(ValidationIssue(
                "warning",
                "Large subtitle file may impact performance",
                suggestion="Consider splitting into smaller files"
            ))
        
        return issues
    
    def _calculate_statistics(self, entries: List[SubtitleEntry]) -> Dict[str, any]:
        """Calculate statistics for SRT entries"""
        if not entries:
            return {}
        
        total_words = sum(len(entry.text.split()) for entry in entries)
        total_chars = sum(len(entry.text) for entry in entries)
        total_duration = sum(entry.duration_ms() for entry in entries)
        reading_speeds = [entry.reading_speed_wpm() for entry in entries if entry.duration_ms() > 0]
        
        return {
            "total_entries": len(entries),
            "total_words": total_words,
            "total_characters": total_chars,
            "total_duration_ms": total_duration,
            "average_reading_speed_wpm": sum(reading_speeds) / len(reading_speeds) if reading_speeds else 0,
            "max_reading_speed_wpm": max(reading_speeds) if reading_speeds else 0,
            "min_reading_speed_wpm": min(reading_speeds) if reading_speeds else 0,
            "average_entry_duration_ms": total_duration / len(entries) if entries else 0
        }
    
    def _calculate_webvtt_statistics(self, content: str) -> Dict[str, any]:
        """Calculate basic statistics for WebVTT content"""
        lines = content.split('\n')
        cue_count = len(re.findall(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}', content))
        
        return {
            "total_lines": len(lines),
            "estimated_cues": cue_count,
            "total_characters": len(content)
        }
    
    # PUBLIC_INTERFACE
    async def correct_subtitle_sync(self, video_path: str, subtitle_path: str, 
                                  offset_ms: int = 0) -> str:
        """
        Correct subtitle synchronization with video
        
        Args:
            video_path: Path to video file
            subtitle_path: Path to subtitle file
            offset_ms: Manual offset in milliseconds
            
        Returns:
            Path to corrected subtitle file
        """
        logger.info(f"Starting sync correction for {subtitle_path}")
        
        # Read subtitle content
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        format_type = self.detect_format(content)
        
        if format_type == SubtitleFormat.SRT:
            corrected_content = await self._correct_srt_sync(content, video_path, offset_ms)
        elif format_type == SubtitleFormat.WEBVTT:
            corrected_content = await self._correct_webvtt_sync(content, video_path, offset_ms)
        else:
            # For unsupported formats, just apply offset
            corrected_content = self._apply_timestamp_offset(content, offset_ms)
        
        # Save corrected file
        corrected_path = subtitle_path.replace(
            os.path.splitext(subtitle_path)[1], 
            f"_corrected{os.path.splitext(subtitle_path)[1]}"
        )
        
        with open(corrected_path, 'w', encoding='utf-8') as f:
            f.write(corrected_content)
        
        logger.info(f"Sync correction completed: {corrected_path}")
        return corrected_path
    
    async def _correct_srt_sync(self, content: str, video_path: str, offset_ms: int) -> str:
        """Correct SRT subtitle synchronization"""
        entries = self.parse_srt(content)
        
        # Apply offset and any detected corrections
        corrected_entries = []
        for entry in entries:
            # Apply manual offset
            new_start = max(0, entry.timestamp.start_ms + offset_ms)
            new_end = max(new_start + 500, entry.timestamp.end_ms + offset_ms)  # Minimum 500ms duration
            
            # Create corrected entry
            corrected_entry = SubtitleEntry(
                entry.sequence,
                TimestampRange(new_start, new_end),
                entry.text
            )
            corrected_entries.append(corrected_entry)
        
        # Convert back to SRT format
        srt_content = self._entries_to_srt(corrected_entries)
        return srt_content
    
    async def _correct_webvtt_sync(self, content: str, video_path: str, offset_ms: int) -> str:
        """Correct WebVTT subtitle synchronization"""
        # Basic WebVTT timestamp correction
        def adjust_webvtt_time(match):
            time_str = match.group(0)
            # Simple offset application for WebVTT format
            return time_str  # Placeholder - would implement proper WebVTT time adjustment
        
        # Apply timestamp corrections
        corrected = re.sub(
            r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}',
            adjust_webvtt_time,
            content
        )
        
        return corrected
    
    def _apply_timestamp_offset(self, content: str, offset_ms: int) -> str:
        """Apply simple timestamp offset to content"""
        # Basic implementation - would be format-specific in production
        return content
    
    def _entries_to_srt(self, entries: List[SubtitleEntry]) -> str:
        """Convert SubtitleEntry list back to SRT format"""
        srt_blocks = []
        
        for entry in entries:
            block = f"{entry.sequence}\n{entry.timestamp.to_srt_timestamp()}\n{entry.text}\n"
            srt_blocks.append(block)
        
        return '\n'.join(srt_blocks)
    
    # PUBLIC_INTERFACE
    async def generate_subtitles_from_audio(self, video_path: str, 
                                          target_language: str = "en") -> str:
        """
        Generate subtitles from video audio using AI/ML models
        
        Args:
            video_path: Path to video file
            target_language: Target language for subtitles
            
        Returns:
            Path to generated subtitle file
        """
        logger.info(f"Generating subtitles for {video_path} in language {target_language}")
        
        # Mock implementation - in production would use:
        # 1. Audio extraction from video
        # 2. Speech-to-text API (e.g., Whisper, Google Speech-to-Text)
        # 3. LLM for text refinement and formatting
        
        # Simulate processing time
        await asyncio.sleep(3)
        
        # Generate mock subtitle content
        mock_subtitles = self._generate_mock_subtitles(target_language)
        
        # Save generated file
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        generated_path = os.path.join(
            os.path.dirname(video_path),
            f"{base_name}_generated_{target_language}.srt"
        )
        
        with open(generated_path, 'w', encoding='utf-8') as f:
            f.write(mock_subtitles)
        
        logger.info(f"Subtitle generation completed: {generated_path}")
        return generated_path
    
    def _generate_mock_subtitles(self, language: str) -> str:
        """Generate mock subtitle content for demonstration"""
        language_samples = {
            "en": [
                "Welcome to this video presentation.",
                "We will explore various topics today.",
                "Thank you for watching and learning with us."
            ],
            "es": [
                "Bienvenidos a esta presentación de video.",
                "Exploraremos varios temas hoy.",
                "Gracias por ver y aprender con nosotros."
            ],
            "fr": [
                "Bienvenue à cette présentation vidéo.",
                "Nous explorerons divers sujets aujourd'hui.",
                "Merci de regarder et d'apprendre avec nous."
            ]
        }
        
        texts = language_samples.get(language, language_samples["en"])
        
        srt_content = ""
        for i, text in enumerate(texts, 1):
            start_time = f"00:00:{i*5:02d},000"
            end_time = f"00:00:{i*5+4:02d},000"
            srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
        
        return srt_content
    
    # PUBLIC_INTERFACE
    async def translate_subtitles(self, subtitle_path: str, 
                                target_language: str) -> str:
        """
        Translate subtitles to target language
        
        Args:
            subtitle_path: Path to subtitle file
            target_language: Target language code
            
        Returns:
            Path to translated subtitle file
        """
        logger.info(f"Translating {subtitle_path} to {target_language}")
        
        # Read original subtitles
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        format_type = self.detect_format(content)
        
        if format_type == SubtitleFormat.SRT:
            translated_content = await self._translate_srt(content, target_language)
        else:
            # Basic translation for other formats
            translated_content = await self._basic_translate(content, target_language)
        
        # Save translated file
        base_name = os.path.splitext(subtitle_path)[0]
        extension = os.path.splitext(subtitle_path)[1]
        translated_path = f"{base_name}_translated_{target_language}{extension}"
        
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        
        logger.info(f"Translation completed: {translated_path}")
        return translated_path
    
    async def _translate_srt(self, content: str, target_language: str) -> str:
        """Translate SRT content preserving format"""
        entries = self.parse_srt(content)
        translated_entries = []
        
        for entry in entries:
            # Mock translation - in production would use translation API
            translated_text = await self._mock_translate_text(entry.text, target_language)
            
            translated_entry = SubtitleEntry(
                entry.sequence,
                entry.timestamp,
                translated_text
            )
            translated_entries.append(translated_entry)
        
        return self._entries_to_srt(translated_entries)
    
    async def _basic_translate(self, content: str, target_language: str) -> str:
        """Basic translation for non-SRT formats"""
        # Mock implementation - would use proper translation service
        await asyncio.sleep(1)  # Simulate API call
        
        # Simple mock translation
        if target_language == "es":
            content = content.replace("Hello", "Hola")
            content = content.replace("Thank you", "Gracias")
        elif target_language == "fr":
            content = content.replace("Hello", "Bonjour")
            content = content.replace("Thank you", "Merci")
        
        return content
    
    async def _mock_translate_text(self, text: str, target_language: str) -> str:
        """Mock text translation"""
        # In production, this would call a translation API like Google Translate,
        # Azure Translator, or use an LLM for translation
        
        await asyncio.sleep(0.1)  # Simulate API call delay
        
        # Simple mock translations
        translations = {
            "es": {
                "Welcome": "Bienvenido",
                "Hello": "Hola", 
                "Thank you": "Gracias",
                "video": "video",
                "presentation": "presentación"
            },
            "fr": {
                "Welcome": "Bienvenue",
                "Hello": "Bonjour",
                "Thank you": "Merci", 
                "video": "vidéo",
                "presentation": "présentation"
            }
        }
        
        if target_language in translations:
            translated_text = text
            for english, translation in translations[target_language].items():
                translated_text = translated_text.replace(english, translation)
            return f"[{target_language.upper()}] {translated_text}"
        
        return f"[{target_language.upper()}] {text}"

# Global processor instance
subtitle_processor = SubtitleProcessor()
