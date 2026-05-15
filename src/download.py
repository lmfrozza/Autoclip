from config import logger, pipeline
import os
import json
import pandas as pd
import yt_dlp

def download_clip(url: str, clip_id: str, output_dir:str = "data/raw"):
    ydl_opts = {
        "outtmpl": f"{output_dir}/{clip_id}.%(ext)s",
        "quiet": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def run():

  # LOAD INFO 
    df = pd.read_json("data/gold.json")
    DOWNLOAD_CAP = pipeline.get("download_cap", 5)  
    logger.info(f"Selected {DOWNLOAD_CAP}/{len(df)}")
    df = df.head(DOWNLOAD_CAP)

  # SET DIRECTORY
    os.makedirs("data/raw", exist_ok=True)
  
  # DOWNLOAD SELECTED CLIPS
    for _, row in df.iterrows():
        logger.info(f"Downloading: {row['title']}")
        download_clip(url=row["url"], clip_id=row["id"])
        
if __name__ == "__main__":
    run()

