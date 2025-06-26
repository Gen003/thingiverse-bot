# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
يرسل كل نموذج جديد فور رفعه من المنصات التالية:
- Thingiverse (جميع النماذج الجديدة منذ آخر فحص)
- Printables.com (جميع العناصر الجديدة من RSS)
- MakerWorld.com (جميع العناصر الجديدة من RSS)
مع الحفاظ على الاستقرار دون تغييرات كبيرة.
"""

import os, time, json, traceback, requests, xml.etree.ElementTree as ET
from threading import Thread
import cloudscraper
from flask import Flask
import sqlite3
import logging

#───── متغيّرات البيئة ─────

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), \
"🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN يجب تعيينها!"

#────ـ تهيئة السجل ─────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

#───── Flask ─────

app = Flask(__name__)
@app.route("/")
def index():
    return "✅ Thingiverse-Bot is running."

#───── Self Ping للحفاظ على الحياة ─────

SELF_URL = "https://thingiverse-bot.onrender.com"
def keep_alive():
    while True:
        try:
            requests.get(SELF_URL)
            logger.info("Self-ping successful")
        except Exception as e:
            logger.error(f"Self-ping failed: {str(e)}")
        time.sleep(240)

#────ـ Telegram & Scraper ─────

scraper = cloudscraper.create_scraper(
    browser={"browser": "firefox", "platform": "linux", "desktop": True},
    delay=10,
    interpreter='nodejs',
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
        "reply_markup": json.dumps(kb, ensure_ascii=False),
        "parse_mode": "HTML"
    }
    try:
        response = scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=25)
        response.raise_for_status()
        logger.info(f"Sent photo: {caption[:50]}...")
    except Exception as e:
        logger.error(f"Failed to send photo: {str(e)}")

def tg_text(txt: str):
    try:
        response = scraper.post(
            f"{TG_ROOT}/sendMessage",
            data={"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML"},
            timeout=15
        )
        response.raise_for_status()
        logger.info(f"Sent text: {txt[:50]}...")
    except Exception as e:
        logger.error(f"Failed to send text: {str(e)}")

#────ـ تخزين الحالة ─────

def init_db():
    conn = sqlite3.connect('state.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS last_ids
                 (source TEXT PRIMARY KEY, last_id TEXT)''')
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def get_last_id(source):
    try:
        conn = sqlite3.connect('state.db')
        c = conn.cursor()
        c.execute("SELECT last_id FROM last_ids WHERE source=?", (source,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"DB get error: {str(e)}")
        return None

def set_last_id(source, last_id):
    try:
        conn = sqlite3.connect('state.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO last_ids (source, last_id) VALUES (?, ?)", 
                  (source, last_id))
        conn.commit()
        conn.close()
        logger.info(f"Set last_id for {source}: {last_id}")
    except Exception as e:
        logger.error(f"DB set error: {str(e)}")

#────ـ Thingiverse API ─────

API_ROOT = "https://api.thingiverse.com"

def newest_thingiverse():
    try:
        url = f"{API_ROOT}/newest/things"
        r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Thingiverse API error: {str(e)}")
        return []

def first_file_id(thing_id: int):
    try:
        url = f"{API_ROOT}/things/{thing_id}/files"
        r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=25)
        r.raise_for_status()
        files = r.json()
        return files[0]["id"] if isinstance(files, list) and files else None
    except Exception as e:
        logger.error(f"Thingiverse files error: {str(e)}")
        return None

#────ـ Printables.com via RSS ─────

def fetch_printables_items():
    try:
        # الرابط الصحيح الحالي لـ Printables
        url = "https://www.printables.com/sitemap.xml?format=rss"
        r = scraper.get(url, timeout=25)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        return root.findall("./channel/item")
    except Exception as e:
        logger.error(f"Printables RSS error: {str(e)}")
        return []

#────ـ MakerWorld.com via RSS ─────

def fetch_makerworld_items():
    try:
        # الرابط الصحيح الحالي لـ MakerWorld
        url = "https://makerworld.com/sitemap.xml?format=rss"
        r = scraper.get(url, timeout=25)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        return root.findall("./channel/item")
    except Exception as e:
        logger.error(f"MakerWorld RSS error: {str(e)}")
        return []

#────ـ العامل الرئيسي مع إصلاحات المصادر الأخرى ─────

def worker():
    init_db()
    logger.info("Worker started")
    
    while True:
        try:
            # Thingiverse
            try:
                last_thingiverse = get_last_id("thingiverse_newest")
                things = newest_thingiverse()
                
                if things:
                    new_items = []
                    for thing in things:
                        if str(thing["id"]) == last_thingiverse:
                            break
                        new_items.append(thing)
                    
                    if new_items:
                        logger.info(f"Found {len(new_items)} new Thingiverse items")
                        for thing in reversed(new_items):
                            title   = thing.get("name", "Thing")
                            pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
                            thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
                            file_id = first_file_id(thing["id"])
                            dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                            tg_photo(thumb, f"📦 <b>[Thingiverse]</b> {title}", pub_url, dl_url)
                        
                        set_last_id("thingiverse_newest", str(new_items[0]["id"]))
            except Exception as e:
                error_msg = f"❌ خطأ في Thingiverse: {str(e)}"
                logger.error(error_msg)
                tg_text(error_msg[:4000])
            
            # Printables
            try:
                last_printables = get_last_id("printables")
                items = fetch_printables_items()
                
                if items:
                    new_items = []
                    for item in items:
                        link = item.find("link").text
                        if link == last_printables:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        logger.info(f"Found {len(new_items)} new Printables items")
                        for item in reversed(new_items):
                            title = item.find("title").text
                            link  = item.find("link").text
                            tg_text(f"🖨️ <b>[Printables]</b> <a href=\"{link}\">{title}</a>")
                        
                        set_last_id("printables", new_items[0].find("link").text)
            except Exception as e:
                error_msg = f"❌ خطأ في Printables: {str(e)}"
                logger.error(error_msg)
                tg_text(error_msg[:4000])
            
            # MakerWorld
            try:
                last_makerworld = get_last_id("makerworld")
                items = fetch_makerworld_items()
                
                if items:
                    new_items = []
                    for item in items:
                        link = item.find("link").text
                        if link == last_makerworld:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        logger.info(f"Found {len(new_items)} new MakerWorld items")
                        for item in reversed(new_items):
                            title = item.find("title").text
                            link  = item.find("link").text
                            tg_text(f"🔧 <b>[MakerWorld]</b> <a href=\"{link}\">{title}</a>")
                        
                        set_last_id("makerworld", new_items[0].find("link").text)
            except Exception as e:
                error_msg = f"❌ خطأ في MakerWorld: {str(e)}"
                logger.error(error_msg)
                tg_text(error_msg[:4000])
        
        except Exception as e:
            error_msg = f"❌ خطأ غير متوقع: {str(e)}"
            logger.error(error_msg)
            tg_text(error_msg[:4000])
            time.sleep(60)
        
        logger.info("Cycle completed. Sleeping...")
        time.sleep(180)  # فحص كل 3 دقائق

#────ـ تشغيل مقدّس ─────

if __name__ == "__main__":
    logger.info("Starting application...")
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))