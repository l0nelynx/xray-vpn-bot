import app.database.requests as rq
import app.handlers.tools as tools
import app.keyboards as kb
import app.marzban.templates as templates
import app.locale.lang_ru as ru
from app.handlers.subscription_service import deliver_subscription, SubscriptionType
from app.settings import bot, secrets
import asyncio
import logging


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
    try:
        userdata = await rq.get_full_transaction_info(order_id)

        if not userdata:
            logging.error(f"Transaction data not found for order_id: {order_id}")
            return

        usrid = userdata.get("user_tg_id")
        # Пытаемся получить username из разных возможных полей
        usrname = userdata.get("username") or userdata.get("user_username") or f"user_{usrid}"
        tariff_days = userdata.get("days_ordered")

        if not usrid or not tariff_days:
            logging.error(f"Missing required data in transaction: user_id={usrid}, days={tariff_days}")
            return

        if userdata.get('status') == 'created':
            await send_alert(order_id, usrname, usrid, tariff_days)
            await rq.update_order_status(order_id, 'confirmed')

            # Используем новую унифицированную систему доставки подписок
            # message=None для фоновых задач, пользователь получит сообщение напрямую
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

            # Проверяем результат доставки
            if delivery_result["status"] != "success":
                unsuccess_counter = 0
                while unsuccess_counter < 3:
                    logging.warning(f'Ошибка доставки для заказа {order_id}: {delivery_result["message"]}. Повторная попытка...')
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
                        logging.info(f'✓ Доставка прошла успешно. Заказ: {order_id}, Сценарий: {delivery_result["scenario"]}')
                        break
                    else:
                        unsuccess_counter += 1
                        logging.warning(f'Попытка доставки #{unsuccess_counter} не удалась: {delivery_result["message"]}')

                if delivery_result["status"] != "success":
                    # Уведомляем администратора об ошибке
                    error_msg = f"""❌ Ошибка доставки подписки для заказа {order_id}
Пользователь: @{usrname} ({usrid})
Ошибка: {delivery_result['message']}
Попыток: 3 из 3

Требуется ручное вмешательство администратора!"""

                    await bot.send_message(
                        chat_id=secrets.get('admin_id'),
                        text=error_msg
                    )
                    logging.error(f"Failed to deliver subscription after 3 attempts for order {order_id}")
            else:
                logging.info(f'✓ Доставка успешна. Заказ: {order_id}, Сценарий: {delivery_result["scenario"]}')
        else:
            logging.warning(f'Double webhook detected or wrong status for order {order_id}. Status: {userdata.get("status")}')

    except Exception as e:
        logging.error(f"Error in payment_process_background for order {order_id}: {e}", exc_info=True)
        # Уведомляем администратора об исключении
        await bot.send_message(
            chat_id=secrets.get('admin_id'),
            text=f"❌ Критическая ошибка при обработке платежа {order_id}:\n{str(e)}"
        )
