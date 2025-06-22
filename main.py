# -*- coding: utf-8 -*-
"""
Thingiverse → Telegram bot (image + title + download link)   ©2025
إعداد: د. إيرك
"""
import os
import time
from datetime import datetime
from threading import Thread

import cloudscraper            # لتجاوز Cloudflare
import requests
from flask import Flask

# === متغيّرات البيئة ===
BOT_TOKEN   = os.getenv("BOT_TOKEN")
CHAT_ID     = os.getenv("CHAT_ID")
APP_TOKEN   = os.getenv("APP_TOKEN")

if not all([BOT_TOKEN, CHAT_ID, APP_TOKEN]):
    raise ValueError("⚠️ تأكّد من تعريف BOT_TOKEN و CHAT_ID و APP_TOKEN في لوحة Render")

# === Flask (لإبقاء الخدمة حية على Render) ===
app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Thingiverse-Bot is up."

# === أداة طلبات تتجاوز Cloudflare ===
scraper = cloudscraper.create_scraper(
    browser={"browser": "firefox", "platform": "linux", "desktop": True}
)

# === إرسال رسالة/صورة إلى تيليجرام ===
def telegram_send_photo(photo_url: str, caption: str):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": CHAT_ID, "photo": photo_url, "caption": caption}
    scraper.post(api, data=payload, timeout=10)

def telegram_send_text(text: str):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    scraper.post(api, data=payload, timeout=10)

# === جلب أحدث تصميم من Thingiverse ===
last_id = None                 # لتجنّب التكرار

def fetch_and_send():
    global last_id
    api = "https://api.thingiverse.com/newest/things"
    params = {"access_token": APP_TOKEN}

    try:
        r = scraper.get(api, params=params, timeout=15)
        r.raise_for_status()            # HTTP ≠ 200 يرفع-استثناء
        data = r.json()                 # لو HTML سيُرمى استثناء ويُلتقط بالأسفل

        # أحياناً تُعاد قائمة مباشرة أو تحت مفتاح hits
        things = data.get("hits") if isinstance(data, dict) else data
        if not things:
            telegram_send_text("⚠️ لا تصميمات جديدة حاليًا.")
            return

        thing = things[0]
        thing_id     = thing.get("id")
        if thing_id == last_id:
            return  # نفس العنصر السابق

        last_id      = thing_id
        title        = thing.get("name", "No title")
        public_url   = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing_id}"
        thumb_url    = thing.get("thumbnail")  or thing.get("preview_image")

        # رابط مباشر لتحميل ملف STL الأول إن وُجد
        # (مجرّد إضافة /download في العادة)
        download_url = f"https://www.thingiverse.com/download:{thing_id}"

        caption = f"📦 {title}\n🔗 {download_url}"

        if thumb_url:
            telegram_send_photo(thumb_url, caption)
        else:
            telegram_send_text(caption)

    except Exception as e:
        telegram_send_text(f"❌ خطأ في جلب التصميمات: {e}")
        print("❌", e)

# === حلقة العمل الخلفية ===
def worker():
    while True:
        fetch_and_send()
        now = datetime.now().strftime("%H:%M:%S")
        telegram_send_text(f"🤖 البوت حي - {now}")     # Ping
        time.sleep(120)    # كل دقيقتين

# === تشغيل ===
if __name__ == "__main__":
    Thread(target=worker, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))