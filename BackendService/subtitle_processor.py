import os

from config import get_gemini_api_key

# LangChain imports for Gemini (google-generativeai and langchain-google-genai must be installed)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate

# -- LLM chain initialization (Gemini via LangChain) --
# Get the Gemini API key from environment/config
GEMINI_API_KEY = get_gemini_api_key()
GEMINI_MODEL = "gemini-pro"  # Default model name; can be changed if needed

# Initialize Gemini model wrapper
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
    # Design a prompt for subtitle generation
    prompt_template = ChatPromptTemplate.from_template(
        (
            "Given the video at path '{video_path}', generate fully timed subtitles in {language}. "
            "Output should be in .srt format with accurate start/end times and natural segmentation."
        )
    )
    chain = prompt_template | llm
    # Call the LLM with formatted input
    result = chain.invoke({"video_path": video_path, "language": language})
    # Extract and return the response (actual output format may depend on Gemini's return)
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
    # Design a prompt for translation, instruct Gemini to preserve timing/format
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
