import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings, validate_settings
from database.sqlite import init_database
from handlers import routers
from services.google_sheets import google_sheets_service


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    validate_settings()
    await init_database()
    await google_sheets_service.initialize()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    for router in routers:
        dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=False)

    try:
        await bot.send_message(
            settings.admin_chat_id,
            "🟢 <b>УслугиГосс запущен</b>\nАдминистративная панель: /panel",
        )
    except Exception:
        logging.exception("Не удалось отправить сообщение о запуске")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
