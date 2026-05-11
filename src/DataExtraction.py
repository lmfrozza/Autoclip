import requests
from datetime import datetime, timedelta, timezone
import os

def ListTwitchClips(streamer: str, range: int) -> list[str]:
    client_id = os.getenv("TWITCH_CLIENT_ID")
    access_token = os.getenv("TWITCH_ACCESS_TOKEN")

    if not client_id or not access_token:
        raise EnvironmentError("TWITCH_CLIENT_ID and TWITCH_ACCESS_TOKEN must be set in environment variables.")

    headers = {
        "Client-Id": client_id,
        "Authorization": f"Bearer {access_token}",
    }

    # Resolve broadcaster_id from login name
    user_resp = requests.get(
        "https://api.twitch.tv/helix/users",
        headers=headers,
        params={"login": streamer.lower()},
    )
    user_resp.raise_for_status()
    users = user_resp.json().get("data", [])

    if not users:
        raise ValueError(f"Streamer '{streamer}' not found on Twitch.")

    broadcaster_id = users[0]["id"]

    # Calculate the start date based on the range
    started_at = (datetime.now(timezone.utc) - timedelta(days=range)).isoformat()

    # Fetch clips, paginating through all results
    clip_urls = []
    cursor = None

    while True:
        params = {
            "broadcaster_id": broadcaster_id,
            "started_at": started_at,
            "first": 100,  # max per request
        }
        if cursor:
            params["after"] = cursor

        clips_resp = requests.get(
            "https://api.twitch.tv/helix/clips",
            headers=headers,
            params=params,
        )
        clips_resp.raise_for_status()
        data = clips_resp.json()

        for clip in data.get("data", []):
            clip_urls.append(clip["url"])

        cursor = data.get("pagination", {}).get("cursor")
        if not cursor:
            break

    return clip_urls


if __name__ == "__main__":
    response = ListTwitchClips(streamer="Coringa", range=1)
    for url in response:
        print(url)
