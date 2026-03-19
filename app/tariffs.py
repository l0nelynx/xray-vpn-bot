from app.settings import secrets


def _disc():
    return str(secrets.get('discount', 0))


def get_tariffs_stars():
    return {
        'month': {
            'days': '30',
            'disc': '0',
            'currency': '⭐️',
            'period': '1 Месяц'
        },
        '3 month': {
            'days': '90',
            'disc': _disc(),
            'currency': '⭐️',
            'period': '3 Месяца'
        },
        '12 month': {
            'days': '360',
            'disc': _disc(),
            'currency': '⭐️',
            'period': 'Год'
        }
    }


def get_tariffs_crypto():
    return {
        'month': {
            'days': '30',
            'disc': '0',
            'currency': 'USDT',
            'period': '1 Месяц'
        },
        '3 month': {
            'days': '90',
            'disc': _disc(),
            'currency': 'USDT',
            'period': '3 Месяца'
        },
        '12 month': {
            'days': '360',
            'disc': _disc(),
            'currency': 'USDT',
            'period': 'Год'
        }
    }


def get_tariffs_sbp():
    return {
        'month': {
            'days': '30',
            'disc': '0',
            'currency': 'RUB',
            'period': '1 Месяц'
        },
        '3 month': {
            'days': '90',
            'disc': _disc(),
            'currency': 'RUB',
            'period': '3 Месяца'
        },
        '12 month': {
            'days': '360',
            'disc': _disc(),
            'currency': 'RUB',
            'period': 'Год'
        }
    }


# Обратная совместимость: модульные имена через __getattr__
def __getattr__(name):
    _map = {
        'tariffs_stars': get_tariffs_stars,
        'tariffs_crypto': get_tariffs_crypto,
        'tariffs_sbp': get_tariffs_sbp,
    }
    if name in _map:
        return _map[name]()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
