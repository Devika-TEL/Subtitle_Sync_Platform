import os
import cv2
import numpy as np
import pysrt
import re
# from rapidocr_test import detect_using_rapidocr
from rapidocr_onnxruntime import RapidOCR # for detection using rapidocr_onnxruntime
# from rapidocr import RapidOCR # for detection using rapidocr
from call_demeter import llm
import logging
logging.basicConfig(
    filename="Reposition_sub_6.txt",
    filemode='w',
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)
log = logging.getLogger()
engine = RapidOCR()
a=0
# def detect_using_rapidocr(img):
#     global a
#     print(f"a:{a}")
#     log.info(f"a:{a}")
#     result = engine(img)
#     # log.info(f"result:{result}")
#     results = result.to_json()
#     if results:
#         log.info("detections found for frame")
#         for i,temp_result in enumerate(results):
#             print("=====================================")
#             print(i,'\n',temp_result)
#             print("======================================")
#         result.vis(rf"rapid_ocr_frames\result_{a}.jpg")
#     else:
#         log.info("no detections found for frame")
#         cv2.imwrite(rf"rapid_ocr_frames\result_{a}.jpg",img)
    
#     a+=1
#     return results

def filter_detections(detections , frame):
    return
    prompt = f"""
Below given are the text detected by ocr , analyze the image and return which of these texts are burnt in text 
(not part of the scenery in the image).
detections :
{detections}
Return the detections list in the original json format. No chatting or giving programs.

"""
    resp = llm.send_image_prompt(image_input=frame, prompt=prompt)
    log.info(f"detections:{detections}")
    log.info(f"resp:{resp}")

def detect_using_rapidocr(img):
    global a
    print(f"a:{a}")
    log.info(f"a:{a}")

    # Run OCR with ONNXRuntime
    results, _ = engine(img)  # results = [(box, text, score), ...]

    detections = []
    if results:
        log.info("detections found for frame")
        for i, (box, text, score) in enumerate(results):
            temp_result = {
                "box": box,
                "text": text,
                "score": float(score)
            }
            detections.append(temp_result)

            print("=====================================")
            print(i, '\n', temp_result)
            print("======================================")

        # Visualization
        vis_img = img.copy()
        for box, text, score in results:
            pts = np.array(box, dtype=np.int32)
            cv2.polylines(vis_img, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
            x, y = pts[0]
            cv2.putText(vis_img, f"{text} ({score:.2f})", (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.imwrite(rf"rapid_ocr_frames\result_{a}.jpg", vis_img)
        # cv2.imwrite(rf"rapid_ocr_frames\intput_frame_{a}.jpg", img)

    else:
        log.info("no detections found for frame")
        cv2.imwrite(rf"rapid_ocr_frames\result_{a}.jpg", img)

    a += 1
    return detections
def to_ass_timestamp(srt_time):
    """Convert pysrt.SubRipTime to ASS H:MM:SS.CC format."""
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

def preprocess_threshold(image):
    """Prepare image for OCR."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    return thresh
import cv2
import numpy as np

def preprocess_using_blackout(image, block_size=50, contrast_thresh=0.3, blur_thresh=100.0):
    """
    Preprocess image by blacking out low-contrast or blurry regions.

    Args:
        image (numpy.ndarray): OpenCV-loaded image.
        block_size (int): Size of the region to check (pixels).
        contrast_thresh (float): Contrast threshold (lower = blacked out).
        blur_thresh (float): Laplacian variance threshold for blur.

    Returns:
        numpy.ndarray: Processed image with blacked-out regions.
    """
    output = image.copy()
    h, w = image.shape[:2]

    for y in range(0, h, block_size):
        for x in range(0, w, block_size):
            roi = image[y:y+block_size, x:x+block_size]

            if roi.size == 0:
                continue

            # Contrast check
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            I_max, I_min = np.max(gray), np.min(gray)
            contrast = (I_max - I_min) / (I_max + I_min + 1e-5)

            # Blur check
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()

            # Blackout if low quality
            if contrast < contrast_thresh or variance < blur_thresh:
                output[y:y+block_size, x:x+block_size] = (0, 0, 0)

    return output
def preprocess(image, block_size=50, contrast_thresh=0.3, blur_thresh=100.0,
               adaptive_block=15, adaptive_C=5):
    """
    Preprocess image by:
    1. Blacking out low-contrast or blurry regions.
    2. Applying adaptive thresholding.

    Args:
        image (numpy.ndarray): OpenCV-loaded image.
        block_size (int): Size of the region to check (pixels).
        contrast_thresh (float): Contrast threshold (lower = blacked out).
        blur_thresh (float): Laplacian variance threshold for blur.
        adaptive_block (int): Block size for adaptive threshold (must be odd).
        adaptive_C (int): Constant subtracted in adaptive threshold.

    Returns:
        numpy.ndarray: Processed binary image (after blackouts + thresholding).
    """
    output = image.copy()
    h, w = image.shape[:2]

    # Step 1: Blackout low-quality regions
    for y in range(0, h, block_size):
        for x in range(0, w, block_size):
            roi = image[y:y+block_size, x:x+block_size]
            if roi.size == 0:
                continue

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            I_max, I_min = np.max(gray), np.min(gray)
            contrast = (I_max - I_min) / (I_max + I_min + 1e-5)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()

            if contrast < contrast_thresh or variance < blur_thresh:
                output[y:y+block_size, x:x+block_size] = (0, 0, 0)

    # Step 2: Adaptive threshold
    gray_full = cv2.cvtColor(output, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray_full, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # or cv2.ADAPTIVE_THRESH_MEAN_C
        cv2.THRESH_BINARY,
        adaptive_block,
        adaptive_C
    )

    return binary

def preprocess_adaptive_threshold(image):
    """Prepare image for OCR using adaptive threshold."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    # Adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        gray, 
        255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # or cv2.ADAPTIVE_THRESH_MEAN_C
        cv2.THRESH_BINARY, 
        blockSize=15,   # size of neighbourhood area (must be odd)
        C=5             # constant subtracted from mean
    )
    return thresh

def decide_subtitle_position(filtered_detections_list, frame_height, bottom_threshold_ratio=0.75):
    """Top if burnt-in detected in bottom, else bottom."""
    
    log.info(f"filtered detections list :\n{filtered_detections_list}")
    for frame_detections in filtered_detections_list:
        if frame_detections:
            for det in frame_detections:
                y_coords = [p[1] for p in det["box"]]
                avg_y = sum(y_coords) / len(y_coords)
                if avg_y > frame_height * bottom_threshold_ratio:
                    return "top"
    return "bottom"

def get_position_for_segment(video_path, start_sec, end_sec, min_frames=3):
    """Run OCR on sampled frames to decide top/bottom."""
    log.info("in get position for segment")
    log.info(f"start sec:{start_sec},end_sec:{end_sec}")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    start_frame = int(start_sec * fps)
    end_frame = int(end_sec * fps)
    frame_indices = np.linspace(start_frame, end_frame, min(min_frames, abs(end_frame - start_frame + 1)), dtype=int)

    filtered_detections_per_frame = []
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            log.info("could not obtain frame")
            continue
        # preprocessed = preprocess_threshold(frame)
        # preprocessed = preprocess_adaptive_threshold(frame)
        # preprocessed = preprocess_using_blackout(frame)
        # preprocessed = preprocess(frame)
        preprocessed = frame
        detections = detect_using_rapidocr(preprocessed)
        filtered_detections_per_frame.append(detections)

    cap.release()
    filter_detections(detections=filtered_detections_per_frame,frame=frame)
    return decide_subtitle_position(filtered_detections_per_frame, frame_height)

def reposition_srt(video_path, srt_path, output_ass_path, min_frames=3):
    """Read SRT, run OCR, output ASS with repositioned alignment tags."""
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

            position = get_position_for_segment(video_path, start_sec, end_sec, min_frames)
            alignment_tag = r"{\an8}" if position == "top" else r"{\an2}"
            formatted_text = sub.text.replace("\n",r"\N")
            f.write(
                f"Dialogue: 0,{to_ass_timestamp(sub.start)},{to_ass_timestamp(sub.end)},Default,,0,0,0,,{alignment_tag}{formatted_text}\n"
            )

def reposition_ass(video_path, ass_path, output_ass_path):
    """Modify only alignment tags in ASS/SSA dialogue lines."""
    with open(ass_path, "r", encoding="utf-8") as fin, open(output_ass_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith("Dialogue:"):
                # Parse times from Dialogue line
                m = re.match(r"Dialogue: \d+,(.*?),(.*?),", line)
                if m:
                    start_str, end_str = m.groups()
                    # Convert ASS time to seconds
                    def ass_time_to_sec(ts):
                        h, m_, s_cs = ts.split(":")
                        s, cs = s_cs.split(".")
                        return int(h)*3600 + int(m_)*60 + int(s) + int(cs)/100
                    start_sec = ass_time_to_sec(start_str)
                    end_sec = ass_time_to_sec(end_str)
                    position = get_position_for_segment(video_path, start_sec, end_sec)
                    alignment_tag = r"{\an8}" if position == "top" else r"{\an2}"
                    # Replace or insert alignment tag
                    if re.search(r"{\an\d}", line):
                        
                        line = re.sub(r"{\\an\d}", alignment_tag, line)
                    else:
                        line = line.rstrip("\n") + alignment_tag + "\n"
            fout.write(line)

def reposition_ssa(video_path, ssa_path, output_ssa_path):
    """Modify only alignment tags in ASS/SSA dialogue lines."""
    with open(ssa_path, "r", encoding="utf-8") as fin, open(output_ssa_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith("Dialogue:"):
                # Parse times from Dialogue line
                m = re.match(r"Dialogue: Marked=\d+,(.*?),(.*?),", line)
                if m:
                    start_str, end_str = m.groups()
                    # Convert ASS time to seconds
                    def ssa_time_to_sec(ts):
                        h, m_, s_cs = ts.split(":")
                        s, cs = s_cs.split(".")
                        return int(h)*3600 + int(m_)*60 + int(s) + int(cs)/100
                    start_sec = ssa_time_to_sec(start_str)
                    end_sec = ssa_time_to_sec(end_str)
                    position = get_position_for_segment(video_path, start_sec, end_sec)
                    alignment_tag = r"{\an8}" if position == "top" else r"{\an2}"
                    # Replace or insert alignment tag
                    if re.search(r"{\an\d}", line):
                        
                        line = re.sub(r"{\an\d}", alignment_tag, line)
                    else:
                        line = line.rstrip("\n") + alignment_tag + "\n"
            fout.write(line)

def reposition_vtt(video_path, vtt_path, output_vtt_path):
    """For VTT: modify 'line:' cue position."""
    log.info("repositioning vtt file")
    with open(vtt_path, "r", encoding="utf-8") as fin, open(output_vtt_path, "w", encoding="utf-8") as fout:
        cue_times = None
        for line in fin:
            log.info(f"line:{line}")
            if "-->" in line:
                cue_times = line
                # Extract start/end times
                start_str, end_str = line.split("-->")
                start_sec = sum(float(x) * 60 ** (i-1) if not i==0 else float(x)/1000 for i, x in enumerate(reversed(start_str.strip().replace('.', ':').split(":"))))
                end_sec = sum(float(x) * 60 ** (i-1) if not i==0 else float(x)/1000 for i, x in enumerate(reversed(end_str.strip().replace('.', ':').split(":"))))
                position = get_position_for_segment(video_path, start_sec, end_sec)
                log.info(f"decided position:{position}")
                if "line:" in line:
                    log.info("in if")
                    line = re.sub(r"line:\d+", "line:0%" if position == "top" else "line:80%", line)
                else:
                    log.info("in else")
                    line = line.strip() + ("line:0%\n" if position == "top" else " line:80%\n")
            fout.write(line)

def process_subtitle(video_path, subtitle_path):
    ext = os.path.splitext(subtitle_path)[1].lower()

    if ext == ".srt":
        output_file = os.path.splitext(subtitle_path)[0] + "_repositioned.ass"
        reposition_srt(video_path, subtitle_path, output_file)
    # elif ext in [".ass", ".ssa"]:
    #     output_file = os.path.splitext(subtitle_path)[0] + "_repositioned.ass"
    #     reposition_ass(video_path, subtitle_path, output_file)
    elif ext ==".ass":
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

    log.info(f"Repositioned subtitle saved: {output_file}")
    return output_file

if __name__ == "__main__":
    video_path = r"../../videos_and_srt/S1E1A The Seinfeld Chronicles (Pilot).mp4"
    sub_path = r"../../videos_and_srt/S1E1A The Seinfeld Chronicles (Pilot).srt"  # Try .ass or .vtt too
    process_subtitle(video_path, sub_path)