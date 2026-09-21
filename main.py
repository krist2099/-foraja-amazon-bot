import os
import requests
from fastapi import FastAPI

app = FastAPI()

AMAZON_CLIENT_ID = os.getenv("AMAZON_CLIENT_ID")
AMAZON_CLIENT_SECRET = os.getenv("AMAZON_CLIENT_SECRET")
AMAZON_PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG", "boydraku20-20")
WHAPI_TOKEN = os.getenv("WHAPI_TOKEN")
WHATSAPP_CHANNEL_ID = os.getenv("WHATSAPP_CHANNEL_ID")
MIN_DISCOUNT_PERCENT = float(os.getenv("MIN_DISCOUNT_PERCENT", "20"))

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
API_URL = "https://creatorsapi.amazon/catalog/v1/searchItems"
WHAPI_URL = "https://gate.whapi.cloud/messages/text"

def get_amazon_token():
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": AMAZON_CLIENT_ID,
        "client_secret": AMAZON_CLIENT_SECRET,
        "scope": "creatorsapi"
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def search_amazon(keywords):
    token = get_amazon_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-marketplace": "www.amazon.com",
    }
    payload = {
        "partnerTag": AMAZON_PARTNER_TAG,
        "marketplace": "www.amazon.com",
        "keywords": keywords,
        "searchIndex": "All",
        "itemCount": 10,
        "resources": [
            "images.primary.medium",
            "itemInfo.title",
            "offersV2.listings.price",
            "offersV2.listings.savings",
            "offersV2.listings.dealDetails",
            "offersV2.listings.availability",
            "offersV2.listings.startTime",
            "offersV2.listings.endTime",
        ],
    }
    r = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def value(obj, *keys):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur

def build_messages(data):
    items = data.get("itemsResult", {}).get("items", [])
    messages = []
    for item in items:
        title = value(item, "itemInfo", "title", "displayValue") or "Oferta de Amazon"
        url = item.get("detailPageURL")
        listings = value(item, "offersV2", "listings") or []
        if not listings:
            continue
        listing = listings[0]
        price = value(listing, "price", "money", "amount")
        savings = value(listing, "savings", "money", "amount")
        percent = value(listing, "savings", "percentage")
        if percent is None or not url:
            continue
        try:
            percent = float(percent)
        except (TypeError, ValueError):
            continue
        if percent < MIN_DISCOUNT_PERCENT:
            continue
        text = (
            "🔥 OFERTA EN AMAZON\n\n"
            f"🛍️ {title}\n\n"
            f"💰 Precio: ${price if price is not None else 'Ver en Amazon'}\n"
            f"💸 Ahorro: ${savings if savings is not None else 'Ver en Amazon'}\n"
            f"📉 Descuento: {percent:.0f}%\n\n"
            f"🛒 Comprar en Amazon: {url}\n\n"
            "📢 Ofertas Foraja de Amazon"
        )
        messages.append(text)
    return messages

def send_whatsapp(text):
    r = requests.post(
        WHAPI_URL,
        headers={"Authorization": f"Bearer {WHAPI_TOKEN}", "Content-Type": "application/json"},
        json={"to": WHATSAPP_CHANNEL_ID, "body": text},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

@app.get("/")
def root():
    return {"status": "ok", "service": "Ofertas Foraja de Amazon"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/run-deals")
def run_deals(keywords: str = "amazon deals"):
    data = search_amazon(keywords)
    messages = build_messages(data)
    sent = 0
    for msg in messages:
        send_whatsapp(msg)
        sent += 1
    return {"found_eligible_offers": len(messages), "sent": sent}
