from config import logger, pipeline
import os
import pandas as pd
import yt_dlp
from multiprocessing import Pool, cpu_count
from faster_whisper import WhisperModel


# ---------------------------------------------------------------------------
# Device detection — use CUDA if available, fallback to CPU
# ---------------------------------------------------------------------------

def _detect_whisper_device() -> tuple[str, str]:
    """Returns (device, compute_type) for WhisperModel."""
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("Whisper: CUDA GPU detected, using float16.")
            return "cuda", "float16"
    except ImportError:
        pass
    logger.info("Whisper: No GPU found, using CPU int8.")
    return "cpu", "int8"


WHISPER_DEVICE, WHISPER_COMPUTE = _detect_whisper_device()


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_clip(url: str, clip_id: str, output_dir: str = "data/raw"):
    ydl_opts = {
        "outtmpl": f"{output_dir}/{clip_id}.%(ext)s",
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# ---------------------------------------------------------------------------
# Transcription — word-level timestamps
# ---------------------------------------------------------------------------

def _format_srt_time(seconds: float) -> str:
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    millis  = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _transcribe_clip(video_path: str, srt_path: str) -> None:
    """
    Transcribe a single clip and write a word-level .srt file.
    Each SRT entry = one word with its exact start/end timestamp.
    This gives the karaoke effect precise timing without approximation.
    """
    # Load model inside the worker so each process has its own instance
    model = WhisperModel("turbo", device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)

    logger.info(f"Transcribing: {os.path.basename(video_path)}")
    segments, info = model.transcribe(
        video_path,
        language="pt",
        vad_filter=True,
        beam_size=2,           # reduced from 5 — faster, negligible quality loss for PT-BR
        word_timestamps=True,  # key change: per-word timing
    )
    logger.info(
        f"[{os.path.basename(video_path)}] "
        f"Language: {info.language} ({info.language_probability:.0%})"
    )

    segments = list(segments)

    with open(srt_path, "w", encoding="utf-8") as srt_file:
        idx = 1
        for segment in segments:
            if not segment.words:
                # Fallback: no word timestamps available, write segment as-is
                start = _format_srt_time(segment.start)
                end   = _format_srt_time(segment.end)
                srt_file.write(f"{idx}\n{start} --> {end}\n{segment.text.strip()}\n\n")
                idx += 1
                continue

            for word in segment.words:
                text = word.word.strip()
                if not text:
                    continue
                start = _format_srt_time(word.start)
                end   = _format_srt_time(word.end)
                srt_file.write(f"{idx}\n{start} --> {end}\n{text}\n\n")
                idx += 1

    logger.info(f"Subtitles saved: {srt_path}")


def _transcribe_worker(args: tuple) -> None:
    video_path, srt_path = args
    _transcribe_clip(video_path, srt_path)


def _get_subtitles(directory: str = "data/raw") -> None:
    """Transcribe all .mp4 files in parallel, one worker per clip."""
    video_files = sorted([f for f in os.listdir(directory) if f.endswith(".mp4")])
    logger.info(f"Transcribing {len(video_files)} video(s) in {directory}...")

    tasks = []
    for filename in video_files:
        video_path = os.path.join(directory, filename)
        clip_id    = os.path.splitext(filename)[0]
        srt_path   = os.path.join(directory, f"{clip_id}.srt")
        tasks.append((video_path, srt_path))

    if not tasks:
        return

    # On CPU: parallelising Whisper across clips is faster than sequential
    # On GPU: Whisper uses the GPU per-call; parallel workers would contend,
    #         so limit to 1 worker when on CUDA to avoid OOM
    if WHISPER_DEVICE == "cuda":
        workers = 1
    else:
        workers = min(len(tasks), cpu_count())

    logger.info(f"Transcription workers: {workers} (device={WHISPER_DEVICE})")

    if workers == 1:
        for task in tasks:
            _transcribe_worker(task)
    else:
        with Pool(processes=workers) as pool:
            pool.map(_transcribe_worker, tasks)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    df = pd.read_json("data/gold.json")
    DOWNLOAD_CAP = pipeline.get("download_cap", 5)
    logger.info(f"Selected {DOWNLOAD_CAP}/{len(df)}")
    df = df.head(DOWNLOAD_CAP)

    os.makedirs("data/raw", exist_ok=True)

    try:
        for _, row in df.iterrows():
            logger.info(f"Downloading: {row['title']}")
            download_clip(url=row["url"], clip_id=row["id"])
    except Exception as e:
        raise ValueError(f"Error downloading clips: {e}")
    finally:
        _get_subtitles()


if __name__ == "__main__":
    run()
