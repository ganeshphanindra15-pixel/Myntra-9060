"""
Myntra Size Monitor - Telegram Bot
Uses Myntra's mobile app API with rotating headers to check size availability.
No paid proxy needed.
"""

import os
import requests
import schedule
import time
import logging
import random
from datetime import datetime

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID    = os.environ.get("CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

PRODUCT_ID             = "28873290"
TARGET_SIZE            = "9"
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))
# ──────────────────────────────────────────────────────────────────────────────

PRODUCT_URL = f"https://www.myntra.com/{PRODUCT_ID}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

_last_notified_available = None

# Myntra Android app device fingerprints
DEVICES = [
    {
        "User-Agent": "MyApp/5.3.2 (Linux; Android 13; SM-G991B Build/TP1A.220624.014)",
        "x-device-id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "x-device-os": "android",
        "x-app-version": "5.3.2",
    },
    {
        "User-Agent": "MyApp/5.3.1 (Linux; Android 12; Pixel 6 Build/SQ3A.220705.004)",
        "x-device-id": "b2c3d4e5-f6a7-8901-bcde-f01234567891",
        "x-device-os": "android",
        "x-app-version": "5.3.1",
    },
    {
        "User-Agent": "MyApp/5.2.9 (Linux; Android 14; OnePlus 11 Build/14.0.0.300)",
        "x-device-id": "c3d4e5f6-a7b8-9012-cdef-012345678902",
        "x-device-os": "android",
        "x-app-version": "5.2.9",
    },
]

def get_headers():
    device = random.choice(DEVICES)
    return {
        **device,
        "Accept": "application/json",
        "Accept-Language": "en-IN",
        "x-location-code": random.choice(["560001", "400001", "500001", "600001"]),
        "x-myntraweb": "Yes",
        "Connection": "keep-alive",
    }


def fetch_via_api(session):
    """Try Myntra's product API endpoints."""
    endpoints = [
        f"https://www.myntra.com/gateway/v2/product/{PRODUCT_ID}",
        f"https://www.myntra.com/gateway/v2/product/{PRODUCT_ID}/sizechart",
    ]
    for url in endpoints:
        try:
            r = session.get(url, headers=get_headers(), timeout=20)
            log.info(f"[{url.split('/')[-1]}] Status: {r.status_code} | Length: {len(r.text)}")
            if r.status_code == 200 and r.text.strip().startswith("{"):
                return r.json()
        except Exception as e:
            log.warning(f"Endpoint failed: {e}")
    return None


def fetch_product_data():
    """Create a session, warm it up with a homepage visit, then fetch product."""
    session = requests.Session()
    try:
        # Warm up: visit homepage first to get cookies (mimics real browser)
        log.info("Warming up session...")
        session.get(
            "https://www.myntra.com/",
            headers={
                "User-Agent": random.choice(DEVICES)["User-Agent"],
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-IN,en;q=0.9",
            },
            timeout=15,
        )
        time.sleep(random.uniform(1.5, 3.0))  # human-like delay
    except Exception as e:
        log.warning(f"Warmup failed (continuing anyway): {e}")

    return fetch_via_api(session)


def parse_sizes(data):
    if not data:
        return [], "Unknown Product"
    for key in ["style", "data", ""]:
        obj = data.get(key, data) if key else data
        if isinstance(obj, dict) and "sizes" in obj:
            return obj["sizes"], obj.get("name", "Product")
    return [], data.get("name", "Product")


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=10)
        r.raise_for_status()
        log.info("Telegram notification sent.")
    except Exception as e:
        log.error(f"Telegram error: {e}")


def check_size_availability():
    global _last_notified_available

    log.info(f"Checking size {TARGET_SIZE} for product {PRODUCT_ID}...")
    data = fetch_product_data()

    if not data:
        log.warning("Could not fetch product data — will retry next interval.")
        return

    sizes, name = parse_sizes(data)
    log.info(f"Product: {name} | Sizes found: {[s.get('label') for s in sizes]}")

    size_entry = next(
        (s for s in sizes if str(s.get("label", "")).strip() == TARGET_SIZE), None
    )

    if size_entry is None:
        log.info(f"Size {TARGET_SIZE} not listed.")
        if _last_notified_available is not False:
            send_telegram(
                f"⚠️ <b>Size {TARGET_SIZE} not in size chart</b>\n"
                f"<b>{name}</b>\n{PRODUCT_URL}"
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
