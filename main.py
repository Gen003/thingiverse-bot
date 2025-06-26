import telegram
import requests
from bs4 import BeautifulSoup
import asyncio
import os
import sys
import logging

# --- إعدادات السجلات (Logging) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('STL_Monitor')

# --- الإعدادات وقراءة المتغيرات ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')

if not BOT_TOKEN or not CHANNEL_ID:
    logger.critical("بيانات الاعتماد غير موجودة! تأكد من تعيين BOT_TOKEN و CHANNEL_ID.")
    sys.exit(1)

SENT_LINKS_FILE = 'sent_links.txt'
bot = telegram.Bot(token=BOT_TOKEN)

# --- دوال مساعدة ---
def load_sent_links():
    try:
        if not os.path.exists(SENT_LINKS_FILE):
            return set()
        with open(SENT_LINKS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f)
    except Exception as e:
        logger.error(f"خطأ في تحميل الروابط المرسلة: {e}")
        return set()

def save_sent_link(link):
    try:
        with open(SENT_LINKS_FILE, 'a', encoding='utf-8') as f:
            f.write(link + '\n')
    except Exception as e:
        logger.error(f"خطأ في حفظ الرابط: {e}")

# --- دالة الإرسال غير المتزامنة ---
async def send_to_telegram(title, link, image_url):
    try:
        domain = link.split('/')[2].replace('www.', '')
        message = f"<b>🎯 تصميم جديد على {domain}!</b>\n\n" \
                  f"<b>🏷️ الاسم:</b> {title}\n" \
                  f"<b>🔗 الرابط:</b> <a href='{link}'>اضغط هنا للتحميل</a>"

        # إرسال الرسالة مع الصورة (أو بدونها إذا فشل)
        if image_url:
            try:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=message,
                    parse_mode=telegram.ParseMode.HTML
                )
                logger.info(f"تم إرسال النموذج مع الصورة: {title}")
                return True
            except Exception as photo_error:
                logger.warning(f"فشل إرسال الصورة: {photo_error} - المحاولة بدون صورة")

        # إرسال بدون صورة إذا فشل الإرسال بالصورة
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode=telegram.ParseMode.HTML,
            disable_web_page_preview=False
        )
        logger.info(f"تم إرسال النموذج بدون صورة: {title}")
        return True
        
    except Exception as e:
        logger.error(f"فشل إرسال النموذج: {e}")
        return False

# --- دوال فحص المواقع (محدثة) ---
async def check_printables(sent_links):
    logger.info("جارٍ فحص Printables...")
    try:
        url = 'https://www.printables.com/model'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        models = soup.select('div[data-test-id="model-card"]', limit=7)
        
        for model in models:
            try:
                # استخراج البيانات
                link_tag = model.select_one('a[href^="/model/"]')
                if not link_tag: continue
                
                model_id = link_tag['href']
                full_link = f"https://www.printables.com{model_id}"
                if full_link in sent_links:
                    continue
                    
                title = link_tag.get_text(strip=True)
                img_tag = model.select_one('img[src]')
                image_url = img_tag['src'] if img_tag else None
                
                # إرسال التنبيه
                if await send_to_telegram(title, full_link, image_url):
                    sent_links.add(full_link)
                    save_sent_link(full_link)
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"خطأ في معالجة النموذج: {e}")
                
    except Exception as e:
        logger.error(f"فشل فحص Printables: {e}")

async def check_thingiverse(sent_links):
    logger.info("جارٍ فحص Thingiverse...")
    try:
        url = 'https://www.thingiverse.com/newest'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        models = soup.select('div[class^="ThingCard__container-"]', limit=7)
        
        for model in models:
            try:
                link_tag = model.select_one('a[href^="/thing:"]')
                if not link_tag: continue
                    
                relative_link = link_tag['href']
                full_link = f"https://www.thingiverse.com{relative_link}"
                if full_link in sent_links:
                    continue
                    
                title = link_tag.get_text(strip=True)
                img_tag = model.select_one('img[src]')
                image_url = img_tag['src'] if img_tag else None
                
                if await send_to_telegram(title, full_link, image_url):
                    sent_links.add(full_link)
                    save_sent_link(full_link)
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"خطأ في معالجة النموذج: {e}")
                
    except Exception as e:
        logger.error(f"فشل فحص Thingiverse: {e}")

async def check_makerworld(sent_links):
    logger.info("جارٍ فحص MakerWorld...")
    try:
        url = 'https://makerworld.com/en/models'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        models = soup.select('div.model-item', limit=7)
        
        for model in models:
            try:
                link_tag = model.select_one('a[href^="/en/models/"]')
                if not link_tag: continue
                    
                relative_link = link_tag['href']
                full_link = f"https://makerworld.com{relative_link}"
                if full_link in sent_links:
                    continue
                    
                title_tag = model.select_one('.model-title')
                title = title_tag.get_text(strip=True) if title_tag else "بلا عنوان"
                img_tag = model.select_one('img[src]')
                image_url = img_tag['src'] if img_tag else None
                
                if await send_to_telegram(title, full_link, image_url):
                    sent_links.add(full_link)
                    save_sent_link(full_link)
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"خطأ في معالجة النموذج: {e}")
                
    except Exception as e:
        logger.error(f"فشل فحص MakerWorld: {e}")

# --- الدورة الرئيسية ---
async def main():
    logger.info("--- بدء تشغيل بوت مراقبة STL ---")
    
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="🚀 بدأ البوت العمل بنجاح! جاري مراقبة المواقع..."
        )
    except Exception as e:
        logger.error(f"فشل إرسال رسالة البدء: {e}")

    sent_links = load_sent_links()
    logger.info(f"تم تحميل {len(sent_links)} رابط مرسل سابقاً")

    while True:
        await asyncio.gather(
            check_printables(sent_links),
            check_thingiverse(sent_links),
            check_makerworld(sent_links)
        )
        
        interval = 300  # 5 دقائق
        logger.info(f"تم الانتهاء من الدورة - الانتظار {interval//60} دقائق")
        await asyncio.sleep(interval)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("تم إيقاف البوت يدويًا")
    except Exception as e:
        logger.critical(f"انهيار غير متوقع: {e}")