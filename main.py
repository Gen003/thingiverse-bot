# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
يرسل كل نموذج جديد فور رفعه من المنصات التالية:
- Thingiverse (جميع النماذج الجديدة منذ آخر فحص)
- Printables.com (من خلال واجهة برمجة التطبيقات)
- MakerWorld.com (من خلال واجهة برمجة التطبيقات)
"""

import os, time, json, traceback, requests
from threading import Thread, Lock
import cloudscraper
from flask import Flask
import sqlite3
import logging
import random
import datetime

# ------ متغيّرات البيئة ------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), \
"🔴 BOT_TOKEN / CHAT_ID / APP_TOKEN يجب تعيينها!"

# ------ تهيئة السجل ------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------ قفل للتحكم في معدل الإرسال ------
send_lock = Lock()
last_send_time = 0

# ------ Flask ------
app = Flask(__name__)
@app.route("/")
def index():
    return "✅ Thingiverse-Bot is running."

# ------ Self Ping للحفاظ على الحياة ------
SELF_URL = "https://thingiverse-bot.onrender.com"
def keep_alive():
    while True:
        try:
            requests.get(SELF_URL, timeout=10)
            logger.info("Self-ping successful")
        except Exception as e:
            logger.error(f"Self-ping failed: {str(e)}")
        time.sleep(300)

# ------ تهيئة السكرابر ------
def create_scraper():
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'linux',
            'desktop': True
        },
        delay=10
    )

scraper = create_scraper()
TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

# إعادة تهيئة السكرابر دورياً
def reset_scraper():
    global scraper
    logger.info("Resetting scraper instance...")
    scraper = create_scraper()

# ------ إرسال آمن إلى Telegram ------
def safe_send_message(payload, is_photo=False):
    global last_send_time
    endpoint = "/sendPhoto" if is_photo else "/sendMessage"
    
    with send_lock:
        # التحكم في معدل الإرسال (رسالة كل 5-8 ثوان)
        elapsed = time.time() - last_send_time
        if elapsed < 5:
            wait_time = 5 + random.uniform(0, 3) - elapsed
            logger.info(f"Rate limiting: Waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        try:
            response = scraper.post(f"{TG_ROOT}{endpoint}", data=payload, timeout=45)
            response.raise_for_status()
            last_send_time = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            if "Too Many Requests" in str(e):
                wait_time = 45 + random.randint(0, 30)
                logger.warning(f"Too Many Requests! Waiting {wait_time}s")
                time.sleep(wait_time)
            elif "Connection reset by peer" in str(e):
                reset_scraper()
            return False

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
    success = safe_send_message(payload, is_photo=True)
    if success:
        logger.info(f"Sent photo: {caption[:50]}...")

def tg_text(txt: str):
    payload = {
        "chat_id": CHAT_ID,
        "text": txt,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    success = safe_send_message(payload)
    if success:
        logger.info(f"Sent text: {txt[:50]}...")

# ------ تخزين الحالة ------
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

# ------ طلبات متينة مع إعادة المحاولة ------
def robust_request(url, method='GET', params=None, headers=None, max_retries=3):
    retry_delays = [5, 15, 30]
    
    for attempt in range(max_retries):
        try:
            final_headers = headers or {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0',
                'Accept': 'application/json',
                'Connection': 'keep-alive'
            }
            
            logger.info(f"Request attempt {attempt+1} to {url}")
            
            if method == 'GET':
                response = scraper.get(url, params=params, headers=final_headers, timeout=30)
            else:
                response = scraper.post(url, data=params, headers=final_headers, timeout=30)
            
            response.raise_for_status()
            return response
        
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            
            delay = retry_delays[attempt] if attempt < len(retry_delays) else 30
            logger.warning(f"Connection error, retrying in {delay}s: {str(e)}")
            time.sleep(delay)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                delay = 60
                logger.warning(f"Rate limited (429), retrying in {delay}s")
                time.sleep(delay)
            else:
                logger.error(f"HTTP error {e.response.status_code}: {str(e)}")
                return None
    
    logger.error(f"Failed after {max_retries} attempts for {url}")
    return None

# ------ Thingiverse API ------
API_ROOT = "https://api.thingiverse.com"

def newest_thingiverse():
    try:
        url = f"{API_ROOT}/newest/things"
        params = {"access_token": APP_TOKEN}
        response = robust_request(url, params=params)
        return response.json() if response else []
    except Exception as e:
        logger.error(f"Thingiverse API error: {str(e)}")
        return []

def first_file_id(thing_id: int):
    try:
        url = f"{API_ROOT}/things/{thing_id}/files"
        params = {"access_token": APP_TOKEN}
        response = robust_request(url, params=params)
        if not response:
            return None
            
        files = response.json()
        return files[0]["id"] if isinstance(files, list) and files else None
    except Exception as e:
        logger.error(f"Thingiverse files error: {str(e)}")
        return None

# ------ Printables.com API ------
def fetch_printables_items():
    try:
        url = "https://api.printables.com/graphql/"
        headers = {
            'Content-Type': 'application/json',
            'Origin': 'https://www.printables.com',
            'Referer': 'https://www.printables.com/'
        }
        
        # استعلام GraphQL للحصول على أحدث النماذج
        payload = {
            "query": """
            query {
                newestModels(first: 20) {
                    edges {
                        node {
                            id
                            name
                            slug
                            thumbnailUrl
                            createdAt
                        }
                    }
                }
            }
            """
        }
        
        response = robust_request(url, method='POST', headers=headers, params=json.dumps(payload))
        if not response:
            return []
            
        data = response.json()
        models = data.get('data', {}).get('newestModels', {}).get('edges', [])
        
        items = []
        for model in models:
            node = model.get('node', {})
            if node:
                items.append({
                    'id': node.get('id'),
                    'title': node.get('name'),
                    'link': f"https://www.printables.com/model/{node.get('id')}-{node.get('slug')}",
                    'thumbnail': node.get('thumbnailUrl'),
                    'created_at': node.get('createdAt')
                })
        return items
    except Exception as e:
        logger.error(f"Printables API error: {str(e)}")
        return []

# ------ MakerWorld.com API ------
def fetch_makerworld_items():
    try:
        url = "https://makerworld.com/api/v1/makers/hot?page=1&limit=20"
        headers = {
            'Accept': 'application/json',
            'X-App': 'makerworld-web'
        }
        
        response = robust_request(url, headers=headers)
        if not response:
            return []
            
        data = response.json()
        items = []
        for item in data.get('data', []):
            items.append({
                'id': item.get('id'),
                'title': item.get('name'),
                'link': f"https://makerworld.com/models/{item.get('id')}",
                'thumbnail': item.get('cover', {}).get('url'),
                'created_at': item.get('created_at')
            })
        return items
    except Exception as e:
        logger.error(f"MakerWorld API error: {str(e)}")
        return []

# ------ العامل الرئيسي ------
def worker():
    init_db()
    logger.info("Worker started")
    
    # تهيئة معدل الإرسال
    global last_send_time
    last_send_time = time.time() - 5
    
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
                        # إرسال أحدث عنصر فقط
                        thing = new_items[0]
                        title   = thing.get("name", "Thing")
                        pub_url = thing.get("public_url") or f"https://www.thingiverse.com/thing:{thing['id']}"
                        thumb   = thing.get("thumbnail") or thing.get("preview_image") or ""
                        file_id = first_file_id(thing["id"])
                        dl_url  = f"https://www.thingiverse.com/download:{file_id}" if file_id else pub_url
                        tg_photo(thumb, f"📦 <b>[Thingiverse]</b> {title}", pub_url, dl_url)
                        
                        # تحديث آخر معرف
                        set_last_id("thingiverse_newest", str(thing["id"]))
                        logger.info(f"Sent 1 new Thingiverse item. {len(new_items)-1} remaining")
            except Exception as e:
                error_msg = f"❌ خطأ في Thingiverse: {str(e)[:300]}"
                logger.error(error_msg)
                time.sleep(10)
            
            # الانتظار قبل المصدر التالي
            time.sleep(15 + random.randint(0, 10))
            
            # Printables
            try:
                last_printables = get_last_id("printables")
                items = fetch_printables_items()
                
                if items:
                    new_items = []
                    for item in items:
                        if item['id'] == last_printables:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        # إرسال أحدث عنصر فقط
                        item = new_items[0]
                        tg_text(f"🖨️ <b>[Printables]</b> <a href=\"{item['link']}\">{item['title']}</a>")
                        
                        # تحديث آخر معرف
                        set_last_id("printables", new_items[0]['id'])
                        logger.info(f"Sent 1 new Printables item. {len(new_items)-1} remaining")
            except Exception as e:
                error_msg = f"❌ خطأ في Printables: {str(e)[:300]}"
                logger.error(error_msg)
                time.sleep(10)
            
            # الانتظار قبل المصدر التالي
            time.sleep(15 + random.randint(0, 10))
            
            # MakerWorld
            try:
                last_makerworld = get_last_id("makerworld")
                items = fetch_makerworld_items()
                
                if items:
                    new_items = []
                    for item in items:
                        if item['id'] == last_makerworld:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        # إرسال أحدث عنصر فقط
                        item = new_items[0]
                        tg_text(f"🔧 <b>[MakerWorld]</b> <a href=\"{item['link']}\">{item['title']}</a>")
                        
                        # تحديث آخر معرف
                        set_last_id("makerworld", new_items[0]['id'])
                        logger.info(f"Sent 1 new MakerWorld item. {len(new_items)-1} remaining")
            except Exception as e:
                error_msg = f"❌ خطأ في MakerWorld: {str(e)[:300]}"
                logger.error(error_msg)
                time.sleep(10)
        
        except Exception as e:
            error_msg = f"❌ خطأ غير متوقع: {str(e)[:300]}"
            logger.error(error_msg)
            reset_scraper()
            time.sleep(60)
        
        logger.info("Cycle completed. Sleeping...")
        time.sleep(300 + random.randint(0, 120))

# ------ تشغيل التطبيق ------
if __name__ == "__main__":
    logger.info("Starting application...")
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))