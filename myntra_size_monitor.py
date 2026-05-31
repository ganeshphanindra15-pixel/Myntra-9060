"""
Myntra Size Monitor - Telegram Bot
Monitors product 28873290 for Size 9 availability and notifies via Telegram.

Setup:
1. pip install requests python-telegram-bot schedule
2. Create a Telegram bot via @BotFather and get your BOT_TOKEN
3. Get your CHAT_ID by messaging @userinfobot on Telegram
4. Fill in BOT_TOKEN and CHAT_ID below
5. Run: python myntra_size_monitor.py
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

PRODUCT_ID    = "28873290"
TARGET_SIZE   = "9"
CHECK_INTERVAL_MINUTES = 10             # How often to check (in minutes)
# ──────────────────────────────────────────────────────────────────────────────

MYNTRA_API_URL = f"https://www.myntra.com/gateway/v2/product/{PRODUCT_ID}"
PRODUCT_URL    = f"https://www.myntra.com/{PRODUCT_ID}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitor.log"),
    ]
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.myntra.com/",
}

# Track last notification state to avoid spamming
_last_notified_available = None


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


def fetch_product_data() -> dict | None:
    """Fetch product details from Myntra's internal API."""
    try:
        r = requests.get(MYNTRA_API_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        log.warning(f"HTTP error fetching product: {e}")
    except Exception as e:
        log.error(f"Error fetching product: {e}")
    return None


def check_size_availability():
    """Main check: fetch product and look for size 9."""
    global _last_notified_available

    log.info(f"Checking size {TARGET_SIZE} availability for product {PRODUCT_ID}...")
    data = fetch_product_data()

    if not data:
        log.warning("No data returned from Myntra API.")
        return

    try:
        # Navigate Myntra's response structure
        product = data.get("style", data)  # some endpoints wrap in 'style'
        name    = product.get("name", "Product")
        sizes   = product.get("sizes", [])

        # Each size entry looks like:
        # { "label": "9", "available": true/false, "skuId": ... }
        size_entry = None
        for s in sizes:
            label = str(s.get("label", "")).strip()
            if label == TARGET_SIZE:
                size_entry = s
                break

        if size_entry is None:
            log.info(f"Size {TARGET_SIZE} not listed for this product.")
            if _last_notified_available is not False:
                send_telegram(
                    f"⚠️ <b>Size {TARGET_SIZE} not found</b> in the size chart for:\n"
                    f"<b>{name}</b>\n{PRODUCT_URL}\n\n"
                    f"It may not be offered in this size."
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
                f"⏰ Checked at: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
            )
            _last_notified_available = True

        elif not is_available and _last_notified_available is True:
            send_telegram(
                f"❌ <b>Size {TARGET_SIZE} is no longer available</b>\n\n"
                f"👟 <b>{name}</b>\n"
                f"🔔 I'll keep watching and notify you when it's back!"
            )
            _last_notified_available = False

        else:
            log.info("No state change — skipping notification.")

    except Exception as e:
        log.error(f"Error parsing product data: {e}")


def main():
    log.info("=" * 50)
    log.info("Myntra Size Monitor started")
    log.info(f"Product : {PRODUCT_URL}")
    log.info(f"Size    : {TARGET_SIZE}")
    log.info(f"Interval: every {CHECK_INTERVAL_MINUTES} minutes")
    log.info("=" * 50)

    # Run once immediately on start
    check_size_availability()

    # Schedule recurring checks
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_size_availability)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
