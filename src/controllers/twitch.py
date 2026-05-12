import requests
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv


class TwitchController:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self._get_acess_token()
    def _get_acess_token(self):
        url = 'https://id.twitch.tv/oauth2/token'
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url=url, data=data) 
        response.raise_for_status()
        return response.json()["access_token"]
    def get_streamer_by_login(self, streamer: str) -> list[dict]:
        headers = {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
        }
        user_resp = requests.get(
            "https://api.twitch.tv/helix/users",
            headers=headers,
            params={"login": streamer.lower()},
        )
        user_resp.raise_for_status()
        users = user_resp.json().get("data", [])
        if not users:
            raise ValueError(f"Streamer '{streamer}' not found on Twitch.")
        return users
    def get_clips(self, streamer_id:str, range:int) -> list[dict]:
        started_at = (datetime.now(timezone.utc) - timedelta(days=range)).isoformat()
        clip_urls = []
        cursor = None
        headers = {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
        }
        while True:
            params = {
                "broadcaster_id": streamer_id,
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
                clip_urls.append(clip)

            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break
        return clip_urls

if __name__ == "__main__":
    load_dotenv()
    controller = TwitchController(
        client_id=os.getenv("TWITCH_CLIENT_ID"),
        client_secret=os.getenv("TWITCH_CLIENT_SECRET")
    )
    streamers = controller.get_streamer_by_login(streamer="cellbit")
    clips = controller.get_clips(streamer_id=streamers[0]["id"], range=1)
    print(clips)