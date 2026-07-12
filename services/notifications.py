import logging

from aiogram import Bot

from config import settings

logger = logging.getLogger(__name__)


async def send_admin_message(bot: Bot, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(settings.admin_chat_id, text, **kwargs)
        return True
    except Exception:
        logger.exception("Не удалось отправить сообщение в административный чат")
        return False


async def send_admin_photo(bot: Bot, photo: str, caption: str, **kwargs) -> bool:
    try:
        await bot.send_photo(settings.admin_chat_id, photo=photo, caption=caption, **kwargs)
        return True
    except Exception:
        logger.exception("Не удалось отправить фото в административный чат")
        return False
