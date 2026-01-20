import re
import os
from typing import List, Optional
from telegram import User, Chat
from .config import Config


def validate_card_number(input_str: str) -> Optional[str]:
    """Валидация номера карточки"""
    if not input_str:
        return None

    # Извлекаем цифры
    digits = re.sub(r'\D', '', input_str)
    if not digits:
        return None

    # Ограничиваем 4 цифрами
    if len(digits) > 4:
        digits = digits[:4]

    return digits.zfill(4)


def split_long_message(text: str, max_length: int = None) -> List[str]:
    """Разделение длинного сообщения на части"""
    if max_length is None:
        max_length = Config.MAX_MESSAGE_LENGTH

    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        # Ищем место для разрыва
        split_pos = text.rfind("\n", 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, max_length)
        if split_pos == -1:
            split_pos = max_length

        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()

    return parts


# Найдите функцию get_user_metadata и исправьте её:

def get_user_metadata(user) -> dict:
    """Получение метаданных пользователя (синхронная версия)"""
    return {
        "username": user.username or "",
        "user_id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "language_code": user.language_code or "",
        "is_premium": bool(getattr(user, 'is_premium', False)),  # Преобразуем в boolean
        "is_bot": bool(user.is_bot),  # Преобразуем в boolean
        "link": f"tg://user?id={user.id}",
        "bio": "",
        "additional_profile_info": "",
        "profile_photo_file_id": ""  # Добавляем поле по ТЗ
    }


async def get_user_metadata_async(user: User, bot) -> dict:
    """Получение метаданных пользователя с bio (асинхронная версия)"""
    metadata = get_user_metadata(user)

    # Пытаемся получить bio через getChat (асинхронно)
    try:
        chat = await bot.get_chat(user.id)
        if chat.bio:
            metadata["bio"] = chat.bio
            metadata["additional_profile_info"] = chat.bio
    except Exception as e:
        # Если не удалось получить bio, оставляем пустым
        pass

    return metadata


def format_card_for_moderation(card: dict) -> str:
    """Форматирование карточки для отправки в группу модерации (по ТЗ)"""
    lines = [
        f"[{card['number']}] {card.get('fio', '')}",
        f"город: {card['city']}",
        f"статус: {card['status']}",
        f"username: @{card['account_meta'].get('username', 'нет')}",
        f"user_id: {card['account_meta'].get('user_id', 'нет')}",
        f"bio: {card['account_meta'].get('bio', 'нет')}",
        f"extra: {card.get('extra', 'нет')}"
    ]

    return "\n".join(lines)