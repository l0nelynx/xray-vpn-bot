import requests
import json
import sys
import os

#sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

#from app.settings import secrets

# url = secrets.get('webhook_host')
# headers = {
#     'Content-Type': 'application/json',
#     'X-MerchantId': f'{secrets.get("platega_merchant_id")}',
#     'X-Secret': f'{secrets.get("platega_api_key")}'
#
# }
# body = {
#     'id': '5f315be7-dfc5-4791-8352-d2c879d9772b',
#     'amount': 100.50,
#     'currency': 'USD',
#     'status': "CONFIRMED",
#     'paymentMethod': 2
# }
url_new = 'http://0.0.0.0:5000/digiseller_webhook'
headers_new = {
    'Content-Type': 'application/json'

}
body_new = {"id": "5422669", "inv": "0", "amount": "0.00", "type_curr": "WMZ",
            "sign": "45f5bccfdd0139e0fc88eac58e76b3a5", "lang": "",
            "options": [{"id": "3883638", "type": "radio", "user_data": "15130377"}]}

response = requests.post(url_new, headers=headers_new, json=body_new, verify=True)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
