import http.client
import json
import time
import hashlib
from app.settings import secrets

conn = http.client.HTTPSConnection("seller.ggsel.net")

async def get_token():
    timestamp = time.time()
    sign = f"{secrets.get('ggsel_api_key')}"+f"{timestamp}"
    sign = hashlib.sha256(sign.encode("utf-8"))
    payload = json.dumps({
      "seller_id": secrets.get("ggsel_seller_id"),
      "timestamp": timestamp,
      "sign": f"{sign}"
    })
    print(payload)
    headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }
    conn.request("POST", "/api_sellers/api/apilogin", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))
    return json.loads(data.decode("utf-8"))

async def send_message(id_i: int, message: str):
    payload = json.dumps({
        "message": f"{message}"
    })
    headers = {
        'Content-Type': 'application/json'
    }
    token = await get_token()
    conn.request("POST", f"/api_sellers/api/debates/v2?token={token}&id_i={id_i}", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))