import os
import json
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Load .env explicitly so SLACK_BOT_TOKEN is available even when this module
# is imported before the main app's load_dotenv() call (e.g. notification_service.py)
load_dotenv()


class SlackClient:
    """Simple wrapper around slack_sdk.WebClient to send messages to a channel."""

    def __init__(self):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.channel_id = os.getenv("SLACK_CHANNEL_ID")
        self.enabled = bool(self.bot_token and self.channel_id)
        if self.enabled:
            self.client = WebClient(token=self.bot_token)
        else:
            print("[Slack] Integration disabled (tokens missing in .env)")
            self.client = None

    def send_message(self, text: str) -> None:
        if not self.enabled or not self.client:
            return
        try:
            self.client.chat_postMessage(channel=self.channel_id, text=text)
        except SlackApiError as e:
            # Log the error; in production you might want a proper logger
            print(f"[Slack] Failed to send message: {e.response['error']}")
