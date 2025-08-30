import requests
import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.settings import secrets

url = secrets.get('webhook_host')
headers = {
    'Content-Type': 'application/json',
    'X-MerchantId': f'{secrets.get("platega_merchant_id")}',
    'X-Secret': f'{secrets.get("platega_api_key")}'

}
body = {
    'id': '5f315be7-dfc5-4791-8352-d2c879d9772b',
    'amount': 100.50,
    'currency': 'USD',
    'status': "CONFIRMED",
    'paymentMethod': 2
}

response = requests.post(url, headers=headers, json=body, verify=True)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
