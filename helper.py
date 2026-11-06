"""Always-on affiliate helper for the VIP Access Bot.

Picks up trader IDs waiting for a check (new verifications and 8-hour rechecks),
asks the affiliate bot about each one from your own Telegram account, and sends
the reply back to the app. Credentials come only from Railway variables.
"""
import asyncio
import logging
import os

import httpx
from telethon import TelegramClient
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("helper")


def need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing Railway variable: {name}")
    return value


API_ID = int(need("TG_API_ID"))
API_HASH = need("TG_API_HASH")
SESSION = need("TG_SESSION")
AFFILIATE_BOT = need("AFFILIATE_BOT")
APP_URL = need("APP_URL").rstrip("/")
SECRET = need("VERIFIER_SECRET")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "5"))
REPLY_TIMEOUT = int(os.environ.get("REPLY_TIMEOUT", "40"))

HEADERS = {"X-Verifier-Secret": SECRET}


async def report(http: httpx.AsyncClient, status: str) -> None:
    try:
        await http.post(f"{APP_URL}/api/public/telegram/bridge", json={"status": status}, headers=HEADERS)
    except httpx.HTTPError as err:
        log.warning("status report failed: %s", err)


async def ask_affiliate(client: TelegramClient, trader_id: str) -> str | None:
    async with client.conversation(AFFILIATE_BOT, timeout=REPLY_TIMEOUT, exclusive=True) as conv:
        await conv.send_message(trader_id)
        # Some affiliate bots send a short "searching" note first; keep the reply that mentions the ID.
        for _ in range(3):
            try:
                msg = await conv.get_response()
            except asyncio.TimeoutError:
                return None
            text = msg.raw_text or ""
            if trader_id in text or "not found" in text.lower() or "deleted" in text.lower():
                return text
        return None


async def main() -> None:
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("TG_SESSION is not valid. Run make_session.py again on your computer.")
    log.info("helper online")

    async with httpx.AsyncClient(timeout=30) as http:
        while True:
            await report(http, "online")
            try:
                r = await http.get(f"{APP_URL}/api/public/telegram/pending-requests", headers=HEADERS)
                r.raise_for_status()
                requests = r.json().get("requests", [])
            except httpx.HTTPError as err:
                log.warning("could not fetch pending checks: %s", err)
                requests = []

            for req in requests:
                trader_id = str(req["trader_id"]).strip()
                reply = await ask_affiliate(client, trader_id)
                if reply is None:
                    # No reply: leave it pending so it is retried; never treated as low balance.
                    log.warning("no affiliate reply for a %s check", req.get("kind"))
                    continue
                try:
                    await http.post(
                        f"{APP_URL}/api/public/telegram/verify-result",
                        json={"request_id": req["id"], "affiliate_reply": reply[:4000]},
                        headers=HEADERS,
                    )
                except httpx.HTTPError as err:
                    log.warning("could not send result: %s", err)
                await asyncio.sleep(2)  # be gentle with the affiliate bot

            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
