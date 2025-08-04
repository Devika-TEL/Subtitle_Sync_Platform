import os
import logging
from typing import Optional, List

import google.generativeai as genai
from config import get_settings

logger = logging.getLogger(__name__)

class GeminiSubtitleLLM:
    """LLM client for subtitle generation/correction using Google's Gemini API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_settings().gemini_api_key
        if not self.api_key:
            logger.error("GEMINI_API_KEY is not set in environment or config.")
            raise ValueError("GEMINI_API_KEY is required for Gemini API integration.")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-pro")

    # PUBLIC_INTERFACE
    def generate_subtitles(self, transcribed_text: str, language: str = "en") -> str:
        """
        Generate SRT subtitles using Gemini LLM for given transcript & language.

        Args:
            transcribed_text: Plain transcript of the video.
            language: Target subtitle language.

        Returns:
            SRT formatted string of subtitles.
        """
        prompt = (
            f"You are an AI that generates professional SRT subtitles.\n"
            f"Given the following transcript, generate SRT subtitles in language '{language}', "
            f"starting timecodes appropriately, following SRT standards and OTT best practices, "
            f"60-chars max/line, <=2 lines per subtitle, proper timing for average speech. "
            f"Transcript:\n\n{transcribed_text}\n"
            f"---\nReturn SRT content only. No extra comments."
        )
        try:
            response = self.model.generate_content(prompt, generation_config={
                "temperature": 0.3
            })
            # Defensive: extract SRT block from possibly verbose LLM response.
            content = response.text
            srt_start = content.find("1\n")
            return content[srt_start:] if srt_start != -1 else content
        except Exception as e:
            logger.error(f"Gemini subtitle generation failed: {e}")
            raise

    # PUBLIC_INTERFACE
    def correct_subtitles(self, original_srt_text: str) -> str:
        """
        Correct timing/format/language errors in an existing SRT using Gemini LLM.

        Args:
            original_srt_text: SRT formatted subtitle content.

        Returns:
            SRT formatted string of improved subtitles.
        """
        prompt = (
            "You are an expert in subtitle correction for OTT platforms. "
            "Given the following SRT file, correct any timing, formatting, spelling, or OTT compliance errors. "
            "Preserve the meaning and synchronize better to spoken audio as much as possible, "
            "without adding or removing subtitles unless needed to fix errors. "
            "Only output the corrected SRT content, no comments. Here is the file:\n\n"
            f"{original_srt_text}\n"
        )
        try:
            response = self.model.generate_content(prompt, generation_config={
                "temperature": 0.2
            })
            content = response.text
            srt_start = content.find("1\n")
            return content[srt_start:] if srt_start != -1 else content
        except Exception as e:
            logger.error(f"Gemini subtitle correction failed: {e}")
            raise

# Single shared instance
gemini_llm = None
def get_gemini_llm():
    global gemini_llm
    if gemini_llm is None:
        gemini_llm = GeminiSubtitleLLM()
    return gemini_llm
