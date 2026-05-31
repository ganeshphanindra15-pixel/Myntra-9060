"""
Myntra Size Monitor - Telegram Bot
Uses ScraperAPI to bypass Myntra's anti-bot protection.

Free tier: 1000 API calls/month → checking every 10 mins = ~4400 calls/month
Recommended: set CHECK_INTERVAL_MINUTES = 20 to stay within free tier (2200 calls/month)
Sign up free at: https://www.scraperapi.com
"""

import os
import requests
import schedule
import time
import logging
from datetime import datetime

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID        = os.environ.get("CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "YOUR_SCRAPERAPI_KEY")

PRODUCT_ID             = "28873290"
TARGET_SIZE            = "9"
CHECK_INTERVAL_MINUTES = 20   # every 20 mins = ~2200 calls/month (within free tier)
# ──────────────────────────────────────────────────────────────────────────────

PRODUCT_URL  = f"https://www.myntra.com/{PRODUCT_ID}"
MYNTRA_API   = f"https://www.myntra.com/gateway/v2/product/{PRODUCT_ID}"
SCRAPER_URL  = "https://api.scraperapi.com/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

_last_notified_available = None


def fetch_product_data():
    """Fetch Myntra product data via ScraperAPI residential proxy."""
    params = {
        "api_key": SCRAPER_API_KEY,
        "url": MYNTRA_API,
        "render": "false",
        "country_code": "in",          # Use Indian IP
    }
    try:
        log.info("Fetching via ScraperAPI...")
        r = requests.get(SCRAPER_URL, params=params, timeout=60)
        log.info(f"Status: {r.status_code} | Length: {len(r.text)}")

        if r.status_code == 200 and r.text.strip():
            try:
                return r.json()
            except Exception:
                log.warning(f"Response not JSON. Preview: {r.text[:200]}")
        else:
            log.warning(f"Bad response: {r.status_code}")
    except Exception as e:
        log.error(f"ScraperAPI error: {e}")
    return None


def parse_sizes(data):
    """Extract sizes and product name from Myntra response."""
    if not data:
        return [], "Unknown Product"
    for key in ["style", "data", ""]:
        obj = data.get(key, data) if key else data
        if "sizes" in obj:
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
        log.warning("No data — will retry next interval.")
        return

    sizes, name = parse_sizes(data)
    log.info(f"Product: {name} | Sizes: {[s.get('label') for s in sizes]}")

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
