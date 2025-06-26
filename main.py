# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
يرسل كل نموذج جديد فور رفعه من المنصات التالية:
#- Thingiverse (جميع النماذج الجديدة منذ آخر فحص)
#- Printables.com (جميع العناصر الجديدة من RSS)
#- MakerWorld.com (جميع العناصر الجديدة من RSS)
مع الحفاظ على الاستقرار دون تغييرات كبيرة.
"""

import os, time, json, traceback, requests, xml.etree.ElementTree as ET
from threading import Thread, Lock
import cloudscraper
from flask import Flask
import sqlite3
import logging
import random
import socket
import http.client

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

#────ـ قفل للتحكم في معدل الإرسال ─────

send_lock = Lock()
last_send_time = 0

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
            requests.get(SELF_URL, timeout=10)
            logger.info("Self-ping successful")
        except Exception as e:
            logger.error(f"Self-ping failed: {str(e)}")
        time.sleep(300)

#────ـ تهيئة السكرابر مع إعدادات متقدمة ─────

def create_scraper():
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'linux',
            'desktop': True,
            'mobile': False
        },
        delay=15,
        interpreter='nodejs',
        captcha={
            'provider': 'return_response'
        }
    )

scraper = create_scraper()
TG_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"

# إعادة تهيئة السكرابر دورياً لتجنب مشاكل الاتصال
def reset_scraper():
    global scraper
    logger.info("Resetting scraper instance...")
    scraper = create_scraper()

#────ـ إرسال آمن إلى Telegram ─────

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

#────ـ طلبات متينة مع إعادة المحاولة ─────

def robust_request(url, method='GET', params=None, headers=None, max_retries=4, is_xml=False):
    """طلب مع إعادة محاولة ذكية وتجاوز الأخطاء الشبكية"""
    retry_delays = [5, 15, 30, 60]  # تأخير متزايد للإعادة
    
    for attempt in range(max_retries):
        try:
            # إعادة تهيئة السكرابر بعد المحاولة الثانية
            if attempt >= 2:
                reset_scraper()
            
            # إضافة رؤوس افتراضية إذا لم يتم توفيرها
            final_headers = headers or {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0',
                'Accept': 'application/xml' if is_xml else 'application/json',
                'Connection': 'keep-alive'
            }
            
            logger.info(f"Request attempt {attempt+1} to {url}")
            
            if method == 'GET':
                response = scraper.get(url, params=params, headers=final_headers, timeout=45)
            else:
                response = scraper.post(url, data=params, headers=final_headers, timeout=45)
            
            response.raise_for_status()
            return response
        
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                http.client.RemoteDisconnected,
                socket.gaierror,
                ConnectionResetError) as e:
            
            delay = retry_delays[attempt] if attempt < len(retry_delays) else 60
            logger.warning(f"Connection error ({type(e).__name__}), retrying in {delay}s: {str(e)}")
            time.sleep(delay)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                delay = 120 if attempt == 0 else 300
                logger.warning(f"Rate limited (429), retrying in {delay}s")
                time.sleep(delay)
            else:
                logger.error(f"HTTP error {e.response.status_code}: {str(e)}")
                return None
    
    logger.error(f"Failed after {max_retries} attempts for {url}")
    return None

#────ـ Thingiverse API ─────

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

#────ـ Printables.com via RSS ─────

def fetch_printables_items():
    try:
        url = "https://www.printables.com/sitemap.xml?format=rss"
        response = robust_request(url, is_xml=True)
        if not response:
            return []
            
        root = ET.fromstring(response.text)
        return root.findall("./channel/item")
    except Exception as e:
        logger.error(f"Printables RSS error: {str(e)}")
        return []

#────ـ MakerWorld.com via RSS ─────

def fetch_makerworld_items():
    try:
        url = "https://makerworld.com/sitemap.xml?format=rss"
        response = robust_request(url, is_xml=True)
        if not response:
            return []
            
        root = ET.fromstring(response.text)
        return root.findall("./channel/item")
    except Exception as e:
        logger.error(f"MakerWorld RSS error: {str(e)}")
        return []

#────ـ العامل الرئيسي مع تحسينات الموثوقية ─────

def worker():
    init_db()
    logger.info("Worker started")
    
    # تهيئة معدل الإرسال
    global last_send_time
    last_send_time = time.time() - 5  # السماح بالإرسال الفوري
    
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
                        link = item.find("link").text
                        if link == last_printables:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        # إرسال أحدث عنصر فقط
                        item = new_items[0]
                        title = item.find("title").text
                        link  = item.find("link").text
                        tg_text(f"🖨️ <b>[Printables]</b> <a href=\"{link}\">{title}</a>")
                        
                        # تحديث آخر معرف
                        set_last_id("printables", link)
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
                        link = item.find("link").text
                        if link == last_makerworld:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        # إرسال أحدث عنصر فقط
                        item = new_items[0]
                        title = item.find("title").text
                        link  = item.find("link").text
                        tg_text(f"🔧 <b>[MakerWorld]</b> <a href=\"{link}\">{title}</a>")
                        
                        # تحديث آخر معرف
                        set_last_id("makerworld", link)
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
        time.sleep(300 + random.randint(0, 120))  # فحص كل 5-7 دقائق

#────ـ تشغيل مقدّس ─────

if __name__ == "__main__":
    logger.info("Starting application...")
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.get