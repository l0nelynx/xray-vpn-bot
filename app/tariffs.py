from app.settings import secrets
price_discount = secrets.get('discount')

tariffs_stars = {
    'month': {
        'days': '30',
        'disc': '0',
        'currency': '⭐️',
        'period': '1 Месяц'
    },
    '3 month': {
        'days': '90',
        'disc': f'{price_discount}',
        'currency': '⭐️',
        'period': '3 Месяца'
    },
    '12 month': {
        'days': '360',
        'disc': f'{price_discount}',
        'currency': '⭐️',
        'period': 'Год'
    }
}
tariffs_crypto = {
    'month': {
        'days': '30',
        'disc': '0',
        'currency': 'USDT',
        'period': '1 Месяц'
    },
    '3 month': {
        'days': '90',
        'disc': f'{price_discount}',
        'currency': 'USDT',
        'period': '3 Месяца'
    },
    '12 month': {
        'days': '360',
        'disc': f'{price_discount}',
        'currency': 'USDT',
        'period': 'Год'
    }
}

tariffs_sbp = {
    'month': {
        'days': '30',
        'disc': '0',
        'currency': 'RUB',
        'period': '1 Месяц'
    },
    '3 month': {
        'days': '90',
        'disc': f'{price_discount}',
        'currency': 'RUB',
        'period': '3 Месяца'
    },
    '12 month': {
        'days': '360',
        'disc': f'{price_discount}',
        'currency': 'RUB',
        'period': 'Год'
    }
}
