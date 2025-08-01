import os
import traceback
from database import update_job_status, create_file_entry
from subtitle_processor import (
    detect_subtitle_format, validate_subtitle_file, auto_correct_subtitle, 
    generate_subtitle_llm, translate_subtitle_llm, check_compliance
)
from config import settings
from file_utils import save_file_bytes
from database import get_file_by_id
import logging

logger = logging.getLogger("uvicorn")

# PUBLIC_INTERFACE
def process_upload_job(job_id, video_path, db):
    """Process uploaded video: could validate, extract metadata, queue for generation."""
    try:
        update_job_status(db, job_id, "processing", logs="Validating uploaded video file.")
        # Placeholder: video validation / metadata extraction
        update_job_status(db, job_id, "finished", logs="Upload complete.")
    except Exception as e:
        logger.error(traceback.format_exc())
        update_job_status(db, job_id, "failed", logs=f"Job failed: {e}")

# PUBLIC_INTERFACE
def process_sync_job(job_id, subtitle_path, db):
    """Process uploaded subtitle: validate and auto-correct."""
    try:
        update_job_status(db, job_id, "processing", logs="Detecting format and running validation.")
        fmt = detect_subtitle_format(subtitle_path)
        issues = validate_subtitle_file(subtitle_path, fmt)
        corrected_path = subtitle_path
        if issues:
            update_job_status(db, job_id, "processing", logs="Auto-correcting issues.")
            corrected_path = auto_correct_subtitle(subtitle_path, fmt, issues)
            update_job_status(db, job_id, "processing", logs="Correction complete.")
        # Register corrected file
        file_entry = create_file_entry(db, corrected_path, get_file_by_id(db, subtitle_path).user_id, "subtitle_corrected")
        update_job_status(db, job_id, "finished", result=corrected_path, logs="Subtitle validation complete.")
    except Exception as e:
        logger.error(traceback.format_exc())
        update_job_status(db, job_id, "failed", logs=f"Subtitle sync failed: {e}")

# PUBLIC_INTERFACE
def process_generation_job(job_id, video_file_id, language, db):
    """Generate subtitle with LLM."""
    try:
        update_job_status(db, job_id, "processing", logs=f"Generating subtitles for language: {language}")
        video_file = get_file_by_id(db, video_file_id)
        # Generate subtitle
        output_path = generate_subtitle_llm(video_file.path, language)
        create_file_entry(db, output_path, video_file.user_id, "generated_subtitle")
        update_job_status(db, job_id, "finished", result=output_path, logs="Subtitle generation complete.")
    except Exception as e:
        logger.error(traceback.format_exc())
        update_job_status(db, job_id, "failed", logs=f"Subtitle generation failed: {e}")

# PUBLIC_INTERFACE
def process_translation_job(job_id, subtitle_file_id, target_language, db):
    """Translate subtitle to another language via LLM."""
    try:
        update_job_status(db, job_id, "processing", logs=f"Translating subtitle to {target_language}")
        subtitle_file = get_file_by_id(db, subtitle_file_id)
        translated_path = translate_subtitle_llm(subtitle_file.path, target_language)
        create_file_entry(db, translated_path, subtitle_file.user_id, "translated_subtitle")
        update_job_status(db, job_id, "finished", result=translated_path, logs="Subtitle translation complete.")
    except Exception as e:
        logger.error(traceback.format_exc())
        update_job_status(db, job_id, "failed", logs=f"Subtitle translation failed: {e}")

# PUBLIC_INTERFACE
def process_compliance_job(job_id, subtitle_file_id, platform, db):
    """Run compliance checks."""
    try:
        update_job_status(db, job_id, "processing", logs="Running compliance checks")
        subtitle_file = get_file_by_id(db, subtitle_file_id)
        result = check_compliance(subtitle_file.path, platform)
        update_job_status(db, job_id, "finished", result=result, logs="Compliance check complete.")
    except Exception as e:
        logger.error(traceback.format_exc())
        update_job_status(db, job_id, "failed", logs=f"Compliance check failed: {e}")
