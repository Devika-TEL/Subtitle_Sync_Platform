import os
import re
import cv2
import numpy as np
import pysrt
import logging
from typing import List, Tuple, Optional

# Use module-level logger; do not reconfigure global logging
logger = logging.getLogger(__name__)

# Visualization toggle (disabled by default in production)
VISUALIZE_FRAMES = False
FRAMES_DIR = os.path.join("processed", "rapid_ocr_frames")

# Try to import RapidOCR; raise helpful error if missing at runtime
try:
    from rapidocr_onnxruntime import RapidOCR  # OCR engine (CPU via onnxruntime)
except Exception as _import_err:
    RapidOCR = None  # Will validate at runtime when needed

# Internal singleton for OCR engine
_engine_instance = None
_frame_counter = 0


def _ensure_frames_dir():
    """Ensure visualization frames directory exists if visualization is enabled."""
    if VISUALIZE_FRAMES:
        os.makedirs(FRAMES_DIR, exist_ok=True)


def get_ocr_engine():
    """
    Get or initialize the RapidOCR engine lazily.

    Returns:
        RapidOCR instance.

    Raises:
        ImportError: If RapidOCR or its dependencies are not installed.
    """
    global _engine_instance
    if _engine_instance is None:
        if RapidOCR is None:
            raise ImportError(
                "RapidOCR is not available. Ensure 'rapidocr-onnxruntime', 'onnxruntime', "
                "'numpy', and 'opencv-python-headless' are installed."
            )
        _engine_instance = RapidOCR()
        logger.info("RapidOCR engine initialized")
    return _engine_instance


def detect_using_rapidocr(img: np.ndarray) -> List[dict]:
    """
    Run OCR on an image and return detections as list of dicts with box, text, score.

    Args:
        img: BGR image (numpy array)

    Returns:
        List of detections: [{"box": [[x,y], ... 4 pts], "text": str, "score": float}, ...]
    """
    global _frame_counter
    engine = get_ocr_engine()
    detections = []

    # Results is typically a list of tuples (box, text, score)
    results, _ = engine(img)
    if results:
        for (box, text, score) in results:
            detections.append({
                "box": box,
                "text": text,
                "score": float(score),
            })

        if VISUALIZE_FRAMES:
            _ensure_frames_dir()
            vis_img = img.copy()
            for (box, text, score) in results:
                pts = np.array(box, dtype=np.int32)
                cv2.polylines(vis_img, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
                x, y = pts[0]
                cv2.putText(vis_img, f"{text} ({score:.2f})", (int(x), int(y) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            out_path = os.path.join(FRAMES_DIR, f"result_{_frame_counter}.jpg")
            cv2.imwrite(out_path, vis_img)
    else:
        if VISUALIZE_FRAMES:
            _ensure_frames_dir()
            out_path = os.path.join(FRAMES_DIR, f"result_{_frame_counter}.jpg")
            cv2.imwrite(out_path, img)

    _frame_counter += 1
    return detections


def to_ass_timestamp(srt_time: pysrt.SubRipTime) -> str:
    """Convert pysrt.SubRipTime to ASS H:MM:SS.CC format (centiseconds)."""
    total_ms = (
        srt_time.hours * 3600 * 1000 +
        srt_time.minutes * 60 * 1000 +
        srt_time.seconds * 1000 +
        srt_time.milliseconds
    )
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    centiseconds = (total_ms % 1000) // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _decide_subtitle_position(filtered_detections_list: List[List[dict]],
                              frame_height: int,
                              bottom_threshold_ratio: float = 0.75) -> str:
    """
    Decide subtitle position: "top" if burnt-in text detected in bottom region, else "bottom".
    """
    for frame_detections in filtered_detections_list:
        if not frame_detections:
            continue
        for det in frame_detections:
            y_coords = [p[1] for p in det["box"]]
            avg_y = sum(y_coords) / len(y_coords)
            if avg_y > frame_height * bottom_threshold_ratio:
                return "top"
    return "bottom"


def _safe_frame_indices(start_frame: int, end_frame: int, min_frames: int, max_frames: int) -> List[int]:
    """Generate safe frame indices for sampling."""
    if end_frame < start_frame:
        end_frame = start_frame
    total = max(1, min(min_frames, (end_frame - start_frame + 1)))
    return np.linspace(start_frame, end_frame, total, dtype=int).tolist()


def get_position_for_segment(video_path: str, start_sec: float, end_sec: float, min_frames: int = 3) -> str:
    """
    Run OCR on sampled frames to decide top/bottom placement for a segment.

    Args:
        video_path: Path to video file
        start_sec: Segment start time (seconds)
        end_sec: Segment end time (seconds)
        min_frames: Number of frames to sample between start and end

    Returns:
        "top" or "bottom"
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("Failed to open video; defaulting to bottom")
        return "bottom"

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)

    if fps <= 0:
        # Fallback if FPS cannot be determined
        fps = 25.0

    start_frame = int(max(0, start_sec) * fps)
    end_frame = int(max(start_sec, end_sec) * fps)

    indices = _safe_frame_indices(start_frame, end_frame, max(1, min_frames), int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
    filtered_detections_per_frame: List[List[dict]] = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        detections = detect_using_rapidocr(frame)
        filtered_detections_per_frame.append(detections)

    cap.release()

    if not filtered_detections_per_frame:
        logger.info("No frames/detections captured; defaulting to bottom")
        return "bottom"

    return _decide_subtitle_position(filtered_detections_per_frame, frame_height)


def reposition_srt(video_path: str, srt_path: str, output_ass_path: str, min_frames: int = 3):
    """Read SRT, run OCR per cue range, and write an ASS file with alignment tags per cue."""
    subs = pysrt.open(srt_path)

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n"
            "ScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
            "0,0,0,0,100,100,0,0,1,2,0,2,10,10,30,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        for sub in subs:
            start_sec = sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds + sub.start.milliseconds / 1000
            end_sec = sub.end.hours * 3600 + sub.end.minutes * 60 + sub.end.seconds + sub.end.milliseconds / 1000

            position = get_position_for_segment(video_path, start_sec, end_sec, min_frames=min_frames)
            alignment_tag = r"{\an8}" if position == "top" else r"{\an2}"
            formatted_text = sub.text.replace("\n", r"\N")
            f.write(
                f"Dialogue: 0,{to_ass_timestamp(sub.start)},{to_ass_timestamp(sub.end)},Default,,0,0,0,,{alignment_tag}{formatted_text}\n"
            )


def reposition_ass(video_path: str, ass_path: str, output_ass_path: str):
    """Modify/insert alignment tags in ASS dialogue lines based on OCR decisions."""
    with open(ass_path, "r", encoding="utf-8") as fin, open(output_ass_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith("Dialogue:"):
                m = re.match(r"Dialogue: \d+,(.*?),(.*?),", line)
                if m:
                    start_str, end_str = m.groups()

                    def ass_time_to_sec(ts: str) -> float:
                        h, m_, s_cs = ts.split(":")
                        s, cs = s_cs.split(".")
                        return int(h) * 3600 + int(m_) * 60 + int(s) + int(cs) / 100.0

                    start_sec = ass_time_to_sec(start_str)
                    end_sec = ass_time_to_sec(end_str)

                    position = get_position_for_segment(video_path, start_sec, end_sec)
                    alignment_tag = r"{\an8}" if position == "top" else r"{\an2}"
                    if re.search(r"{\\an\d}", line):
                        line = re.sub(r"{\\an\d}", alignment_tag, line)
                    else:
                        line = line.rstrip("\n") + alignment_tag + "\n"
            fout.write(line)


def reposition_ssa(video_path: str, ssa_path: str, output_ssa_path: str):
    """Modify/insert alignment tags in SSA dialogue lines based on OCR decisions."""
    with open(ssa_path, "r", encoding="utf-8") as fin, open(output_ssa_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith("Dialogue:"):
                m = re.match(r"Dialogue: Marked=\d+,(.*?),(.*?),", line)
                if m:
                    start_str, end_str = m.groups()

                    def ssa_time_to_sec(ts: str) -> float:
                        h, m_, s_cs = ts.split(":")
                        s, cs = s_cs.split(".")
                        return int(h) * 3600 + int(m_) * 60 + int(s) + int(cs) / 100.0

                    start_sec = ssa_time_to_sec(start_str)
                    end_sec = ssa_time_to_sec(end_str)

                    position = get_position_for_segment(video_path, start_sec, end_sec)
                    alignment_tag = r"{\an8}" if position == "top" else r"{\an2}"
                    if re.search(r"{\\an\d}", line):
                        line = re.sub(r"{\\an\d}", alignment_tag, line)
                    else:
                        line = line.rstrip("\n") + alignment_tag + "\n"
            fout.write(line)


def _parse_vtt_time(ts: str) -> float:
    """
    Parse WebVTT time string to seconds. Supports:
    - HH:MM:SS.mmm
    - MM:SS.mmm
    """
    ts = ts.strip()
    parts = ts.split()
    time_part = parts[0]  # Ignore cue settings if any
    h = 0
    m = 0
    s = 0
    ms = 0
    t_parts = time_part.split(":")
    if len(t_parts) == 3:
        h = int(t_parts[0])
        m = int(t_parts[1])
        if "." in t_parts[2]:
            s_str, ms_str = t_parts[2].split(".")
            s = int(s_str)
            ms = int(ms_str)
        else:
            s = int(t_parts[2])
    elif len(t_parts) == 2:
        m = int(t_parts[0])
        if "." in t_parts[1]:
            s_str, ms_str = t_parts[1].split(".")
            s = int(s_str)
            ms = int(ms_str)
        else:
            s = int(t_parts[1])
    else:
        # Fallback
        try:
            return float(time_part)
        except Exception:
            return 0.0
    return h * 3600 + m * 60 + s + ms / 1000.0


def reposition_vtt(video_path: str, vtt_path: str, output_vtt_path: str):
    """For VTT: modify or insert 'line:' cue position based on OCR decision."""
    with open(vtt_path, "r", encoding="utf-8") as fin, open(output_vtt_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if "-->" in line:
                # Example: "00:00:01.000 --> 00:00:05.000 align:start line:0%"
                left, right = line.split("-->", 1)
                start_str = left.strip()
                # Right part may include cue settings after the end timestamp
                right_tokens = right.strip().split()
                end_time_token = right_tokens[0] if right_tokens else ""
                other_settings = " ".join(right_tokens[1:]) if len(right_tokens) > 1 else ""

                start_sec = _parse_vtt_time(start_str)
                end_sec = _parse_vtt_time(end_time_token)
                position = get_position_for_segment(video_path, start_sec, end_sec)

                # Update or insert line setting
                desired_line = "line:0%" if position == "top" else "line:80%"

                if "line:" in other_settings or (" line:" in line and not other_settings):
                    # Replace existing line:NN%
                    line_updated = re.sub(r"line:\s*\d+%?", desired_line, line)
                else:
                    # Append setting, preserving other settings if any
                    if other_settings:
                        line_updated = f"{start_str} --> {end_time_token} {other_settings} {desired_line}\n"
                    else:
                        line_updated = f"{start_str} --> {end_time_token} {desired_line}\n"
                fout.write(line_updated)
            else:
                fout.write(line)


# PUBLIC_INTERFACE
def process_subtitle(video_path: str, subtitle_path: str, min_frames: int = 3) -> str:
    """
    Process a subtitle file to reposition cues (top/bottom) based on OCR detections.

    Args:
        video_path: Path to the corresponding video file.
        subtitle_path: Path to the subtitle file (.srt, .ass, .ssa, .vtt).
        min_frames: Number of frames to sample per cue time range for OCR decision.

    Returns:
        Path to the repositioned subtitle output.

    Raises:
        ValueError: If an unsupported subtitle format is provided.
        ImportError: If OCR dependencies are missing.
    """
    # Ensure OCR deps are available before proceeding
    get_ocr_engine()

    ext = os.path.splitext(subtitle_path)[1].lower()

    if ext == ".srt":
        output_file = os.path.splitext(subtitle_path)[0] + "_repositioned.ass"
        reposition_srt(video_path, subtitle_path, output_file, min_frames=min_frames)
    elif ext == ".ass":
        output_file = os.path.splitext(subtitle_path)[0] + "_repositioned.ass"
        reposition_ass(video_path, subtitle_path, output_file)
    elif ext == ".ssa":
        output_file = os.path.splitext(subtitle_path)[0] + "_repositioned.ssa"
        reposition_ssa(video_path, subtitle_path, output_file)
    elif ext == ".vtt":
        output_file = os.path.splitext(subtitle_path)[0] + "_repositioned.vtt"
        reposition_vtt(video_path, subtitle_path, output_file)
    else:
        raise ValueError(f"Unsupported subtitle format: {ext}")

    logger.info(f"Repositioned subtitle saved: {output_file}")
    return output_file
