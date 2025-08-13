from fkassa import FreeKassa, PaymentSystem


free_kassa = FreeKassa(
    shop_id=64548,
    api_key="45cfe1e82e69f69ba43e5efd7dbc6eb3",
    secret_word_1='vM//M}KBq_}jB.4'
)
 #payment_link = free_kassa.create_payment_link(
#     order_id='order_001',
#     amount=1000.0,
#     currency='RUB'
# )
#print(f"Ссылка на оплату: {payment_link}")

order_response = free_kassa.create_order(
    order_id='order_003',
    ip='82.22.184.87',
    amount=1500.0,
    currency='RUB',
    email='exec@example.com'
 )
print(f"Созданный заказ ID: {order_response.fk_id}, Ссылка: {order_response.url}")
    # orders_response = free_kassa.get_orders()
    # print(orders_response)
    # for order in orders_response.orders:
    #     print(f"Заказ ID: {order.id}, Статус: {order.status}")
status_response = free_kassa.check_payment_system_status(PaymentSystem.SBP)
if status_response.type == "success":
    print("Платежная система доступна.")
else:
    print(f"Ошибка: {status_response.description}")