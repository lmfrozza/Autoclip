import requests
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from config import logger


class TwitchController:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        logger.debug("TwitchController initialized.")
        self.access_token = self._get_acess_token()

    def _get_acess_token(self):
        logger.debug("Requesting access token...")
        url = 'https://id.twitch.tv/oauth2/token'
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url=url, data=data)
        response.raise_for_status()
        logger.info("Access token generated successfully.")
        return response.json()["access_token"]

    def get_streamer_by_login(self, streamer: str) -> list[dict]:
        logger.debug(f"Fetching streamer info for '{streamer}'...")
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
            logger.warning(f"Streamer '{streamer}' not found on Twitch.")
            raise ValueError(f"Streamer '{streamer}' not found on Twitch.")
        logger.info(f"Streamer '{streamer}' found (id={users[0]['id']}).")
        return users

    def get_clips(self, streamer_id: str, range: int) -> list[dict]:
        logger.debug(f"Fetching clips for streamer_id={streamer_id}, range={range}d...")
        started_at = (datetime.now(timezone.utc) - timedelta(days=range)).isoformat()
        all_clips = []
        cursor = None
        headers = {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
        }
        while True:
            params = {
                "broadcaster_id": streamer_id,
                "started_at": started_at,
                "first": 100,
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

            batch = data.get("data", [])
            all_clips.extend(batch)
            logger.debug(f"Fetched {len(batch)} clips (total so far: {len(all_clips)}).")

            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break

        logger.info(f"Finished fetching clips for streamer_id={streamer_id}: {len(all_clips)} total.")
        return all_clips


if __name__ == "__main__":
    load_dotenv()
    controller = TwitchController(
        client_id=os.getenv("TWITCH_CLIENT_ID"),
        client_secret=os.getenv("TWITCH_CLIENT_SECRET")
    )
    streamers = controller.get_streamer_by_login(streamer="cellbit")
    clips = controller.get_clips(streamer_id=streamers[0]["id"], range=1)
    print(clips)
