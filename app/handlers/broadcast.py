import asyncio
from aiogram import Bot
from aiogram.types import Message

from app.database.requests import get_users
from app.settings import secrets

ADMIN_IDS = [secrets.get('admin_id')]


# Broadcast making function
async def broadcast_message(bot: Bot, message_text: str,
                            parse_mode: str = 'HTML', test_flag: str = '',
                            post_id=secrets.get('admin_id')):
    try:
        result = await get_users()
        print(result)
        users = result.all()
        success_count = 0
        fail_count = 0
        failed_users = []
        if test_flag == '':
            for user in users:
                try:
                    await bot.send_message(
                        chat_id=user.tg_id,
                        text=message_text,
                        parse_mode=parse_mode,
                        disable_web_page_preview=True
                    )
                    success_count += 1
                    await asyncio.sleep(0.1)  # latency to avoid Telegram limitations

                except Exception as e:
                    fail_count += 1
                    failed_users.append((user.tg_id, str(e)))
                    print(f"Не удалось отправить сообщение пользователю {user.tg_id}: {e}")
        else:
            success_count += 1
            await bot.send_message(
                chat_id=post_id,
                text=message_text,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
        report = (
            f"📊 <b>Отчет о рассылке</b>\n\n"
            f"✅ Успешно отправлено: {success_count}\n"
            f"❌ Не удалось отправить: {fail_count}"
        )
        return report, failed_users

    except Exception as e:
        print(f"Ошибка при рассылке: {e}")
        return f"Ошибка при рассылке: {e}", []


# Broadcast command handler
async def admin_broadcast(message: Message, test_flag: str = '', post_id=secrets.get('admin_id')):
    if message.from_user.id not in ADMIN_IDS:  # Admin rights check
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    broadcast_text = message.text.replace('/broadcast' + test_flag, '').strip()

    if not broadcast_text:
        await message.answer("Укажите текст для рассылки после команды /broadcast")
        return

    await message.answer("📨 Рассылка начата...")

    # post_id is single message target id
    if post_id:
        report, failed_users = await broadcast_message(message.bot, broadcast_text, 'HTML', test_flag, post_id)
    else:
        report, failed_users = await broadcast_message(message.bot, broadcast_text, 'HTML', test_flag)
    # success report to admin
    await message.answer(report, parse_mode='HTML')
    # errors report to admin
    if failed_users:
        error_details = "\n".join(
            [f"ID: {uid}, Ошибка: {error}" for uid, error in failed_users[:10]])  # Первые 10 ошибок
        if len(failed_users) > 10:
            error_details += f"\n... и еще {len(failed_users) - 10} ошибок"
        await message.answer(f"<b>Ошибки при отправке:</b>\n{error_details}", parse_mode='HTML')
