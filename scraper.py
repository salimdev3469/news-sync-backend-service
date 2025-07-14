import os
import json
import requests
import xml.etree.ElementTree as ET
import re
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
from dateutil import parser

# FIREBASE INIT (Environment Variable üzerinden)
firebase_creds = json.loads(os.environ["FIREBASE_CREDENTIALS"])
cred = credentials.Certificate(firebase_creds)
firebase_app = initialize_app(cred)
db = firestore.client()

# Tüm iller
CITIES = [
    'Adana', 'Adıyaman', 'Afyonkarahisar', 'Ağrı', 'Aksaray', 'Amasya',
    'Ankara', 'Antalya', 'Ardahan', 'Artvin', 'Aydın', 'Balıkesir', 'Bartın',
    'Batman', 'Bayburt', 'Bilecik', 'Bingöl', 'Bitlis', 'Bolu', 'Burdur',
    'Bursa', 'Çanakkale', 'Çankırı', 'Çorum', 'Denizli', 'Diyarbakır',
    'Düzce', 'Edirne', 'Elazığ', 'Erzincan', 'Erzurum', 'Eskişehir',
    'Gaziantep', 'Giresun', 'Gümüşhane', 'Hakkâri', 'Hatay', 'Iğdır',
    'Isparta', 'İstanbul', 'İzmir', 'Kahramanmaraş', 'Karabük', 'Karaman',
    'Kars', 'Kastamonu', 'Kayseri', 'Kilis', 'Kırıkkale', 'Kırklareli',
    'Kırşehir', 'Kocaeli', 'Konya', 'Kütahya', 'Malatya', 'Manisa', 'Mardin',
    'Mersin', 'Muğla', 'Muş', 'Nevşehir', 'Niğde', 'Ordu', 'Osmaniye',
    'Rize', 'Sakarya', 'Samsun', 'Siirt', 'Sinop', 'Sivas', 'Şanlıurfa',
    'Şırnak', 'Tekirdağ', 'Tokat', 'Trabzon', 'Tunceli', 'Uşak', 'Van',
    'Yalova', 'Yozgat', 'Zonguldak',
]

RSS_FEEDS = {
    "Manşet": "https://www.trthaber.com/manset_articles.rss",
    "Son Dakika": "https://www.trthaber.com/sondakika_articles.rss",
    "Koronavirüs": "https://www.trthaber.com/koronavirus_articles.rss",
    "Gündem": "https://www.trthaber.com/gundem_articles.rss",
    "Türkiye": "https://www.trthaber.com/turkiye_articles.rss",
    "Dünya": "https://www.trthaber.com/dunya_articles.rss",
    "Ekonomi": "https://www.trthaber.com/ekonomi_articles.rss",
    "Spor": "https://www.trthaber.com/spor_articles.rss",
    "Yaşam": "https://www.trthaber.com/yasam_articles.rss",
    "Sağlık": "https://www.trthaber.com/saglik_articles.rss",
    "Kültür Sanat": "https://www.trthaber.com/kultur_sanat_articles.rss",
    "Bilim Teknoloji": "https://www.trthaber.com/bilim_teknoloji_articles.rss",
    "Güncel": "https://www.trthaber.com/guncel_articles.rss",
    "Eğitim": "https://www.trthaber.com/egitim_articles.rss",
    "İnfografik": "https://www.trthaber.com/infografik_articles.rss",
    "İnteraktif": "https://www.trthaber.com/interaktif_articles.rss",
    "Özel Haber": "https://www.trthaber.com/ozel_haber_articles.rss",
    "Dosya Haber": "https://www.trthaber.com/dosya_haber_articles.rss"
}


def extract_image_and_text(description_html):
    img_regex = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)
    img_match = img_regex.search(description_html)
    image_url = img_match.group(1) if img_match else None

    cleaned_html = img_regex.sub("", description_html).strip()
    text_only = re.sub(r"<.*?>", "", cleaned_html).strip()

    return image_url, text_only


def clean_text(text):
    if text:
        text = text.encode('utf-8').decode('utf-8-sig')
        text = text.strip()

        # Bitişik kelimeleri ayır
        text = re.sub(r"(?<=[a-zçğıöşü])(?=[A-ZÇĞİÖŞÜ])", " ", text)

        # \n, \t temizle
        text = text.replace("\n", " ").replace("\t", " ")

        # Semboller temizle
        text = re.sub(r"[\|\*\"\'\\\[\]\(\)\{\}\<\>/]", "", text)
        text = re.sub(r"\\+", "", text)

        # Fazla boşlukları tek boşluk yap
        text = re.sub(r"\s{2,}", " ", text)
    return text



def get_news_content(news_url):
    try:
        resp = requests.get(news_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        news_div = soup.find(class_="news-content")
        if news_div:
            paragraphs = news_div.find_all("p")
            text = "\n\n".join([clean_text(p.get_text(strip=True)) for p in paragraphs])
            return text
        else:
            return ""
    except Exception as e:
        print(f"Detay sayfası hatası ({news_url}): {str(e)}")
        return ""


def detect_cities(text):
    found = []
    for city in CITIES:
        if city.lower() in text.lower():
            found.append(city)
    return found


def format_publish_date(raw_date_str):
    if not raw_date_str:
        return None

    try:
        # BOM temizle, boşluk kırp
        raw_date_str = raw_date_str.strip().lstrip('\ufeff')

        dt = parser.parse(raw_date_str)

        turkish_months = {
            "January": "Ocak",
            "February": "Şubat",
            "March": "Mart",
            "April": "Nisan",
            "May": "Mayıs",
            "June": "Haziran",
            "July": "Temmuz",
            "August": "Ağustos",
            "September": "Eylül",
            "October": "Ekim",
            "November": "Kasım",
            "December": "Aralık"
        }

        month_name_en = dt.strftime("%B")
        month_name_tr = turkish_months.get(month_name_en, month_name_en)

        formatted = f"{dt.day} {month_name_tr} {dt.year}, {dt.strftime('%H:%M')}"
        return formatted

    except Exception as e:
        print(f"Tarih parse hatası: {raw_date_str} → {e}")
        return raw_date_str



def fetch_and_save_trt_news(limit_per_category=5):
    for category, feed_url in RSS_FEEDS.items():
        print(f"Fetching: {category}")

        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            items = root.findall("./channel/item")

            for item in items[:limit_per_category]:
                raw_title = item.findtext("title") or ""
                title = clean_text(raw_title)

                link = item.findtext("link")
                description_html = item.findtext("description") or ""

                image_url, short_content = extract_image_and_text(description_html)

                if not image_url:
                    print(f"Skipped news without image: {title}")
                    continue

                detailed_content = get_news_content(link)
                final_content = detailed_content if detailed_content else short_content
                final_content = clean_text(final_content)

                if not final_content.strip():
                    print(f"Skipped news without content: {title}")
                    continue

                cities_found = detect_cities(final_content)

                pub_date_raw = item.findtext("pubDate") or ""
                formatted_date = format_publish_date(pub_date_raw)

                # --- BURADA DUPLICATE KONTROLÜ ---
                existing_docs = db.collection("Articles")\
                    .where("title", "==", title )\
                    .limit(1)\
                    .get()

                if existing_docs:
                    print(f"Skipped (duplicate): {title}")
                    continue
                # -----------------------------------

                news_data = {
                    "created_at_server": datetime.utcnow().isoformat() + "Z",
                    "image_url": image_url,
                    "publish_date_str": formatted_date,
                    "source_name": "TRT Haber",
                    "title": title,
                    "url": link,
                    "category": category,
                    "content": final_content,
                    "cities": cities_found
                }

                db.collection("Articles").add(news_data)
                print(f"Added: {title}")

        except Exception as e:
            print(f"Error fetching {category}: {str(e)}")


if __name__ == "__main__":
    fetch_and_save_trt_news(limit_per_category=1)
