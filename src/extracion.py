from controllers.twitch import TwitchController
from config import logger
import os
import json
from dotenv import load_dotenv
import pandas as pd


def bronze():
    logger.info("Starting bronze stage...")
    try:
        os.remove("data/bronze.json")
    except:
        logger.info("No bronze table founded")
    load_dotenv()
    controller = TwitchController(
        client_id=os.getenv("TWITCH_CLIENT_ID"),
        client_secret=os.getenv("TWITCH_CLIENT_SECRET")
    )

    with open("data/streamers.txt", "r") as f:
        streamers = [line.strip() for line in f if line.strip()]
    logger.info(f"{len(streamers)} streamers loaded.")

    all_clips = []

    for streamer in streamers:
        logger.debug(f"Fetching clips for '{streamer}'...")
        response = controller.get_streamer_by_login(streamer=streamer)
        clips = controller.get_clips(streamer_id=response[0]["id"], range=5)
        all_clips.extend(clips)
        logger.info(f"[{streamer}] {len(clips)} clips fetched.")

    os.makedirs("data", exist_ok=True)
    with open("data/bronze.json", "w", encoding="utf-8") as f:
        json.dump(all_clips, f, ensure_ascii=False, indent=2)
    logger.info(f"Bronze stage complete: {len(all_clips)} total clips saved to data/bronze.json.")

def silver():
    logger.info("Starting silver stage...")
    try:
        os.remove("data/silver.json")
    except:
        logger.info("No silver table founded")
    df = pd.read_json("data/bronze.json")
    logger.info(f"Loaded {len(df)} clips from bronze.")

    # --- Limpeza ---
    before = len(df)
    df = df.drop_duplicates(subset="id")
    df = df[df["view_count"] > 0]
    df["game_id"] = df["game_id"].replace("", None)
    logger.info(f"Removed {before - len(df)} rows (duplicates + zero views).")

    # --- Tipagem ---
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["duration"] = df["duration"].astype(float)

    # --- Enriquecimento ---
    now = pd.Timestamp.now(tz="UTC")
    df["created_date"] = df["created_at"].dt.date
    df["created_hour"] = df["created_at"].dt.hour
    df["clip_age_days"] = (now - df["created_at"]).dt.days

    # --- Remover colunas desnecessárias ---
    df = df.drop(columns=["embed_url", "thumbnail_url", "vod_offset"])

    os.makedirs("data", exist_ok=True)
    df.to_json("data/silver.json", orient="records", force_ascii=False, indent=2, date_format="iso")
    logger.info(f"Silver stage complete: {len(df)} clips saved to data/silver.json.")

def gold():
    logger.info("Starting gold stage...")
    try:
        os.remove("data/gold.json")
    except:
        logger.info("No gold table founded")

    df = pd.read_json("data/silver.json")
    logger.info(f"Loaded {len(df)} clips from silver.")

    # REMOVE SHORT VIDEOS
    logger.info(f'Removing {len(df[df['duration']<15])} that are too short!')
    df = df[df['duration']>=15]

    # REMOVE LONG VIDEOS
    logger.info(f'Removing {len(df[df['duration']>60])} that are too long!')
    df = df[df['duration']<=60]

    logger.info(f'{len(df)} videos are in between the "sweet spot"!')
    df_sorted = df.sort_values(by='view_count', ascending=False)
    print(df_sorted.head())

medallion = [bronze, silver,gold]

if __name__ == "__main__":
    #for stage in medallion:
    #    stage()
    gold()