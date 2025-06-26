# إعادة كتابة الكود مع ضمان خلوّه من الأخطاء النحوية لتشغيل بوت Telegram يجلب تصاميم جديدة من Thingiverse ومصادر أخرى

code = """
import os
import time
import json
import pickle
import traceback
import requests
import feedparser
from threading import Thread
from flask import Flask

# ───────── إعداد البيئة ─────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
THINGIVERSE_TOKEN = os.getenv("APP_TOKEN")

assert all([BOT_TOKEN, CHAT_ID]), "❌ تأكد من ضبط متغيرات البيئة BOT_TOKEN و CHAT_ID"

# ───────── إرسال رسالة إلى Telegram ─────────
def send_to_telegram(text, image_url=None, buttons=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto" if image_url else f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "caption": text,
        "parse_mode": "HTML"
    } if image_url else {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    if image_url:
        payload["photo"] = image_url

    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": [[btn] for btn in buttons]})

    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"[Telegram Error] {e}")

# ───────── حفظ / تحميل آخر العناصر ─────────
def load_last_ids():
    if os.path.exists("last_ids.pkl"):
        with open("last_ids.pkl", "rb") as f:
            return pickle.load(f)
    return {}

def save_last_ids(data):
    with open("last_ids.pkl", "wb") as f:
        pickle.dump(data, f)

# ───────── Thingiverse API ─────────
def fetch_thingiverse(last_ids):
    try:
        headers = {"Authorization": f"Bearer {THINGIVERSE_TOKEN}"}
        r = requests.get("https://api.thingiverse.com/newest", headers=headers)
        items = r.json()
        if not isinstance(items, list):
            return
        for item in items:
            thing_id = str(item["id"])
            if last_ids.get("thingiverse") == thing_id:
                break
            title = item["name"]
            img = item["thumbnail"]
            link = item["public_url"]
            send_to_telegram(f"📦 <b>{title}</b>", img, [[{"text": "🔗 View", "url": link}]])
            last_ids["thingiverse"] = thing_id
            save_last_ids(last_ids)
            time.sleep(1)
    except Exception as e:
        print(f"[Thingiverse Error] {e}")

# ───────── RSS مصدر عام ─────────
def fetch_rss_source(source_name, url, last_ids):
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            entry_id = entry.get("id", entry.link)
            if last_ids.get(source_name) == entry_id:
                break
            title = entry.title
            link = entry.link
            img = entry.get("media_thumbnail", [{}])[0].get("url", "")
            send_to_telegram(f"🆕 <b>{title}</b>", img, [[{"text": "🔗 Visit", "url": link}]])
            last_ids[source_name] = entry_id
            save_last_ids(last_ids)
            break
    except Exception as e:
        print(f"[{source_name} Error] {e}")

# ───────── حلقة التشغيل ─────────
def loop():
    last_ids = load_last_ids()
    sources = [
        ("thingiverse", lambda: fetch_thingiverse(last_ids)),
        ("printables", lambda: fetch_rss_source("printables", "https://www.printables.com/model/rss", last_ids)),
        ("thangs", lambda: fetch_rss_source("thangs", "https://thangs.com/designs/rss", last_ids)),
        ("cults3d", lambda: fetch_rss_source("cults3d", "https://cults3d.com/en/feed", last_ids)),
        ("youmagine", lambda: fetch_rss_source("youmagine", "https://www.youmagine.com/designs.rss", last_ids)),
        ("prusaprinters", lambda: fetch_rss_source("prusaprinters", "https://blog.prusa3d.com/feed/", last_ids))
    ]

    while True:
        for name, func in sources:
            func()
        time.sleep(120)

# ───────── Keep-Alive Server ─────────
app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Bot is running."

# ───────── بدء التشغيل ─────────
if __name__ == "__main__":
    Thread(target=loop).start()
    app.run(host="0.0.0.0", port=10000)
"""
print(code)