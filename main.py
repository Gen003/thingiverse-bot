import telegram
import requests
from bs4 import BeautifulSoup
import time
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
APP_TOKEN = os.getenv("APP_TOKEN")
PORT      = int(os.getenv("PORT", "10000"))

assert all([BOT_TOKEN, CHAT_ID, APP_TOKEN]), "Missing environment variables."

# --- ملف لتخزين الروابط التي تم إرسالها لتجنب التكرار ---
SENT_LINKS_FILE = 'sent_links.txt'

# --- تهيئة البوت ---
# تأكد من أن إصدار مكتبة python-telegram-bot متوافق. إذا واجهت مشاكل، قد تحتاج إلى تثبيت إصدار محدد.
# pip install python-telegram-bot==13.7
bot = telegram.Bot(token=BOT_TOKEN)

def load_sent_links():
    """تحميل الروابط المرسلة سابقاً من الملف"""
    if not os.path.exists(SENT_LINKS_FILE):
        return set()
    with open(SENT_LINKS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

def save_sent_link(link):
    """حفظ رابط جديد في الملف"""
    with open(SENT_LINKS_FILE, 'a', encoding='utf-8') as f:
        f.write(link + '\n')

def send_to_telegram(title, link, image_url):
    """إرسال البيانات إلى قناة التليجرام"""
    try:
        message = f"<b>تصميم جديد تم رصده!</b>\n\n" \
                  f"<b>الاسم:</b> {title}\n" \
                  f"<b>المصدر:</b> {link.split('/')[2]}\n" \
                  f"<b>الرابط:</b> <a href='{link}'>اضغط هنا للتحميل</a>"

        bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=message,
            parse_mode=telegram.ParseMode.HTML
        )
        print(f"تم إرسال: {title}")
        return True
    except Exception as e:
        print(f"حدث خطأ أثناء الإرسال إلى تليجرام: {e}")
        return False

def check_printables(sent_links):
    """فحص موقع Printables.com عن أحدث التصاميم"""
    print("\n[INFO] جار فحص Printables...")
    try:
        url = 'https://www.printables.com/en/new'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')

        # ملاحظة: قد تتغير هذه المحددات إذا تغير تصميم الموقع
        new_models = soup.find_all('div', class_='print-card', limit=5)

        for model in new_models:
            link_tag = model.find('a', class_='link')
            if not link_tag: continue

            relative_link = link_tag['href']
            full_link = f"https://www.printables.com{relative_link.split('?')[0]}"
            
            if full_link not in sent_links:
                title = link_tag.text.strip()
                img_tag = model.find('img')
                image_url = img_tag.get('src') if img_tag else None

                if image_url and title:
                    if send_to_telegram(title, full_link, image_url):
                        sent_links.add(full_link)
                        save_sent_link(full_link)
                        time.sleep(3) # فاصل زمني بسيط بين الرسائل
    except Exception as e:
        print(f"[ERROR] فشل فحص Printables: {e}")

def check_thingiverse(sent_links):
    """فحص موقع Thingiverse.com عن أحدث التصاميم"""
    print("\n[INFO] جار فحص Thingiverse...")
    try:
        url = 'https://www.thingiverse.com/newest'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')

        # ملاحظة: قد تتغير هذه المحددات إذا تغير تصميم الموقع
        new_things = soup.find_all('div', class_='Card__card--', limit=5)

        for thing in new_things:
            link_tag = thing.find('a', class_='Card__link--')
            if not link_tag: continue
            
            full_link = f"https://www.thingiverse.com{link_tag['href']}"

            if full_link not in sent_links:
                title = link_tag.get('title', 'بلا عنوان')
                img_tag = thing.find('img', class_='Card__image--')
                image_url = img_tag.get('src') if img_tag else None
                
                if image_url:
                    if send_to_telegram(title, full_link, image_url):
                        sent_links.add(full_link)
                        save_sent_link(full_link)
                        time.sleep(3)
    except Exception as e:
        print(f"[ERROR] فشل فحص Thingiverse: {e}")


def check_makerworld(sent_links):
    """فحص موقع MakerWorld.com عن أحدث التصاميم"""
    print("\n[INFO] جار فحص MakerWorld...")
    try:
        url = 'https://makerworld.com/en/models/new'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ملاحظة: قد تتغير هذه المحددات إذا تغير تصميم الموقع
        new_models = soup.find_all('div', class_='card-model-item', limit=5)

        for model in new_models:
            link_tag = model.find('a')
            if not link_tag: continue
            
            relative_link = link_tag['href']
            full_link = f"https://makerworld.com{relative_link}"

            if full_link not in sent_links:
                title_tag = model.find('div', class_='model-title')
                title = title_tag.text.strip() if title_tag else "بلا عنوان"
                img_tag = model.find('img', class_='w-full')
                image_url = img_tag.get('src') if img_tag else None

                if image_url:
                    if send_to_telegram(title, full_link, image_url):
                        sent_links.add(full_link)
                        save_sent_link(full_link)
                        time.sleep(3)
    except Exception as e:
        print(f"[ERROR] فشل فحص MakerWorld: {e}")


if __name__ == '__main__':
    print("--- مرصد المجسمات الرقمية يعمل الآن ---")
    sent_links = load_sent_links()
    print(f"[INFO] تم تحميل {len(sent_links)} رابط مرسل سابقاً.")

    while True:
        check_printables(sent_links)
        check_thingiverse(sent_links)
        check_makerworld(sent_links)
        
        # --- فترة الانتظار قبل الفحص التالي (بالثواني) ---
        # 3600 ثانية = 1 ساعة
        wait_time = 3600
        print(f"\n... اكتمل الفحص الدوري، في وضع الاستعداد لمدة {int(wait_time / 60)} دقيقة ...")
        time.sleep(wait_time)

