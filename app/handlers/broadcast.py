import asyncio
from aiogram import Bot
from aiogram.types import Message

# Ваша модель пользователя
from app.database.requests import get_users
from app.settings import secrets

ADMIN_IDS = [secrets.get('admin_id')]


async def broadcast_message(bot: Bot, message_text: str, parse_mode: str = 'HTML', test_flag: int):
    """
    Функция рассылки сообщения всем пользователям
    """
    try:
        # Получаем всех пользователей из базы данных
        # result = await session.execute(select(User))
        result = await get_users()
        print(result)
        users = result.all()

        success_count = 0
        fail_count = 0
        failed_users = []
        if test_flag == 0:
            # Отправляем сообщение каждому пользователю
            for user in users:
                try:
                    await bot.send_message(
                        chat_id=user.tg_id,
                        text=message_text,
                        parse_mode=parse_mode
                    )
                    success_count += 1

                    # Небольшая задержка, чтобы не превысить лимиты Telegram
                    await asyncio.sleep(0.1)

                except Exception as e:
                    fail_count += 1
                    failed_users.append((user.tg_id, str(e)))
                    print(f"Не удалось отправить сообщение пользователю {user.tg_id}: {e}")
        else:
            await bot.send_message(
                        chat_id=secrets.get('admin_id'),
                        text=message_text,
                        parse_mode=parse_mode
            )

        # Формируем отчет о рассылке
        report = (
            f"📊 <b>Отчет о рассылке</b>\n\n"
            f"✅ Успешно отправлено: {success_count}\n"
            f"❌ Не удалось отправить: {fail_count}"
        )

        return report, failed_users

    except Exception as e:
        print(f"Ошибка при рассылке: {e}")
        return f"Ошибка при рассылке: {e}", []


# Обработчик команды для администратора
async def admin_broadcast(message: Message, test_flag: int):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in ADMIN_IDS:  # ADMIN_IDS - список ID администраторов
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Получаем текст для рассылки (всё после команды /broadcast)
    broadcast_text = message.text.replace('/broadcast', '').strip()

    if not broadcast_text:
        await message.answer("Укажите текст для рассылки после команды /broadcast")
        return

    # Создаем сессию для работы с БД
        # Отправляем сообщение о начале рассылки
    await message.answer("📨 Рассылка начата...")

    # Выполняем рассылку
    report, failed_users = await broadcast_message(message.bot, broadcast_text, test_flag)

    # Отправляем отчет администратору
    await message.answer(report, parse_mode='HTML')

    # Если есть ошибки, можно отправить подробности
    if failed_users:
        error_details = "\n".join(
            [f"ID: {uid}, Ошибка: {error}" for uid, error in failed_users[:10]])  # Первые 10 ошибок
        if len(failed_users) > 10:
            error_details += f"\n... и еще {len(failed_users) - 10} ошибок"

        await message.answer(f"<b>Ошибки при отправке:</b>\n{error_details}", parse_mode='HTML')




