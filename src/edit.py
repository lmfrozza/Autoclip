import os
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from config import logger
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip

# --- Reels target resolution (9:16) ---
REELS_W = 1080
REELS_H = 1920

# --- Subtitle style ---
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE = 72
COLOR_SPOKEN = (255, 255, 255)    # white — words already said
COLOR_CURRENT = (255, 220, 0)     # yellow — word being said now
COLOR_UPCOMING = (200, 200, 200)  # light gray — words not yet said
STROKE_COLOR = (0, 0, 0)
STROKE_WIDTH = 3
SUBTITLE_Y_RATIO = 0.80           # vertical position (80% from top)
MAX_LINE_WIDTH = int(REELS_W * 0.92)


def _parse_srt(srt_path: str) -> list[dict]:
    """Parse a .srt file into subtitle entries with start/end/text."""
    subtitles = []
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        time_match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", lines[1]
        )
        if not time_match:
            continue
        start = _srt_time_to_seconds(time_match.group(1))
        end = _srt_time_to_seconds(time_match.group(2))
        text = " ".join(lines[2:]).strip()
        subtitles.append({"start": start, "end": end, "text": text})

    return subtitles


def _srt_time_to_seconds(time_str: str) -> float:
    h, m, rest = time_str.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _render_karaoke_frame(words: list[str], current_idx: int, img_w: int) -> Image.Image:
    """
    Render a single PIL image with the full phrase.
    - words before current_idx: white
    - words[current_idx]: yellow
    - words after current_idx: light gray
    Handles word wrapping manually.
    """
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    stroke = STROKE_WIDTH

    # --- Measure each word ---
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)

    space_w = draw.textlength(" ", font=font)

    word_widths = [draw.textlength(w, font=font) for w in words]

    # --- Word wrap into lines ---
    lines = []       # list of list of (word_index, word)
    current_line = []
    current_w = 0.0

    for i, (word, ww) in enumerate(zip(words, word_widths)):
        needed = ww if not current_line else space_w + ww
        if current_line and current_w + needed > MAX_LINE_WIDTH:
            lines.append(current_line)
            current_line = [(i, word)]
            current_w = ww
        else:
            current_line.append((i, word))
            current_w += needed

    if current_line:
        lines.append(current_line)

    # --- Compute image height ---
    line_h = FONT_SIZE + stroke * 2 + 8  # 8px line gap
    total_h = line_h * len(lines) + stroke * 2
    img = Image.new("RGBA", (img_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = 0
    for line in lines:
        # Compute total line width for centering
        line_w = sum(draw.textlength(w, font=font) for _, w in line)
        line_w += space_w * (len(line) - 1)
        x = (img_w - line_w) / 2

        for word_idx, word in line:
            if word_idx < current_idx:
                color = COLOR_SPOKEN
            elif word_idx == current_idx:
                color = COLOR_CURRENT
            else:
                color = COLOR_UPCOMING

            # Draw stroke
            for dx in range(-stroke, stroke + 1):
                for dy in range(-stroke, stroke + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((x + dx, y + dy), word, font=font, fill=(*STROKE_COLOR, 255))

            # Draw word
            draw.text((x, y), word, font=font, fill=(*color, 255))
            x += draw.textlength(word, font=font) + space_w

        y += line_h

    return img


def _make_karaoke_clips(subtitle: dict, video_w: int, video_h: int) -> list[ImageClip]:
    """
    For each word in the subtitle, render a PIL frame and return an ImageClip
    timed to that word's estimated window.
    """
    text: str = subtitle["text"]
    start: float = subtitle["start"]
    end: float = subtitle["end"]
    duration: float = end - start

    words = text.split()
    if not words:
        return []

    # Distribute time proportionally by character count
    char_counts = [max(len(w), 1) for w in words]
    total_chars = sum(char_counts)
    word_durations = [(c / total_chars) * duration for c in char_counts]

    clips = []
    word_start = start

    for i, word_dur in enumerate(word_durations):
        pil_img = _render_karaoke_frame(words, i, video_w)

        # Position: centered horizontally, SUBTITLE_Y_RATIO from top
        y_pos = int(video_h * SUBTITLE_Y_RATIO) - pil_img.height // 2

        clip = (
            ImageClip(np.array(pil_img), duration=word_dur)
            .with_start(word_start)
            .with_position(("center", y_pos))
        )
        clips.append(clip)
        word_start += word_dur

    return clips


def _resize_to_reels(video: VideoFileClip) -> CompositeVideoClip:
    """Scale video to fit 1080px wide, center vertically on black 1080x1920 canvas."""
    scale = REELS_W / video.w
    new_w = REELS_W
    new_h = int(video.h * scale)

    resized = video.resized((new_w, new_h))
    bg = ColorClip(size=(REELS_W, REELS_H), color=(0, 0, 0)).with_duration(video.duration)
    y_offset = (REELS_H - new_h) // 2
    resized = resized.with_position(("center", y_offset))

    return CompositeVideoClip([bg, resized], size=(REELS_W, REELS_H))


def _process_clip(video_path: str, srt_path: str, output_path: str):
    logger.info(f"Processing: {os.path.basename(video_path)}")

    video = VideoFileClip(video_path)
    reels = _resize_to_reels(video)

    subtitle_clips = []
    if os.path.exists(srt_path):
        logger.info(f"Parsing subtitles: {os.path.basename(srt_path)}")
        subtitles = _parse_srt(srt_path)
        for sub in subtitles:
            subtitle_clips.extend(_make_karaoke_clips(sub, REELS_W, REELS_H))
    else:
        logger.warning(f"No .srt found for {os.path.basename(video_path)}, skipping subtitles.")

    if subtitle_clips:
        final = CompositeVideoClip([reels, *subtitle_clips], size=(REELS_W, REELS_H))
    else:
        final = reels

    final = final.with_duration(video.duration)

    logger.info(f"Exporting to: {output_path}")
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=video.fps or 30,
    )

    video.close()
    final.close()
    logger.info(f"Done: {output_path}")


def run():
    os.makedirs("data/edit", exist_ok=True)

    raw_dir = "data/raw"
    mp4_files = sorted([f for f in os.listdir(raw_dir) if f.endswith(".mp4")])

    if not mp4_files:
        logger.warning("No .mp4 files found in data/raw. Skipping edit stage.")
        return

    logger.info(f"Found {len(mp4_files)} clip(s) to process.")

    for filename in mp4_files:
        clip_id = os.path.splitext(filename)[0]
        video_path = os.path.join(raw_dir, filename)
        srt_path = os.path.join(raw_dir, f"{clip_id}.srt")
        output_path = os.path.join("data/edit", filename)

        _process_clip(video_path, srt_path, output_path)

    logger.info("Edit stage complete.")


if __name__ == "__main__":
    run()
