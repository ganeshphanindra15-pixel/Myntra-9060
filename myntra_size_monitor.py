"""
Myntra Size Monitor - Telegram Bot
Monitors product 28873290 for Size 9 availability and notifies via Telegram.
"""

import os
import requests
import schedule
import time
import logging
from datetime import datetime

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

PRODUCT_ID             = "28873290"
TARGET_SIZE            = "9"
CHECK_INTERVAL_MINUTES = 10
# ──────────────────────────────────────────────────────────────────────────────

PRODUCT_URL = f"https://www.myntra.com/{PRODUCT_ID}"

# Try multiple API endpoints — Myntra blocks some from cloud IPs
API_ENDPOINTS = [
    f"https://www.myntra.com/gateway/v2/product/{PRODUCT_ID}",
    f"https://www.myntra.com/gateway/v1/product/{PRODUCT_ID}/inventory",
    f"https://api.myntra.com/v2/catalog/products/{PRODUCT_ID}",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# Rotate through different User-Agent strings to avoid blocks
USER_AGENTS = [
    # Android app UA (least likely to be blocked)
    "com.myntra.android/5.2.9 (Android 13; Samsung SM-G991B)",
    # iOS app UA
    "Myntra/5.2.9 CFNetwork/1492.0.1 Darwin/23.3.0",
    # Desktop browser
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Mobile browser
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Mobile Safari/537.36",
]

_ua_index = 0
_last_notified_available = None


def get_headers():
    """Rotate User-Agent on each call."""
    global _ua_index
    ua = USER_AGENTS[_ua_index % len(USER_AGENTS)]
    _ua_index += 1
    return {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer": "https://www.myntra.com/",
        "Origin": "https://www.myntra.com",
        "x-myntraweb": "Yes",
        "x-location-code": "560001",   # Bangalore pincode — helps with inventory
    }


def fetch_product_data():
    """Try each API endpoint until one works."""
    for url in API_ENDPOINTS:
        try:
            log.info(f"Trying endpoint: {url}")
            r = requests.get(url, headers=get_headers(), timeout=20)
            if r.status_code == 200:
                log.info("Got a response!")
                return r.json()
            else:
                log.warning(f"Status {r.status_code} from {url}")
        except Exception as e:
            log.warning(f"Failed {url}: {e}")
    return None


def parse_sizes(data):
    """Extract sizes list from various Myntra response formats."""
    if not data:
        return [], "Unknown Product"

    # Format 1: { "style": { "name": ..., "sizes": [...] } }
    if "style" in data:
        style = data["style"]
        return style.get("sizes", []), style.get("name", "Product")

    # Format 2: { "name": ..., "sizes": [...] }
    if "sizes" in data:
        return data["sizes"], data.get("name", "Product")

    # Format 3: { "data": { ... } }
    if "data" in data:
        inner = data["data"]
        return inner.get("sizes", []), inner.get("name", "Product")

    return [], "Product"


def send_telegram(message: str):
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        log.info("Telegram notification sent.")
    except Exception as e:
        log.error(f"Failed to send Telegram message: {e}")


def check_size_availability():
    global _last_notified_available

    log.info(f"Checking size {TARGET_SIZE} for product {PRODUCT_ID}...")
    data = fetch_product_data()

    if not data:
        log.warning("All endpoints failed — Myntra is blocking this IP. Will retry next interval.")
        return

    sizes, name = parse_sizes(data)
    log.info(f"Product: {name} | Sizes found: {[s.get('label') for s in sizes]}")

    size_entry = next((s for s in sizes if str(s.get("label", "")).strip() == TARGET_SIZE), None)

    if size_entry is None:
        log.info(f"Size {TARGET_SIZE} not listed.")
        if _last_notified_available is not False:
            send_telegram(
                f"⚠️ <b>Size {TARGET_SIZE} not found</b> in size chart\n"
                f"<b>{name}</b>\n{PRODUCT_URL}\n\n"
                f"It may not be offered in this size yet."
            )
            _last_notified_available = False
        return

    is_available = size_entry.get("available", False)
    log.info(f"Size {TARGET_SIZE} available: {is_available}")

    if is_available and _last_notified_available is not True:
        send_telegram(
            f"✅ <b>Size {TARGET_SIZE} is NOW AVAILABLE!</b>\n\n"
            f"👟 <b>{name}</b>\n"
            f"🛒 <a href='{PRODUCT_URL}'>Buy now on Myntra</a>\n\n"
            f"⏰ {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
        )
        _last_notified_available = True

    elif not is_available and _last_notified_available is True:
        send_telegram(
            f"❌ <b>Size {TARGET_SIZE} is no longer available</b>\n\n"
            f"👟 <b>{name}</b>\n"
            f"🔔 Watching for it to come back..."
        )
        _last_notified_available = False
    else:
        log.info("No state change — skipping notification.")


def main():
    log.info("=" * 50)
    log.info("Myntra Size Monitor started")
    log.info(f"Product : {PRODUCT_URL}")
    log.info(f"Size    : {TARGET_SIZE}")
    log.info(f"Interval: every {CHECK_INTERVAL_MINUTES} minutes")
    log.info("=" * 50)

    check_size_availability()

    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_size_availability)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
