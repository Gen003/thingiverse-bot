# -*- coding: utf-8 -*-

""" Thingiverse → Telegram  ❚  د. إيرك 2025
نظام متكامل لجلب أحدث النماذج من مصادر متعددة مع تجاوز الحظر
"""

import os, time, json, traceback, random
from threading import Thread, Lock
from flask import Flask
import sqlite3
import logging
import requests
from bs4 import BeautifulSoup
import cloudscraper  # إضافة مكتبة لتجاوز حماية Cloudflare

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

# ------ إرسال آمن إلى Telegram ------
def safe_send_message(payload, is_photo=False):
    global last_send_time
    endpoint = "sendPhoto" if is_photo else "sendMessage"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
    
    with send_lock:
        # التحكم في معدل الإرسال (رسالة كل 5-8 ثوان)
        elapsed = time.time() - last_send_time
        if elapsed < 5:
            wait_time = 5 + random.uniform(0, 3) - elapsed
            logger.info(f"Rate limiting: Waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            last_send_time = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            if "Too Many Requests" in str(e):
                wait_time = 45 + random.randint(0, 30)
                logger.warning(f"Too Many Requests! Waiting {wait_time}s")
                time.sleep(wait_time)
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

# ------ جلب المحتوى باستخدام تقنيات متقدمة لتجاوز الحظر ------
def fetch_html(url):
    # توليد وكيل عشوائي جديد لكل طلب
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1"
    ]
    
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.google.com/'
    }
    
    # تقنية متقدمة لتجاوز حماية Cloudflare
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
        logger.warning(f"Cloudscraper request failed with status: {response.status_code}")
    except Exception as e:
        logger.warning(f"Cloudscraper failed: {str(e)}")
    
    # المحاولة الثانية مع طلبات عادية
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
        logger.warning(f"Direct request failed with status: {response.status_code}")
    except Exception as e:
        logger.warning(f"Direct request failed: {str(e)}")
    
    # المحاولة الثالثة مع وكيل (إذا فشلت الطرق السابقة)
    proxies = [
        "http://45.94.47.66:8110",
        "http://193.122.71.184:3128",
        "http://103.155.54.137:83",
        "http://47.88.3.19:8080",
        "http://8.219.97.248:80"
    ]
    
    try:
        proxy = {"http": random.choice(proxies), "https": random.choice(proxies)}
        response = requests.get(url, headers=headers, proxies=proxy, timeout=25)
        if response.status_code == 200:
            return response.text
        logger.warning(f"Proxy request failed with status: {response.status_code}")
    except Exception as e:
        logger.error(f"Proxy request failed: {str(e)}")
    
    return None

# ------ Thingiverse (بديل للـ API) ------
def scrape_thingiverse_latest():
    try:
        url = "https://www.thingiverse.com/newest"
        content = fetch_html(url)
        if not content:
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        items = []
        
        for card in soup.select('div.thing-card'):
            try:
                thing_id = card.select_one('a')['href'].split(':')[-1]
                title = card.select_one('h3.name').text.strip()
                link = f"https://www.thingiverse.com/thing:{thing_id}"
                thumb = card.select_one('img')['src']
                
                items.append({
                    'id': thing_id,
                    'title': title,
                    'link': link,
                    'thumb': thumb
                })
            except Exception as e:
                logger.warning(f"Error parsing Thingiverse card: {str(e)}")
                continue
        
        return items
    except Exception as e:
        logger.error(f"Thingiverse scraping error: {str(e)}")
        return []

# ------ Printables.com Scraping ------
def scrape_printables_latest():
    try:
        url = "https://www.printables.com/explore/newest"
        content = fetch_html(url)
        if not content:
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        items = []
        
        for card in soup.select('div[data-test-id="model-card"]'):
            try:
                model_id = card.select_one('a')['href'].split('/')[-1]
                title = card.select_one('h3[data-test-id="model-card-name"]').text.strip()
                link = f"https://www.printables.com/model/{model_id}"
                
                items.append({
                    'id': model_id,
                    'title': title,
                    'link': link
                })
            except Exception as e:
                logger.warning(f"Error parsing Printables card: {str(e)}")
                continue
        
        return items
    except Exception as e:
        logger.error(f"Printables scraping error: {str(e)}")
        return []

# ------ MakerWorld.com Scraping ------
def scrape_makerworld_latest():
    try:
        url = "https://makerworld.com/explore?tab=newest"
        content = fetch_html(url)
        if not content:
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        items = []
        
        for card in soup.select('div.model-item'):
            try:
                model_id = card.select_one('a')['href'].split('/')[-1]
                title = card.select_one('.model-name').text.strip()
                link = f"https://makerworld.com/models/{model_id}"
                
                items.append({
                    'id': model_id,
                    'title': title,
                    'link': link
                })
            except Exception as e:
                logger.warning(f"Error parsing MakerWorld card: {str(e)}")
                continue
        
        return items
    except Exception as e:
        logger.error(f"MakerWorld scraping error: {str(e)}")
        return []

# ------ العامل الرئيسي مع تحسينات كبرى ------
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
                items = scrape_thingiverse_latest()
                
                if items:
                    new_items = []
                    for item in items:
                        if item['id'] == last_thingiverse:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        # إرسال أحدث عنصر
                        item = new_items[0]
                        tg_photo(
                            item['thumb'],
                            f"📦 <b>[Thingiverse]</b> {item['title']}",
                            item['link'],
                            item['link']
                        )
                        
                        # تحديث آخر معرف
                        set_last_id("thingiverse_newest", new_items[0]['id'])
                        logger.info(f"Sent 1 new Thingiverse item. {len(new_items)-1} remaining")
            except Exception as e:
                error_msg = f"❌ خطأ في Thingiverse: {str(e)[:300]}"
                logger.error(error_msg)
                time.sleep(10)
            
            # الانتظار قبل المصدر التالي
            time.sleep(20)
            
            # Printables
            try:
                last_printables = get_last_id("printables")
                items = scrape_printables_latest()
                
                if items:
                    new_items = []
                    for item in items:
                        if item['id'] == last_printables:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        # إرسال أحدث عنصر
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
            time.sleep(20)
            
            # MakerWorld
            try:
                last_makerworld = get_last_id("makerworld")
                items = scrape_makerworld_latest()
                
                if items:
                    new_items = []
                    for item in items:
                        if item['id'] == last_makerworld:
                            break
                        new_items.append(item)
                    
                    if new_items:
                        # إرسال أحدث عنصر
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
            time.sleep(60)
        
        logger.info("Cycle completed. Sleeping...")
        time.sleep(300 + random.randint(0, 120))

# ------ تشغيل التطبيق ------
if __name__ == "__main__":
    logger.info("Starting application...")
    Thread(target=worker, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))