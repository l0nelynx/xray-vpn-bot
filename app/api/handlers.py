import app.database.requests as rq
import app.handlers.tools as tools
import app.keyboards as kb
import app.marzban.templates as templates
import app.locale.lang_ru as ru
from app.handlers.subscription_service import deliver_subscription, SubscriptionType
from app.settings import bot, secrets
import asyncio


async def send_alert(order_id: str, usrname: str, usrid: int, tariff_days: int):
    await bot.send_message(chat_id=secrets.get('admin_id'),
                           text=f"Транзакция ID - {order_id}\n"
                                f"Пользователь - @{usrname}\n"
                                f"UserId - {usrid}\n"
                                f"Количество дней - {tariff_days}\n")


async def payment_process_background(order_id: str):
    """
    Обработка платежа в фоновом режиме с использованием
    унифицированной системы выдачи подписок.
    """
    userdata = await rq.get_full_transaction_info(order_id)
    usrid = userdata["user_tg_id"]
    usrname = userdata["username"]
    tariff_days = userdata["days_ordered"]

    if userdata['status'] == 'created':
        await send_alert(order_id, usrname, usrid, tariff_days)
        await rq.update_order_status(order_id, 'confirmed')

        # Используем новую унифицированную систему доставки подписок
        delivery_result = await deliver_subscription(
            message=None,  # Нет message/callback, отправляем прямо пользователю
            username=usrname,
            user_id=usrid,
            days=tariff_days,
            subscription_type=SubscriptionType.PAID,
            payment_method=order_id,  # ID заказа как идентификатор платежа
            data_limit_gb=None,  # Неограниченный трафик
            reset_strategy="no_reset"
        )

        # Проверяем результат доставки
        if delivery_result["status"] != "success":
            unsuccess_counter = 0
            while unsuccess_counter < 3:
                print('Ошибка при доставке товара, попытка повторить доставку')
                await asyncio.sleep(2)

                # Повторная попытка доставки
                delivery_result = await deliver_subscription(
                    message=None,
                    username=usrname,
                    user_id=usrid,
                    days=tariff_days,
                    subscription_type=SubscriptionType.PAID,
                    payment_method=order_id,
                    data_limit_gb=None,
                    reset_strategy="no_reset"
                )

                if delivery_result["status"] == "success":
                    print(f'Доставка прошла успешно. Сценарий: {delivery_result["scenario"]}')
                    break
                else:
                    unsuccess_counter += 1
                    print(f'Попытка доставки #{unsuccess_counter} не удалась: {delivery_result["message"]}')

            if delivery_result["status"] != "success":
                # Уведомляем администратора об ошибке
                await bot.send_message(
                    chat_id=secrets.get('admin_id'),
                    text=f"❌ Ошибка доставки подписки для заказа {order_id}\n"
                         f"Пользователь: @{usrname} ({usrid})\n"
                         f"Ошибка: {delivery_result['message']}"
                )
        else:
            print(f'Доставка прошла успешно. Сценарий: {delivery_result["scenario"]}')
    else:
        print('Double webhook detected')
