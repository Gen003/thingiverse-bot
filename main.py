# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
    يرسل أحدث تصميم (صورة + زرين View / Download) كل دقيقتين،
    بالإضافة إلى أحدث التصاميم من MyMiniFactory, Printables.com, MakerWorld.com
"""

import os, time, json, traceback, requests, xml.etree.ElementTree as ET
from datetime import datetime
from threading import Thread

import cloudscraper
from flask import Flask

# ───── متغيّرات البيئة ─────
BOT_TOKEN    = os.getenv("BOT_TOKEN")
CHAT_ID      = os.getenv("CHAT_ID")
APP_TOKEN    = os.getenv("APP_TOKEN")
MMF_API_KEY  = os.getenv("MMF_API_KEY")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN, MMF_API_KEY]), \
       "🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN / MMF_API_KEY يجب تعيينها!"

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
            {"text": "🔗 View", "url": view_url},
            {"text": "⬇️ Download STL", "url": dl_url},
        ]
    ]}
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "reply_markup": json.dumps(kb, ensure_ascii=False)
    }
    scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

def tg_text(txt: str):
    scraper.post(f"{TG_ROOT}/sendMessage",
                 data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"},
                 timeout=10)

# ───── Thingiverse API ─────
API_ROOT = "https://api.thingiverse.com"
last_ids = {
    "thingiverse_newest": None,
    "mmf":               None,
    "printables":        None,
    "makerworld":        None,
}

def newest_thingiverse():
    url = f"{API_ROOT}/newest/things"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data[0] if isinstance(data, list) and data else None

def first_file_id(thing_id: int):
    url = f"{API_ROOT}/things/{thing_id}/files"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    files = r.json()
    return files[0]["id"] if isinstance(files, list) and files else None

# ───── MyMiniFactory API (with SSL bypass) ─────
def newest_mmf():
    url = "https://api.myminifactory.com/api/v2/objects"
    try:
        r = scraper.get(
            url,
            params={"apikey": MMF_API_KEY, "order_by": "publish_date", "limit": 1},
            timeout=20,
            verify=False      # ← تجاوز التحقق من الشهادة
        )
        r.raise_for_status()
        objs = r.json().get("objects", [])
        return objs[0] if objs else None
    except Exception as e:
        print(f"[MMF Error] {e}")  # يسجل محلياً دون إرسال رسالة خطأ للمستخدم
        return None

# ───── Printables.com via RSS ─────
def newest_printables():
    url = "https://www.printables.com/rss"
    try:
        r = scraper.get(url, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        item = root.find("./channel/item")
        if item is None:
            return None
        title = item.find("title").text
        link  = item.find("link").text
        # المصغرة ليست متوفرة في RSS، نتركها فارغة
        return {"id": link, "title": title, "url": link, "thumbnail": ""}
    except Exception as e:
        print(f"[Printables Error] {e}")
        return None

# ───── MakerWorld.com via RSS ─────
def newest_makerworld():
    url = "https://makerworld.com/feed"
    try:
        r = scraper.get(url, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        item = root.find("./channel/item")
        if item is None:
            return None
        title = item.find("title").text
        link  = item.find("link").text
        return {"id": link, "title": title, "url": link, "thumbnail": ""}
    except Exception as e:
        print(f"[MakerWorld Error] {e}")
        return None

# ───── العامل الرئيسي ─────
def worker():
    global last_ids
    while True:
        try:
            # ——— Thingiverse newest ———
            thing = newest_thingiverse()
            if thing and thing["id"] != last_ids["thingiverse_newest"]:
                last_ids["thingiverse_newest"] = thing["id"]
                title   = thing.get("name", "Thing")
                pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
                thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
                file_id = first_file_id(thing["id"])
                dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                tg_photo(thumb, f"📦 [Thingiverse] {title}", pub_url, dl_url)

            # ——— MyMiniFactory ———
            mmf = newest_mmf()
            if mmf and mmf["id"] != last_ids["mmf"]:
                last_ids["mmf"] = mmf["id"]
                title   = mmf.get("name", "MMF Object")
                thumb   = mmf.get("media", [{}])[0].get("thumbnail_url", "")
                pub_url = mmf.get("url")
                dl_url  = mmf.get("files", [{}])[0].get("url", pub_url)
                tg_photo(thumb, f"🌐 [MyMiniFactory] {title}", pub_url, dl_url)

            # ——— Printables.com ———
            pp = newest_printables()
            if pp and pp["id"] != last_ids["printables"]:
                last_ids["printables"] = pp["id"]
                tg_text(f"🖨️ <b>[Printables]</b> <a href=\"{pp['url']}\">{pp['title']}</a>")

            # ——— MakerWorld.com ———
            mw = newest_makerworld()
            if mw and mw["id"] != last_ids["makerworld"]:
                last_ids["makerworld"] = mw["id"]
                tg_text(f"🔧 <b>[MakerWorld]</b> <a href=\"{mw['url']}\">{mw['title']}</a>")

        except Exception as e:
            # أخطاء غير متوقعة جداً تُسجَّل محلياً فقط
            print("⚠️ Unhandled error:", traceback.format_exc(limit=1))

        now = datetime.now().strftime("%H:%M:%S")
        tg_text(f"🤖 التحديث التالي بعد دقيقتين — {now}")
        time.sleep(120)

# ───── تشغيل مقدّس ─────
if __name__ == "__main__":
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))