"""Run ONCE on your own computer (not Railway) to log in and get TG_SESSION.

    pip install telethon
    python make_session.py

It asks for your API ID, API hash, phone, and the login code Telegram sends you.
Copy the printed session text into Railway as TG_SESSION. Never share it with anyone.
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API ID: ").strip())
api_hash = input("API hash: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nYour TG_SESSION (keep it secret):\n")
    print(client.session.save())
