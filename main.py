# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
يرسل كل نموذج جديد فور رفعه من المنصات التالية:
#- Thingiverse (جميع النماذج الجديدة منذ آخر فحص)
#- Printables.com (جميع العناصر الجديدة من RSS)
#- MakerWorld.com (جميع العناصر الجديدة من RSS)
مع الحفاظ على الاستقرار دون تغييرات كبيرة.
"""

import os, time, json, traceback, requests, xml.etree.ElementTree as ET
from threading import Thread
import cloudscraper
from flask import Flask
import sqlite3  # <-- إضافة مهمة لتخزين الحالة

#───── متغيّرات البيئة ─────

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), \
"🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN يجب تعيينها!"

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
        except:
            pass
        time.sleep(240)

#───── Telegram & Scraper ─────

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

#────ـ تخزين الحالة ─────

def init_db():
    conn = sqlite3.connect('state.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS last_ids
                 (source TEXT PRIMARY KEY, last_id TEXT)''')
    conn.commit()
    conn.close()

def get_last_id(source):
    conn = sqlite3.connect('state.db')
    c = conn.cursor()
    c.execute("SELECT last_id FROM last_ids WHERE source=?", (source,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_last_id(source, last_id):
    conn = sqlite3.connect('state.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO last_ids (source, last_id) VALUES (?, ?)", 
              (source, last_id))
    conn.commit()
    conn.close()

#────ـ Thingiverse API ─────

API_ROOT = "https://api.thingiverse.com"

def newest_thingiverse():
    url = f"{API_ROOT}/newest/things"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    return r.json()

def first_file_id(thing_id: int):
    url = f"{API_ROOT}/things/{thing_id}/files"
    r = scraper.get(url, params={"access_token": APP_TOKEN}, timeout=20)
    r.raise_for_status()
    files = r.json()
    return files[0]["id"] if isinstance(files, list) and files else None

#────ـ Printables.com via RSS ─────

def fetch_printables_items():
    url = "https://www.printables.com/rss"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return root.findall("./channel/item")

#────ـ MakerWorld.com via RSS ─────

def fetch_makerworld_items():
    url = "https://makerworld.com/feed"
    r = scraper.get(url, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return root.findall("./channel/item")

#────ـ العامل الرئيسي مع إصلاحات المصادر الأخرى ─────

def worker():
    init_db()  # تهيئة قاعدة البيانات
    
    while True:
        try:
            # Thingiverse
            last_thingiverse = get_last_id("thingiverse_newest")
            things = newest_thingiverse()
            
            new_items = []
            for thing in things:
                if str(thing["id"]) == last_thingiverse:
                    break
                new_items.append(thing)
                
            if new_items:
                for thing in reversed(new_items):
                    title   = thing.get("name", "Thing")
                    pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
                    thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
                    file_id = first_file_id(thing["id"])
                    dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                    tg_photo(thumb, f"📦 [Thingiverse] {title}", pub_url, dl_url)
                
                set_last_id("thingiverse_newest", str(new_items[0]["id"]))
            
            # Printables
            last_printables = get_last_id("printables")
            items = fetch_printables_items()
            
            new_items = []
            for item in items:
                link = item.find("link").text
                if link == last_printables:
                    break
                new_items.append(item)
                
            if new_items:
                for item in reversed(new_items):
                    title = item.find("title").text
                    link  = item.find("link").text
                    tg_text(f"🖨️ <b>[Printables]</b> <a href=\"{link}\">{title}</a>")
                
                set_last_id("printables", new_items[0].find("link").text)
            
            # MakerWorld
            last_makerworld = get_last_id("makerworld")
            items = fetch_makerworld_items()
            
            new_items = []
            for item in items:
                link = item.find("link").text
                if link == last_makerworld:
                    break
                new_items.append(item)
                
            if new_items:
                for item in reversed(new_items):
                    title = item.find("title").text
                    link  = item.find("link").text
                    tg_text(f"🔧 <b>[MakerWorld]</b> <a href=\"{link}\">{title}</a>")
                
                set_last_id("makerworld", new_items[0].find("link").text)
        
        except Exception as e:
            error_msg = f"❌ خطأ في جلب التحديثات: {str(e)}\n\n{traceback.format_exc()}"
            tg_text(error_msg[:4000])  # تأكد من عدم تجاوز حد التلجرام
            time.sleep(60)
        
        time.sleep(120)

#────ـ تشغيل مقدّس ─────

if __name__ == "__main__":
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))