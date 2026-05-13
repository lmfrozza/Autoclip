from controllers.twitch import TwitchController
import os
import json
from dotenv import load_dotenv
import pandas as pd

  

def bronze():
    os.remove("data/bronze.json")
    load_dotenv()
    controller = TwitchController(
        client_id=os.getenv("TWITCH_CLIENT_ID"),
        client_secret=os.getenv("TWITCH_CLIENT_SECRET")
    )

    with open("data/streamers.txt", "r") as f:
        streamers = [line.strip() for line in f if line.strip()]

    all_clips = []

    for streamer in streamers:
        response = controller.get_streamer_by_login(streamer=streamer)
        clips = controller.get_clips(streamer_id=response[0]["id"], range=5)
        all_clips.extend(clips)

    os.makedirs("data", exist_ok=True)
    with open("data/bronze.json", "w", encoding="utf-8") as f:
        json.dump(all_clips, f, ensure_ascii=False, indent=2)




medallion = [bronze]


if __name__ == "__main__":
    for stage in medallion:
        stage()