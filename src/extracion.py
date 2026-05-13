from controllers.twitch import TwitchController
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from config import logger
import pandas as pd
import os
import json

load_dotenv()

controller = TwitchController(
    client_id=os.getenv("TWITCH_CLIENT_ID"),
    client_secret=os.getenv("TWITCH_CLIENT_SECRET")
)

def _fetch_clips_for_streamer(streamer: str, range: int) -> list[dict]:
    """Fetches clips for a single streamer. Designed to run in parallel."""
    response = controller.get_streamer_by_login(streamer=streamer)
    clips = controller.get_clips(streamer_id=response[0]["id"], range=range)
    return clips

def bronze(range: int = 5, max_workers: int = 5):
    logger.info("Starting bronze stage...")

    with open("data/streamers.txt", "r") as f:
        streamers = [line.strip() for line in f if line.strip()]
    logger.info(f"{len(streamers)} streamers loaded from data/streamers.txt.")

    all_clips = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_clips_for_streamer, s, range): s for s in streamers}
        for future in as_completed(futures):
            streamer = futures[future]
            try:
                clips = future.result()
                all_clips.extend(clips)
                logger.info(f"[OK] {streamer}: {len(clips)} clips fetched.")
            except Exception as e:
                logger.error(f"[ERRO] {streamer}: {e}")

    if not all_clips:
        logger.warning("No clips found. Skipping file write.")
        return

    output_path = "data/bronze.json"
    os.makedirs("data", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_clips, f, ensure_ascii=False, indent=2)

    logger.info(f"Bronze stage complete: {len(all_clips)} clips saved to {output_path}.")


medallion = [bronze]


if __name__ == "__main__":
    for stage in medallion:
        stage()
