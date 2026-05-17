import os
import re
import subprocess
import tempfile
from multiprocessing import Pool, cpu_count
from config import logger, watermark
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# --- Reels target resolution (9:16) ---
REELS_W = 1080
REELS_H = 1920

# --- Subtitle style (ASS format) ---
FONT_NAME = "DejaVu Sans Bold"
FONT_SIZE = 72
COLOR_SPOKEN  = "&H00FFFFFF"   # white  (ASS: &HAABBGGRR)
COLOR_CURRENT = "&H0000DCFF"   # yellow
COLOR_UPCOMING = "&H00C8C8C8"  # light gray
OUTLINE_COLOR = "&H00000000"   # black outline
OUTLINE_SIZE = 3
SUBTITLE_Y_MARGIN = int(REELS_H * 0.12)  # margin from bottom


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

def _detect_encoder() -> str:
    """
    Try hardware encoders in order of preference.
    Returns the first one FFmpeg can actually use, falls back to libx264.
    """
    candidates = [
        ("h264_nvenc",  ["-f", "lavfi", "-i", "nullsrc=s=64x64:d=1", "-c:v", "h264_nvenc",  "-f", "null", "-"]),
        ("h264_amf",    ["-f", "lavfi", "-i", "nullsrc=s=64x64:d=1", "-c:v", "h264_amf",    "-f", "null", "-"]),
        ("h264_qsv",    ["-f", "lavfi", "-i", "nullsrc=s=64x64:d=1", "-c:v", "h264_qsv",    "-f", "null", "-"]),
    ]
    for name, args in candidates:
        try:
            result = subprocess.run(
                [FFMPEG, "-y", *args],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info(f"Hardware encoder detected: {name}")
                return name
        except Exception:
            pass
    logger.info("No hardware encoder found, using libx264 (CPU).")
    return "libx264"


# Detect once at module load so workers inherit the value
ENCODER = _detect_encoder()


# ---------------------------------------------------------------------------
# SRT parsing
# ---------------------------------------------------------------------------

def _parse_srt(srt_path: str) -> list[dict]:
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
        end   = _srt_time_to_seconds(time_match.group(2))
        text  = " ".join(lines[2:]).strip()
        subtitles.append({"start": start, "end": end, "text": text})

    return subtitles


def _srt_time_to_seconds(t: str) -> float:
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _seconds_to_ass_time(t: float) -> str:
    h  = int(t // 3600)
    m  = int((t % 3600) // 60)
    s  = int(t % 60)
    cs = int((t % 1) * 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


# ---------------------------------------------------------------------------
# ASS subtitle generation with karaoke effect
# ---------------------------------------------------------------------------

def _build_ass(subtitles: list[dict]) -> str:
    """
    Build an ASS subtitle file with word-level karaoke coloring.

    Strategy per subtitle line:
      - Words already spoken: COLOR_SPOKEN
      - Current word: COLOR_CURRENT  (highlighted via \\c color override)
      - Upcoming words: COLOR_UPCOMING

    We emit one ASS Dialogue line per subtitle entry.
    Inside each line we use inline color overrides (\\c) per word,
    and \\k tags to drive timing so the highlight advances word by word.
    """
    ass_header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {REELS_W}
PlayResY: {REELS_H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{FONT_SIZE},{COLOR_UPCOMING},{COLOR_CURRENT},{OUTLINE_COLOR},&H00000000,-1,0,0,0,100,100,0,0,1,{OUTLINE_SIZE},0,2,10,10,{SUBTITLE_Y_MARGIN},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []

    for sub in subtitles:
        words = sub["text"].split()
        if not words:
            continue

        start  = sub["start"]
        end    = sub["end"]
        duration = end - start

        # Distribute time proportionally by character count
        char_counts   = [max(len(w), 1) for w in words]
        total_chars   = sum(char_counts)
        word_durations = [(c / total_chars) * duration for c in char_counts]

        # Build ASS karaoke text
        # \\k<N> = karaoke tag, N = centiseconds for this syllable
        # \\c&HCOLOR& = primary color override for following text
        # We color each word individually:
        #   before highlight: COLOR_SPOKEN via \\c
        #   at highlight:     COLOR_CURRENT via \\c  (\\k advances the highlight)
        #   after highlight:  COLOR_UPCOMING (default style color)
        #
        # ASS karaoke works by advancing through \\k tags sequentially.
        # We use \\kf (fill) for a smooth highlight sweep per word.

        text_parts = []
        for i, (word, dur) in enumerate(zip(words, word_durations)):
            k_cs = max(1, int(round(dur * 100)))  # centiseconds
            # \\kf<N> advances the highlight; color before = spoken, during = current
            text_parts.append(
                f"{{\\kf{k_cs}\\c{COLOR_CURRENT}}}{word}"
            )

        # Join with spaces; reset color to upcoming after each word via \\c
        # Actually with \\kf the color transitions automatically via SecondaryColour→PrimaryColour
        # But we want: spoken=white, current=yellow, upcoming=gray
        # The cleanest way: use \\1c (primary) and \\2c (secondary/karaoke fill)
        # PrimaryColour = upcoming (gray), SecondaryColour = current (yellow)
        # Before \\k fires: text shows in PrimaryColour (gray/upcoming)
        # While \\kf fires: text fills from SecondaryColour (yellow) → PrimaryColour
        # After \\k: text stays PrimaryColour (gray) — but we want white for spoken
        #
        # To get spoken=white we need a different approach:
        # Emit one Dialogue line per word, coloring the full phrase each time.

        # --- Better approach: one Dialogue line per word window ---
        # Each line shows the full phrase with correct colors for that moment.
        # This is heavier in the ASS file but renders correctly.
        word_start = start
        for i, (word, dur) in enumerate(zip(words, word_durations)):
            word_end = word_start + dur
            phrase_parts = []
            for j, w in enumerate(words):
                if j < i:
                    phrase_parts.append(f"{{\\c{COLOR_SPOKEN}}}{w}")
                elif j == i:
                    phrase_parts.append(f"{{\\c{COLOR_CURRENT}}}{w}")
                else:
                    phrase_parts.append(f"{{\\c{COLOR_UPCOMING}}}{w}")
            text = " ".join(phrase_parts)
            s_time = _seconds_to_ass_time(word_start)
            e_time = _seconds_to_ass_time(word_end)
            lines.append(
                f"Dialogue: 0,{s_time},{e_time},Default,,0,0,0,,{text}"
            )
            word_start = word_end

    return ass_header + "\n".join(lines) + "\n"


def _process_clip(args: tuple) -> None:
    video_path, srt_path, output_path, encoder = args

    clip_name = os.path.basename(video_path)
    logger.info(f"[{clip_name}] Starting (encoder={encoder})")

    # --- Build ASS subtitle file ---
    ass_content = None
    if os.path.exists(srt_path):
        subtitles = _parse_srt(srt_path)
        ass_content = _build_ass(subtitles)

    with tempfile.TemporaryDirectory() as tmpdir:
        ass_path = None
        if ass_content:
            ass_path = os.path.join(tmpdir, "subs.ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

        # --- Watermark config ---
        wm_path    = watermark.get("path", "")
        wm_exists  = bool(wm_path and os.path.exists(wm_path))
        wm_w       = int(REELS_W * float(watermark.get("scale", 0.15)))
        opacity    = float(watermark.get("opacity", 0.8))
        position   = watermark.get("position", "top-right")
        margin     = int(watermark.get("margin", 40))

        if position == "top-right":
            ox, oy = f"W-w-{margin}", str(margin)
        elif position == "top-left":
            ox, oy = str(margin), str(margin)
        elif position == "bottom-right":
            ox, oy = f"W-w-{margin}", f"H-h-{margin}"
        else:  # bottom-left
            ox, oy = str(margin), f"H-h-{margin}"

        # --- Subtitle filter string ---
        subs_filter = None
        if ass_path:
            escaped = ass_path.replace("\\", "/").replace(":", "\\:")
            subs_filter = f"subtitles='{escaped}'"

        scale_pad = (
            f"scale={REELS_W}:-2,"
            f"pad={REELS_W}:{REELS_H}:(ow-iw)/2:(oh-ih)/2:black"
        )

        # --- Build FFmpeg command ---
        # With watermark: must use -filter_complex (two inputs)
        # Without watermark: simpler -vf chain
        if wm_exists:
            # [0:v] → scale+pad → [base]
            # [1:v] → scale+opacity → [wm]
            # [base][wm] → overlay → [out]
            # [out] → subtitles (optional) → [final]
            fc = (
                f"[0:v]{scale_pad}[base];"
                f"[1:v]scale={wm_w}:-1,format=rgba,colorchannelmixer=aa={opacity:.2f}[wm];"
                f"[base][wm]overlay={ox}:{oy}[out]"
            )
            if subs_filter:
                fc += f";[out]{subs_filter}[final]"
                map_v = "[final]"
            else:
                map_v = "[out]"

            cmd = [
                FFMPEG, "-y",
                "-i", video_path,
                "-i", wm_path,
                "-filter_complex", fc,
                "-map", map_v,
                "-map", "0:a",
            ]
        else:
            vf = scale_pad
            if subs_filter:
                vf += f",{subs_filter}"
            cmd = [
                FFMPEG, "-y",
                "-i", video_path,
                "-vf", vf,
            ]

        # --- Encoder options ---
        if encoder == "libx264":
            enc_opts = ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
        elif encoder == "h264_nvenc":
            enc_opts = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"]
        elif encoder == "h264_amf":
            enc_opts = ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23"]
        elif encoder == "h264_qsv":
            enc_opts = ["-c:v", "h264_qsv", "-preset", "medium", "-global_quality", "23"]
        else:
            enc_opts = ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]

        cmd += [
            *enc_opts,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info(f"[{clip_name}] Running FFmpeg (watermark={'yes' if wm_exists else 'no'})...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"[{clip_name}] FFmpeg failed:\n{result.stderr}")
            raise RuntimeError(f"FFmpeg failed for {clip_name}")

    logger.info(f"[{clip_name}] Done → {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    os.makedirs("data/edit", exist_ok=True)

    raw_dir  = "data/raw"
    mp4_files = sorted([f for f in os.listdir(raw_dir) if f.endswith(".mp4")])

    if not mp4_files:
        logger.warning("No .mp4 files found in data/raw. Skipping edit stage.")
        return

    logger.info(f"Found {len(mp4_files)} clip(s). Encoder: {ENCODER}")

    tasks = []
    for filename in mp4_files:
        clip_id    = os.path.splitext(filename)[0]
        video_path = os.path.join(raw_dir, filename)
        srt_path   = os.path.join(raw_dir, f"{clip_id}.srt")
        output_path = os.path.join("data/edit", filename)
        tasks.append((video_path, srt_path, output_path, ENCODER))

    # Use min(n_clips, cpu_count) workers — no point spawning more than clips
    workers = min(len(tasks), cpu_count())
    logger.info(f"Processing {len(tasks)} clip(s) with {workers} parallel worker(s).")

    if workers == 1:
        # Single clip: run directly (avoids multiprocessing overhead)
        _process_clip(tasks[0])
    else:
        with Pool(processes=workers) as pool:
            pool.map(_process_clip, tasks)

    logger.info("Edit stage complete.")


if __name__ == "__main__":
    run()
