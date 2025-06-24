# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
    يرسل أحدث تصميم (صورة + زرين View / Download) كل دقيقتين،
    بالإضافة إلى أحدث التصاميم من منصات MyMiniFactory, Cults3D, Pinshape, YouMagine
    والتصاميم الرائجة من Thingiverse.
"""

import os, time, json, traceback, requests
from datetime import datetime
from threading import Thread

import cloudscraper
from flask import Flask

# ───── متغيّرات البيئة ─────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), "🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN must be set!"

# ───── Flask ─────
app = Flask(__name__)
@app.route("/")
def index():
    return "✅ Thingiverse-Bot is running."

# ───── Self Ping للحفاظ على الحياة ─────
SELF_URL = "https://thingiverse-bot.onrender.com"  # ← تأكد أنه مطابق للرابط الفعلي
def keep_alive():
    while True:
        try:
            requests.get(SELF_URL)
            print("[⏳ Self-Ping] تم إرسال ping لإبقاء السيرفر نشطًا.")
        except Exception as e:
            print(f"[❌ Self-Ping Error] {e}")
        time.sleep(240)  # كل 4 دقائق

# ───── Telegram & Scraper ─────
scraper = cloudscraper.create_scraper(
    browser={"browser": "firefox", "platform": "linux", "desktop": True}
)
TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg_photo(photo_url: str, caption: str, view_url: str, dl_url: str):
    kb = {
        "inline_keyboard": [
            [
                {"text": "🔗 View", "url": view_url},
                {"text": "⬇️ Download STL", "url": dl_url},
            ]
        ]
    }
    payload = {
        "chat_id": CHAT_ID,
        "photo":   photo_url,
        "caption": caption,
        "reply_markup": json.dumps(kb, ensure_ascii=False)
    }
    scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=15)

def tg_text(txt: str):
    scraper.post(f"{TG_ROOT}/sendMessage", data={"chat_id": CHAT_ID, "text": txt}, timeout=10)

# ───── Thingiverse API ─────
API_ROOT = "https://api.thingiverse.com"
last_ids = {"thingiverse_newest": None, "thingiverse_trending": None,
            "mmf": None, "cults": None, "pinshape": None, "youmagine": None}

def newest_thingiverse():
    url = f"{API_ROOT}/newest/things"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data[0] if isinstance(data, list) and data else None

def trending_thingiverse():
    url = f"{API_ROOT}/popular/things"
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

# ───── MyMiniFactory API ─────
MMF_ROOT = "https://api.myminifactory.com"
MMF_KEY  = os.getenv("MMF_API_KEY")  # احفظ مفتاح API في متغير MMF_API_KEY

def newest_mmf():
    url = f"{MMF_ROOT}/api/v2/objects"
    r = scraper.get(url, params={"apikey": MMF_KEY, "order_by": "publish_date", "limit": 1}, timeout=20)
    r.raise_for_status()
    data = r.json().get("objects", [])
    return data[0] if data else None

# ───── Cults3D (Web Scraping) ─────
def newest_cults():
    url = "https://cults3d.com/en/new"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    # هنا يمكن استخدام BeautifulSoup لاستخلاص أول عنصر، لكن cloudscraper يعيد HTML،
    # وللتبسيط نفترض استخراج الرابط والصورة يدوياً أو عبر تعابير منتظمة.
    # مثال تقريبي:
    # match = re.search(r'data-model-id="(\d+)"', r.text)
    # ثم استخراج الصورة والعنوان عبر تعابير.
    return None  # يتطلب تنفيذ تفصيلي حسب هيكل HTML

# ───── Pinshape (Web Scraping) ─────
def newest_pinshape():
    url = "https://pinshape.com/explore"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    return None  # يحتاج تنفيذ تفصيلي

# ───── YouMagine (Web Scraping) ─────
def newest_youmagine():
    url = "https://www.youmagine.com/designs"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    return None  # يحتاج تنفيذ تفصيلي

# ───── العامل الرئيسي ─────
def worker():
    global last_ids
    while True:
        try:
            # 1) أحدث من Thingiverse
            thing = newest_thingiverse()
            if thing and thing["id"] != last_ids["thingiverse_newest"]:
                last_ids["thingiverse_newest"] = thing["id"]
                title   = thing.get("name", "Thing")
                pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
                thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
                file_id = first_file_id(thing["id"])
                dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                tg_photo(thumb, f"📦 [New Thingiverse] {title}", pub_url, dl_url)

            # 2) الرائجة من Thingiverse
            trend = trending_thingiverse()
            if trend and trend["id"] != last_ids["thingiverse_trending"]:
                last_ids["thingiverse_trending"] = trend["id"]
                title   = trend.get("name", "Trending")
                pub_url = trend.get("public_url") or f"https://www.thingiverse.com/thing:{trend['id']}"
                thumb   = trend.get("thumbnail") or trend.get("preview_image") or ""
                file_id = first_file_id(trend["id"])
                dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                tg_photo(thumb, f"🔥 [Trending Thingiverse] {title}", pub_url, dl_url)

            # 3) أحدث من MyMiniFactory
            mmf = newest_mmf()
            if mmf and mmf["id"] != last_ids["mmf"]:
                last_ids["mmf"] = mmf["id"]
                title   = mmf.get("name", "MMF Object")
                thumb   = mmf.get("media", [{}])[0].get("thumbnail_url", "")
                pub_url = mmf.get("url")
                dl_url  = mmf.get("files", [{}])[0].get("url", pub_url)
                tg_photo(thumb, f"🌐 [MyMiniFactory] {title}", pub_url, dl_url)

            # 4) (نموذج مستقبلي) Cults3D
            cult = newest_cults()
            if cult:
                # handle similar to above بعد الاستخلاص
                pass

            # 5) (نموذج مستقبلي) Pinshape
            pin = newest_pinshape()
            if pin:
                pass

            # 6) (نموذج مستقبلي) YouMagine
            ym = newest_youmagine()
            if ym:
                pass

        except Exception as e:
            print("⚠️", traceback.format_exc(limit=1))
            tg_text(f"❌ خطأ في جلب التصاميم:\n{e}")

        now = datetime.now().strftime("%H:%M:%S")
        tg_text(f"🤖 التحديث التالي بعد دقيقتين — {now}")
        time.sleep(120)

# ───── تشغيل مقدّس ─────
if __name__ == "__main__":
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))