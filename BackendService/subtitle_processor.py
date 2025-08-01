"""
subtitle_processor.py

Defines FastAPI endpoints for subtitle-audio synchronization, subtitle generation,
and translation using Gemini LLMs (via LangChain). Exports a router object for inclusion
in the main FastAPI application.

PUBLIC INTERFACE:
- 'router' (APIRouter): Register in your FastAPI application via `include_router`.
- generate_subtitles_with_llm: Helper for LLM-based subtitle generation.
- translate_subtitles_with_llm: Helper for LLM-based subtitle translation.
"""

import os
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from config import get_gemini_api_key

# LangChain imports for Gemini (google-generativeai and langchain-google-genai must be installed)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate

# --- FastAPI Router ---
# PUBLIC_INTERFACE
router = APIRouter()

# ------------------ LLM core logic ------------------

GEMINI_API_KEY = get_gemini_api_key()
GEMINI_MODEL = "gemini-pro"  # Default model name; can be changed if needed

llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY)

# PUBLIC_INTERFACE
def generate_subtitles_with_llm(video_path, language):
    """Generate subtitles for a video using Gemini LLM via LangChain.

    Args:
        video_path (str): The path to the video file.
        language (str): The language for subtitle generation.

    Returns:
        str: LLM-generated subtitles (as string or SRT format).
    """
    prompt_template = ChatPromptTemplate.from_template(
        (
            "Given the video at path '{video_path}', generate fully timed subtitles in {language}. "
            "Output should be in .srt format with accurate start/end times and natural segmentation."
        )
    )
    chain = prompt_template | llm
    result = chain.invoke({"video_path": video_path, "language": language})
    return result.content if hasattr(result, "content") else str(result)

# PUBLIC_INTERFACE
def translate_subtitles_with_llm(subtitle_text, target_language):
    """Translate subtitles to a target language using Gemini LLM via LangChain.

    Args:
        subtitle_text (str): The input subtitle file contents as text.
        target_language (str): The target language for translation.

    Returns:
        str: Translated subtitles (as string or SRT format).
    """
    prompt_template = ChatPromptTemplate.from_template(
        (
            "Translate the following .srt subtitles to {target_language}. Only translate the dialogue; "
            "preserve the SRT timing and structure exactly. Output ONLY the .srt:\n{subtitle_text}"
        )
    )
    chain = prompt_template | llm
    result = chain.invoke({
        "subtitle_text": subtitle_text,
        "target_language": target_language
    })
    return result.content if hasattr(result, "content") else str(result)

# ------------------ FastAPI models and sample endpoints ------------------

class GenerateSubtitlesRequest(BaseModel):
    video_path: str = Field(..., description="Path to the video file")
    language: str = Field(..., description="Language for subtitle generation")

class TranslateSubtitlesRequest(BaseModel):
    subtitle_text: str = Field(..., description="Subtitle file contents as text")
    target_language: str = Field(..., description="Target language for translation")

# PUBLIC_INTERFACE
@router.get(
    "/health",
    summary="Health Check for Subtitle Processor",
    description="Returns status if the subtitle processor router is correctly attached.",
    tags=["Health"],
    responses={200: {"description": "Healthy status"}}
)
async def health_check():
    """Returns a healthy status if router is correctly attached."""
    return {"status": "ok"}

# PUBLIC_INTERFACE
@router.post(
    "/generate-subtitles",
    summary="Generate Subtitles using LLM",
    description="Generate subtitles for a video file using Gemini LLM via LangChain.",
    tags=["LLM", "Subtitles"],
    response_description="LLM-generated subtitles in string/SRT format."
)
async def api_generate_subtitles(request: GenerateSubtitlesRequest):
    """
    Generate subtitles for a video file (by path) using Gemini language model.
    """
    try:
        result = generate_subtitles_with_llm(request.video_path, request.language)
        return {"subtitles": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Subtitle generation failed: {e}")

# PUBLIC_INTERFACE
@router.post(
    "/translate-subtitles",
    summary="Translate Subtitles using LLM",
    description="Translate subtitle content to a target language using Gemini LLM via LangChain.",
    tags=["LLM", "Translation"],
    response_description="Translated subtitles in string/SRT format."
)
async def api_translate_subtitles(request: TranslateSubtitlesRequest):
    """
    Translate subtitles (provided as text content) to a target language.
    """
    try:
        result = translate_subtitles_with_llm(request.subtitle_text, request.target_language)
        return {"subtitles": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Subtitle translation failed: {e}")
