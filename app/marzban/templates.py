vless_template = {
    "username": "user1234",
    "proxies": {
        "vless": {
            "id": "35e4e39c-7d5c-4f4b-8b71-558e4f37ff53",
            "flow": "xtls-rprx-vision"
        }
    },
    "inbounds": {
        "vless": [
            "VLESS+TCP+REALITY+9696",
            "VLESS+XHTTP+REALITY+9797"
        ]
    },
    "expire": 0,
    "data_limit": 0,
    "data_limit_reset_strategy": "no_reset",
    "status": "active",
    "note": "",
    "on_hold_timeout": "2023-11-03T20:30:00",
    "on_hold_expire_duration": 0
}