# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
    يرسل كل نموذج جديد فور رفعه من المنصات التالية:
    - Thingiverse (جميع النماذج الجديدة منذ آخر فحص)
    - Printables.com (جميع العناصر الجديدة من RSS)
    - MakerWorld.com (جميع العناصر الجديدة من RSS)
    بشكل مستقر دون حذف أي قسم موجود سابقاً.
"""

import os, time, json, traceback, requests, xml.etree.ElementTree as ET
from datetime import datetime
from threading import Thread

import cloudscraper
from flask import Flask

# ───── متغيّرات البيئة ─────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), \
       "🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN يجب تعيينها!"

# ───── Flask ─────
app = Flask(__name__)
@app.route("/")
def index():
    return "✅ Thingiverse-Bot is running."

# ───── Self Ping للحفاظ على الحياة ─────
SELF_URL = "https://thingiverse-bot.onrender.com"
def keep_alive():
    while True:
        try:
            requests.get(SELF_URL)
            print("[⏳ Self-Ping] تم إرسال ping لإبقاء السيرفر نشطًا.")
        except Exception as e:
            print(f"[❌ Self-Ping Error] {e}")
        time.sleep(240)

# ───── Telegram & Scraper ─────
scraper = cloudscraper.create_scraper(
    browser={"browser": "firefox", "platform": "linux", "desktop": True}
)
TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg_photo(photo_url: str, caption: str, view_url: str, dl_url: str):
    kb = {"inline_keyboard": [
        [
            {"text": "🔗 View",         "url": view_url},
            {"text": "⬇️ Download STL", "url": dl_url},
        ]
    ]}
    payload = {
        "chat_id": CHAT_ID,
        "photo":   photo_url,
        "caption": caption,
        "reply_markup": json.dumps(kb, ensure_ascii=False)
    }
    scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

def tg_text(txt: str):
    scraper.post(
        f"{TG_ROOT}/sendMessage",
        data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"},
        timeout=10
    )

# ───── Thingiverse API (وظائف الأصلية تحافظ عليها) ─────
API_ROOT = "https://api.thingiverse.com"
last_ids = {
    "thingiverse_newest": None,
    "printables":        None,
    "makerworld":        None,
}

def newest_thingiverse():
    url = f"{API_ROOT}/newest/things"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    return r.json()  # الآن نعيد القائمة كاملة بدل العنصر الأول فقط

def first_file_id(thing_id: int):
    url = f"{API_ROOT}/things/{thing_id}/files"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    files = r.json()
    return files[0]["id"] if isinstance(files, list) and files else None

# ───── Printables.com via RSS ─────
def fetch_printables_items():
    url = "https://www.printables.com/rss"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return root.findall("./channel/item")  # قائمة العناصر

# ───── MakerWorld.com via RSS ─────
def fetch_makerworld_items():
    url = "https://makerworld.com/feed"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return root.findall("./channel/item")

# ───── العامل الرئيسي مع دعم إرسال كل جديد ─────
def worker():
    global last_ids
    while True:
        try:
            # ——— Thingiverse: جميع النماذج الجديدة منذ آخر فحص ———
            things = newest_thingiverse()  # قائمة عناصر مرتبة من الأحدث للأقدم
            new_items = []
            for thing in things:
                if thing["id"] == last_ids["thingiverse_newest"]:
                    break
                new_items.append(thing)
            if new_items:
                # أرسل الأقدم أولاً حتى تحافظ على الترتيب الزمني
                for thing in reversed(new_items):
                    title   = thing.get("name", "Thing")
                    pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
                    thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
                    file_id = first_file_id(thing["id"])
                    dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                    tg_photo(thumb, f"📦 [Thingiverse] {title}", pub_url, dl_url)
                # حدّث آخر معرف
                last_ids["thingiverse_newest"] = new_items[0]["id"]

            # ——— Printables.com: جميع العناصر الجديدة من RSS ———
            items = fetch_printables_items()
            new_items = []
            for item in items:
                link = item.find("link").text
                if link == last_ids["printables"]:
                    break
                new_items.append(item)
            if new_items:
                for item in reversed(new_items):
                    title = item.find("title").text
                    link  = item.find("link").text
                    tg_text(f"🖨️ <b>[Printables]</b> <a href=\"{link}\">{title}</a>")
                last_ids["printables"] = new_items[0].find("link").text

            # ——— MakerWorld.com: جميع العناصر الجديدة من RSS ———
            items = fetch_makerworld_items()
            new_items = []
            for item in items:
                link = item.find("link").text
                if link == last_ids["makerworld"]:
                    break
                new_items.append(item)
            if new_items:
                for item in reversed(new_items):
                    title = item.find("title").text
                    link  = item.find("link").text
                    tg_text(f"🔧 <b>[MakerWorld]</b> <a href=\"{link}\">{title}</a>")
                last_ids["makerworld"] = new_items[0].find("link").text

        except Exception as e:
            # أي خطأ غير متوقع يُسجَّل محلياً فقط
            print("⚠️ Unhandled error:", traceback.format_exc(limit=1))

        # تنبيه بالتوقيت قبل الفحص القادم
        now = datetime.now().strftime("%H:%M:%S")
        tg_text(f"🤖 التحديث التالي بعد دقيقتين — {now}")
        time.sleep(120)

# ───── تشغيل مقدّس ─────
if __name__ == "__main__":
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))