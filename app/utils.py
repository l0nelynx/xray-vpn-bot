from aiocrystal.v3.async_crystal import CrystalPay
from aiocrystal.utils.types import CallbackInvoice, InvoiceState
from aiocrystal.webhook import FastApiManager
from app.settings import app_uvi, secrets


host = secrets.get('crystal_webhook_host')

# noinspection PyTypeChecker
cp = CrystalPay(auth_login=secrets.get('crystal_login'),
                auth_secret=secrets.get('crystal_secret'),
                salt=secrets.get('crystal_salt'),
                webhook_manager=FastApiManager(app_fastapi=app_uvi, end_point_invoice='/pay/crystalpay')
                )


# # пример фильтрации
# async def is_payed(invoice: CallbackInvoice):
#     return invoice.rub_amount >= 100
#
#
# async def anti_unavailable_is_payed(invoice: CallbackInvoice):
#     return invoice.state == InvoiceState.payed
#
#
# @cp.callback_invoice(is_payed, anti_unavailable_is_payed)  # <- возможность добавлять несколько фильтров
# async def pay_cp(invoice: CallbackInvoice):
#     print(f'Пришло: {invoice.rub_amount}')

#
# async def create_smart_invoice():
#     invoice = await cp.invoice.create(100, callback_url=f'{host}/pay/crystalpay')
#     print(invoice.url)
#     return invoice.url


# Here some utils
def discount(price, dis_amount):
    return (price * 3) * (1 - dis_amount)
