import telegram
import requests
from bs4 import BeautifulSoup
import asyncio
import os
import sys

# --- الإعدادات وقراءة المتغيرات ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')

if not BOT_TOKEN or not CHANNEL_ID:
    print("[خطأ فادح] لم يتم العثور على متغيرات البيئة. يرجى إضافتها في Render.")
    sys.exit(1)

SENT_LINKS_FILE = 'sent_links.txt'
bot = telegram.Bot(token=BOT_TOKEN)

# --- دوال مساعدة ---
def load_sent_links():
    if not os.path.exists(SENT_LINKS_FILE):
        return set()
    with open(SENT_LINKS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

def save_sent_link(link):
    with open(SENT_LINKS_FILE, 'a', encoding='utf-8') as f:
        f.write(link + '\n')

# --- دالة الإرسال غير المتزامنة ---
async def send_to_telegram(title, link, image_url):
    try:
        message = f"<b>تصميم جديد تم رصده!</b>\n\n" \
                  f"<b>الاسم:</b> {title}\n" \
                  f"<b>المصدر:</b> {link.split('/')[2]}\n" \
                  f"<b>الرابط:</b> <a href='{link}'>اضغط هنا للتحميل</a>"

        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=message,
            parse_mode=telegram.ParseMode.HTML
        )
        print(f"تم إرسال: {title}")
        return True
    except Exception as e:
        print(f"حدث خطأ أثناء إرسال التصميم: {e}")
        return False

# --- دوال فحص المواقع (كلها async الآن) ---

async def check_printables(sent_links):
    print("\n[INFO] جار فحص Printables...")
    try:
        url = 'https://www.printables.com/en/new'
        headers = {'User-Agent': 'Mozilla/5.0'}
        # تشغيل طلب الويب المتزامن في خيط منفصل لتجنب حظر الحلقة
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
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
                if image_url and title and await send_to_telegram(title, full_link, image_url):
                    sent_links.add(full_link)
                    save_sent_link(full_link)
                    await asyncio.sleep(3) # فاصل لطيف بين الرسائل
    except Exception as e:
        print(f"[ERROR] فشل فحص Printables: {e}")

async def check_thingiverse(sent_links):
    print("\n[INFO] جار فحص Thingiverse...")
    try:
        url = 'https://www.thingiverse.com/newest'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        new_things = soup.find_all('div', class_='Card__card--', limit=5) # قد يتغير هذا المحدد
        for thing in new_things:
            link_tag = thing.find('a', class_='Card__link--')
            if not link_tag: continue
            full_link = f"https://www.thingiverse.com{link_tag['href']}"
            if full_link not in sent_links:
                title = link_tag.get('title', 'بلا عنوان')
                img_tag = thing.find('img', class_='Card__image--')
                image_url = img_tag.get('src') if img_tag else None
                if image_url and await send_to_telegram(title, full_link, image_url):
                    sent_links.add(full_link)
                    save_sent_link(full_link)
                    await asyncio.sleep(3)
    except Exception as e:
        print(f"[ERROR] فشل فحص Thingiverse: {e}")

async def check_makerworld(sent_links):
    print("\n[INFO] جار فحص MakerWorld...")
    try:
        url = 'https://makerworld.com/en/models/new'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
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
                if image_url and await send_to_telegram(title, full_link, image_url):
                    sent_links.add(full_link)
                    save_sent_link(full_link)
                    await asyncio.sleep(3)
    except Exception as e:
        print(f"[ERROR] فشل فحص MakerWorld: {e}")

async def main():
    """الدالة الرئيسية غير المتزامنة التي تدير كل شيء"""
    print("--- مرصد المجسمات الرقمية يعمل الآن (النظام غير المتزامن) ---")
    
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text="🛰️ وحدة 'مرصد المجسمات' بدأت العمل. جميع المستشعرات نشطة.")
        print("[INFO] تم إرسال رسالة بدء التشغيل إلى تليجرام.")
    except Exception as e:
        print(f"[ERROR] فشل إرسال رسالة بدء التشغيل: {e}")

    sent_links = load_sent_links()
    print(f"[INFO] تم تحميل {len(sent_links)} رابط مرسل سابقاً.")

    while True:
        # === تفعيل جميع المستشعرات ===
        await check_printables(sent_links)
        await check_thingiverse(sent_links)
        await check_makerworld(sent_links)
        
        wait_time = 120
        print(f"\n... اكتمل الفحص الدوري، في وضع الاستعداد لمدة {int(wait_time / 60)} دقيقة ...")
        await asyncio.sleep(wait_time)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] تم إيقاف المرصد يدويًا.")
