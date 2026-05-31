"""
Myntra Size Monitor - Telegram Bot
Monitors product 28873290 for Size 9 availability and notifies via Telegram.
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

PRODUCT_URL = "https://www.myntra.com/28873290"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

_last_notified_available = None

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
    endpoints = [
        "https://www.myntra.com/gateway/v2/product/28873290",
        "https://www.myntra.com/gateway/v2/product/28873290/sizechart",
    ]
    for url in endpoints:
        try:
            r = session.get(url, headers=get_headers(), timeout=20)
            log.info("Status: " + str(r.status_code) + " | Length: " + str(len(r.text)))
            if r.status_code == 200 and r.text.strip().startswith("{") and len(r.text) > 1000:
                return r.json()
            elif r.status_code == 200 and len(r.text) <= 1000:
                log.warning("Response too small, retrying with delay...")
                time.sleep(random.uniform(4.0, 8.0))
        except Exception as e:
            log.warning("Endpoint failed: " + str(e))
    return None

def fetch_product_data():
    session = requests.Session()
    try:
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
        time.sleep(random.uniform(1.5, 3.0))
    except Exception as e:
        log.warning("Warmup failed: " + str(e))
    return fetch_via_api(session)

def parse_sizes(data):
    if not data:
        return [], "Unknown Product"
    for key in ["style", "data", ""]:
        obj = data.get(key, data) if key else data
        if isinstance(obj, dict) and "sizes" in obj:
            return obj["sizes"], obj.get("name", "Product")
    return [], "Product"

def send_telegram(message):
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        }, timeout=10)
        r.raise_for_status()
        log.info("Telegram notification sent.")
    except Exception as e:
        log.error("Telegram error: " + str(e))

def check_size_availability():
    global _last_notified_available
    log.info("Checking size 9 for product 28873290...")
    data = fetch_product_data()
    if not data:
        log.warning("Could not fetch product data, will retry next interval.")
        return

    sizes, name = parse_sizes(data)
    log.info("Sizes found: " + str([s.get("label") for s in sizes]))

    size_entry = None
    for s in sizes:
        if str(s.get("label", "")).strip() == "9":
            size_entry = s
            break

    if size_entry is None:
        log.info("Size 9 not listed.")
        if _last_notified_available is not False:
            send_telegram("Size 9 not found in size chart\nNew Balance Men Woven Design 9060 Sneakers\n" + PRODUCT_URL)
            _last_notified_available = False
        return

    is_available = size_entry.get("available", False)
    log.info("Size 9 available: " + str(is_available))

    if is_available and _last_notified_available is not True:
        msg = (
            "Size 9 is NOW AVAILABLE!\n"
            "New Balance Men Woven Design 9060 Sneakers\n"
            "Buy now: " + PRODUCT_URL + "\n"
            "Checked at: " + datetime.now().strftime("%d %b %Y %I:%M %p")
        )
        log.info("Sending message: " + msg)
        send_telegram(msg)
        _last_notified_available = True

    elif not is_available and _last_notified_available is True:
        send_telegram("Size 9 is no longer available\nWill notify when it is back!")
        _last_notified_available = False
    else:
        log.info("No state change, skipping notification.")

def main():
    log.info("==================================================")
    log.info("Myntra Size Monitor started")
    log.info("Product: " + PRODUCT_URL)
    log.info("Size: 9")
    log.info("Interval: every " + str(CHECK_INTERVAL_MINUTES) + " minutes")
    log.info("==================================================")
    check_size_availability()
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_size_availability)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
