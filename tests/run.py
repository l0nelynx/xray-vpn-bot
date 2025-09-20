import requests
import json
import sys
import os

url_new = 'http://0.0.0.0:5000/digiseller_webhook'
headers_new = {
    'Content-Type': 'application/json'
}
body_new = {}

response = requests.post(url_new, headers=headers_new, json=body_new, verify=True)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
