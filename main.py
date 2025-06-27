import os
import time
import json
import traceback
import requests
from datetime import datetime
from threading import Thread, Lock
import sqlite3
import re
import cloudscraper
from flask import Flask
from bs4 import BeautifulSoup

# ───── متغيّرات البيئة ─────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")
DB_PATH   = os.getenv("DB_PATH", "thingiverse_bot.db")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), "🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN must be set!"

# ───── Flask ─────
app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Thingiverse-Bot is running."

# ───── إعداد قاعدة البيانات ─────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processed_things
                 (id INTEGER PRIMARY KEY, 
                  processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS last_check
                 (id INTEGER PRIMARY KEY, 
                  last_id INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# ───── Telegram & Thingiverse ─────
scraper = cloudscraper.create_scraper(
    browser={"browser": "firefox", "platform": "linux", "desktop": True},
    delay=10
)
TG_ROOT  = f"https://api.telegram.org/bot{BOT_TOKEN}"
API_ROOT = "https://api.thingiverse.com"
db_lock = Lock()

def get_last_id():
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT last_id FROM last_check WHERE id = 1")
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

def set_last_id(last_id):
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO last_check (id, last_id) VALUES (1, ?)", (last_id,))
        conn.commit()
        conn.close()

def is_processed(thing_id):
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM processed_things WHERE id = ?", (thing_id,))
        exists = c.fetchone() is not None
        conn.close()
        return exists

def mark_processed(thing_id):
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO processed_things (id) VALUES (?)", (thing_id,))
        conn.commit()
        conn.close()

def get_thingiverse_files(thing_id):
    """استخراج ملفات STL مباشرة من صفحة التصميم"""
    url = f"https://www.thingiverse.com/thing:{thing_id}"
    try:
        response = scraper.get(url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        files = []
        for link in soup.select('a[href*="/thing:download/"]'):
            file_id = re.search(r'/thing:download/(\d+)', link['href'])
            if file_id:
                file_name = link.text.strip()
                if file_name.lower().endswith('.stl'):
                    files.append({
                        "id": file_id.group(1),
                        "name": file_name,
                        "url": f"https://www.thingiverse.com{link['href']}"
                    })
        return files[:5]  # إرجاع أول 5 ملفات فقط
    except Exception as e:
        print(f"Failed to scrape files: {e}")
        return []

def send_telegram_message(thing):
    thing_id = thing["id"]
    title    = thing.get("name", "Thing")
    pub_url  = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing_id}"
    thumb    = thing.get("thumbnail") or thing.get("preview_image") or ""
    
    # استخراج الملفات
    files = get_thingiverse_files(thing_id)
    
    # إنشاء واجهة المستخدم
    buttons = []
    if files:
        for file in files:
            buttons.append([{"text": f"⬇️ {file['name']}", "url": file['url']}])
        buttons.append([{"text": "🔗 View on Thingiverse", "url": pub_url}])
    else:
        buttons = [[{"text": "🔗 View on Thingiverse", "url": pub_url}]]
    
    keyboard = {"inline_keyboard": buttons}
    
    # إعداد المحتوى
    caption = f"📦 *{title}*"
    if thing.get("description"):
        desc = thing["description"][:300] + "..." if len(thing["description"]) > 300 else thing["description"]
        caption += f"\n\n{desc}"
    
    # إرسال الصورة أو الرسالة
    if thumb:
        payload = {
            "chat_id": CHAT_ID,
            "photo": thumb,
            "caption": caption,
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(keyboard, ensure_ascii=False)
        }
        scraper.post(f"{TG_ROOT}/sendPhoto", data=payload, timeout=20)
    else:
        payload = {
            "chat_id": CHAT_ID,
            "text": f"{caption}\n\n{pub_url}",
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(keyboard, ensure_ascii=False)
        }
        scraper.post(f"{TG_ROOT}/sendMessage", data=payload, timeout=15)

def fetch_new_things():
    """جلب التصاميم الجديدة مع التعامل مع التقييد"""
    url = f"{API_ROOT}/newest/things"
    params = {"access_token": APP_TOKEN, "per_page": 20}
    
    try:
        response = scraper.get(url, params=params, timeout=25)
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Retrying after {retry_after} seconds")
            time.sleep(retry_after)
            return fetch_new_things()
        
        response.raise_for_status()
        return response.json() if response.headers.get("content-type","").startswith("application/json") else []
    except Exception as e:
        print(f"Fetch error: {e}")
        return []

def worker():
    while True:
        try:
            last_id = get_last_id()
            things = fetch_new_things()
            
            if not things:
                time.sleep(60)
                continue
                
            new_items = []
            for thing in things:
                if thing["id"] == last_id:
                    break
                if not is_processed(thing["id"]):
                    new_items.append(thing)
            
            # معالجة العناصر الجديدة من الأحدث إلى الأقدم
            for thing in reversed(new_items):
                try:
                    send_telegram_message(thing)
                    mark_processed(thing["id"])
                    time.sleep(2)  # تجنب القيود
                except Exception as e:
                    print(f"Error processing thing {thing['id']}: {e}")
            
            # تحديث آخر معرف
            if things:
                set_last_id(things[0]["id"])
                
        except Exception as e:
            print(f"Worker error: {traceback.format_exc(limit=1)}")
        
        time.sleep(120)  # فحص كل دقيقتين

def keep_alive():
    """يبقي التطبيق حيًّا"""
    port = os.getenv("PORT", "10000")
    url  = f"http://localhost:{port}/"
    while True:
        try:
            requests.get(url, timeout=10)
        except:
            pass
        time.sleep(300)

if __name__ == "__main__":
    Thread(target=worker,     daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))