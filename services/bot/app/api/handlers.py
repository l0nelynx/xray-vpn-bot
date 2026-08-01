import asyncio
import logging
import time

import app.database.requests as rq
import app.locale.lang_ru as ru
from app.handlers.subscription_service import deliver_subscription, SubscriptionType
from app.settings import bot, admin_bot, secrets

_notify = admin_bot or bot


async def send_alert(order_id: str, usrname: str, usrid: int, tariff_days: int,
                     disable_notification: bool = False, payment_method: str = None,
                     amount: float = None, transaction_id: str = None):
    """
    Отправляет уведомление администратору о транзакции.

    Args:
        order_id: ID заказа
        usrname: Имя пользователя
        usrid: ID пользователя в Telegram
        tariff_days: Количество дней тарифа
        disable_notification: Отключить звук уведомления (для FREE транзакций)
        payment_method: Способ оплаты
        amount: Сумма платежа
        transaction_id: ID транзакции
    """
    await _notify.send_message(
        chat_id=secrets.get('admin_id'),
        text=ru.admin_transaction_message.format(
            transaction_id=transaction_id or order_id,
            payment_method=payment_method or order_id,
            amount=amount if amount is not None else "—",
            username=usrname,
            user_id=usrid,
            days=tariff_days
        ),
        disable_notification=disable_notification
    )


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
        local_transaction_id = userdata.get("transaction_id") or order_id
        db_user_id = userdata.get("user_db_id")
        # Пытаемся получить username из разных возможных полей
        usrname = userdata.get("username") or userdata.get("user_username") or f"user_{usrid}"
        tariff_days = userdata.get("days_ordered")

        # Определяем тип транзакции (FREE или PAID)
        is_free_transaction = userdata.get("is_free") or userdata.get("type") == "free" or userdata.get("payment_type") == "free"

        # Every persisted purchase has a local owner. Route by users.id and
        # purchase_source; android_user_id is only an Android-origin marker.
        if db_user_id:
            await _process_account_payment(order_id, userdata, db_user_id, tariff_days)
            return

        if not usrid or not tariff_days:
            logging.error(f"Missing required data in transaction: user_id={usrid}, days={tariff_days}")
            return

        if userdata.get('status') == 'created':
            # Атомарно захватываем заказ: только один обработчик пройдёт дальше
            claimed = await rq.claim_order_for_processing(local_transaction_id)
            if not claimed:
                logging.warning(f'Order {order_id} already claimed by another handler, skipping')
                return

            payment_method_name = userdata.get("payment_method") or order_id
            tx_amount = userdata.get("amount")

            # Отправляем уведомление с disable_notification=True для FREE транзакций
            await send_alert(
                local_transaction_id, usrname, usrid, tariff_days,
                disable_notification=is_free_transaction,
                payment_method=payment_method_name,
                amount=tx_amount,
                transaction_id=local_transaction_id,
            )

            # Prefer tariff_slug stored on the transaction (set by miniapp /
            # tariff constructor); fall back to bot-side resolution by days.
            tariff_slug = userdata.get("tariff_slug")
            if not tariff_slug:
                logging.error("Transaction %s has no delivery squad snapshot", local_transaction_id)
                await rq.update_order_status(local_transaction_id, "pending")
                return
            delivery_target = {
                "internal_squad_ids": userdata.get("internal_squad_ids") or [],
                "external_squad_id": userdata.get("external_squad_id"),
                "traffic_limit_bytes": userdata.get("traffic_limit_bytes") or 0,
                "traffic_limit_strategy": userdata.get("traffic_limit_strategy") or "NO_RESET",
                "remnawave_description": userdata.get("remnawave_description"),
                "remnawave_tag": userdata.get("remnawave_tag"),
            }

            # Используем новую унифицированную систему доставки подписок
            # message=None для фоновых задач, пользователь получит сообщение напрямую
            delivery_result = await deliver_subscription(
                message=None,
                username=usrname,
                user_id=usrid,
                days=tariff_days,
                subscription_type=SubscriptionType.PAID,
                payment_method=payment_method_name,
                data_limit_gb=None,
                reset_strategy="no_reset",
                transaction_id=local_transaction_id,
                amount=tx_amount,
                tariff_slug=tariff_slug,
                delivery_target=delivery_target,
            )

            # Проверяем результат доставки
            if delivery_result["status"] != "success":
                unsuccess_counter = 0
                retry_start = time.monotonic()
                while unsuccess_counter < 3:
                    logging.warning(f'Ошибка доставки для заказа {order_id}: {delivery_result["message"]}. Повторная попытка...')
                    delay = 2 ** (unsuccess_counter + 1)  # 2s, 4s, 8s
                    if time.monotonic() - retry_start + delay > 30:
                        logging.error(f'Retry timeout exceeded for order {order_id}')
                        break
                    await asyncio.sleep(delay)

                    # Повторная попытка доставки
                    delivery_result = await deliver_subscription(
                        message=None,
                        username=usrname,
                        user_id=usrid,
                        days=tariff_days,
                        subscription_type=SubscriptionType.PAID,
                        payment_method=payment_method_name,
                        data_limit_gb=None,
                        reset_strategy="no_reset",
                        transaction_id=local_transaction_id,
                        amount=tx_amount,
                        tariff_slug=tariff_slug,
                        delivery_target=delivery_target,
                    )

                    if delivery_result["status"] == "success":
                        logging.info(f'✓ Доставка прошла успешно. Заказ: {order_id}, Сценарий: {delivery_result["scenario"]}')
                        break
                    else:
                        unsuccess_counter += 1
                        logging.warning(f'Попытка доставки #{unsuccess_counter} не удалась: {delivery_result["message"]}')

                if delivery_result["status"] != "success":
                    # Оплачено, но не доставлено — ставим pending
                    await rq.update_order_status(local_transaction_id, 'pending')
                    # Уведомляем администратора об ошибке
                    error_msg = f"""❌ Ошибка доставки подписки для заказа {order_id}
Пользователь: @{usrname} ({usrid})
Ошибка: {delivery_result['message']}
Попыток: 3 из 3

Требуется ручное вмешательство администратора!"""

                    await _notify.send_message(
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
        await _notify.send_message(
            chat_id=secrets.get('admin_id'),
            text=f"❌ Критическая ошибка при обработке платежа {order_id}:\n{str(e)}"
        )


async def _process_account_payment(order_id: str, userdata: dict, db_user_id: int, tariff_days: int) -> None:
    """Deliver a paid transaction using local ownership, independent of UI."""
    from app.handlers.android_delivery import deliver_android_paid

    if userdata.get('status') not in {'created', 'pending'}:
        logging.warning(
            f"Account payment {order_id} ignored — status={userdata.get('status')}"
        )
        return
    local_transaction_id = userdata.get("transaction_id") or order_id
    claimed = await rq.claim_order_for_processing(local_transaction_id)
    if not claimed:
        logging.warning(f"Account payment {order_id} already claimed; skipping")
        return

    payment_method_name = userdata.get("payment_method") or order_id
    tx_amount = userdata.get("amount")
    email = userdata.get("user_email")
    tg_id = userdata.get("user_tg_id")
    username = userdata.get("user_username") or userdata.get("username")
    purchase_source = userdata.get("purchase_source") or "legacy_unknown"

    await send_alert(
        local_transaction_id,
        usrname=username or email or f"user_{db_user_id}",
        usrid=int(tg_id) if tg_id is not None else -int(db_user_id),
        tariff_days=tariff_days,
        payment_method=payment_method_name,
        amount=tx_amount,
        transaction_id=local_transaction_id,
    )

    attempts = 0
    while True:
        attempts += 1
        result = await deliver_android_paid(
            transaction_id=local_transaction_id,
            android_user_id=db_user_id,
            email=email,
            days=tariff_days,
            tariff_slug=userdata.get("tariff_slug"),
            delivery_target={
                "internal_squad_ids": userdata.get("internal_squad_ids") or [],
                "external_squad_id": userdata.get("external_squad_id"),
                "traffic_limit_bytes": userdata.get("traffic_limit_bytes") or 0,
                "traffic_limit_strategy": userdata.get("traffic_limit_strategy") or "NO_RESET",
                "remnawave_description": userdata.get("remnawave_description"),
                "remnawave_tag": userdata.get("remnawave_tag"),
            },
            target_rw_id=userdata.get("target_rw_id"),
            tg_id=tg_id,
            tg_username=username if tg_id is not None else None,
            purchase_source=purchase_source,
        )
        if result["status"] == "success":
            break
        if not result.get("retryable") or attempts >= 3:
            break
        delay = 2 ** attempts  # 2s, then 4s
        logging.warning(
            "Transient account delivery failure order=%s attempt=%s/3: %s; "
            "retrying in %ss",
            order_id, attempts, result.get("message"), delay,
        )
        await asyncio.sleep(delay)

    if result["status"] != "success":
        await rq.update_order_status(local_transaction_id, 'pending')
        logging.error(
            f"Account delivery failed for {order_id}: {result.get('message')}"
        )
        await _notify.send_message(
            chat_id=secrets.get('admin_id'),
            text=(
                f"❌ Subscription delivery failed ({purchase_source}): {order_id}\n"
                f"User: {username or email} (db_id={db_user_id})\n"
                f"Error: {result.get('message')}\n"
                f"Attempts: {attempts}/3"
            ),
        )
        return

    logging.info(
        f"✓ Account delivery success: order={order_id}, scenario={result.get('scenario')}"
    )
