from config import logger, pipeline
import os
import json
import pandas as pd
import yt_dlp
from faster_whisper import WhisperModel

def download_clip(url: str, clip_id: str, output_dir:str = "data/raw"):
  ydl_opts = {
    "outtmpl": f"{output_dir}/{clip_id}.%(ext)s",
    "quiet": True
  }
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])

def _get_subtitles(dir: str = "data/raw"):
  model = WhisperModel("turbo", device="cpu", compute_type="int8")

  video_files = [f for f in os.listdir(dir) if f.endswith(".mp4")]
  logger.info(f"Transcribing {len(video_files)} video(s) in {dir}...")

  for filename in video_files:
    video_path = os.path.join(dir, filename)
    clip_id = os.path.splitext(filename)[0]
    srt_path = os.path.join(dir, f"{clip_id}.srt")

    logger.info(f"Transcribing: {filename}")
    segments, info = model.transcribe(
      video_path,
      language="pt",
      vad_filter=True,
      beam_size=5,
    )
    logger.info(f"Language detected: {info.language} ({info.language_probability:.0%})")

    segments = list(segments)

    with open(srt_path, "w", encoding="utf-8") as srt_file:
      for i, segment in enumerate(segments, start=1):
        start = _format_srt_time(segment.start)
        end = _format_srt_time(segment.end)
        srt_file.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")

    logger.info(f"Subtitles saved: {srt_path}")


def _format_srt_time(seconds: float) -> str:
  hours = int(seconds // 3600)
  minutes = int((seconds % 3600) // 60)
  secs = int(seconds % 60)
  millis = int((seconds % 1) * 1000)
  return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
  
def run():

  # LOAD INFO 
  df = pd.read_json("data/gold.json")
  DOWNLOAD_CAP = pipeline.get("download_cap", 5)  
  logger.info(f"Selected {DOWNLOAD_CAP}/{len(df)}")
  df = df.head(DOWNLOAD_CAP)

  # SET DIRECTORY
  os.makedirs("data/raw", exist_ok=True)
  
  # DOWNLOAD SELECTED CLIPS
  try:
    for _, row in df.iterrows():
      logger.info(f"Downloading: {row['title']}")
      download_clip(url=row["url"], clip_id=row["id"])
  except:
    raise ValueError("Error trying to download clips")    
  finally:
    _get_subtitles()

if __name__ == "__main__":
  run()

