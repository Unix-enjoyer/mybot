import re
import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from .config import Config
from .database import CardManager
from .schemas import create_history_entry
from .utils import get_user_metadata, split_long_message, format_card_for_moderation

logger = logging.getLogger(__name__)

# Состояния диалога
SELECTING_CITY, ENTERING_FIO, ENTERING_EXTRA = range(3)

# Временное хранилище данных пользователей
user_sessions: Dict[int, Dict[str, Any]] = {}


# ============================= ОБРАБОТЧИКИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =============================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /start (асинхронная версия)"""
    user = update.effective_user

    # Создаем клавиатуру выбора города
    keyboard = [
        [
            InlineKeyboardButton("Москва", callback_data="city_Москва"),
            InlineKeyboardButton("Не Москва", callback_data="city_Не Москва")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        Config.START_MESSAGE,
        reply_markup=reply_markup
    )

    return SELECTING_CITY


async def city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора города с получением фото профиля"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    city = query.data.replace("city_", "")

    # Получаем метаданные пользователя
    user_meta = get_user_metadata(user)

    # Пробуем получить bio через getChat
    try:
        chat = await context.bot.get_chat(user.id)
        if chat.bio:
            user_meta["bio"] = chat.bio
            user_meta["additional_profile_info"] = chat.bio
    except Exception as e:
        logger.debug(f"Не удалось получить bio для пользователя {user.id}: {e}")

    # ПОЛУЧАЕМ ФОТО ПРОФИЛЯ (по ТЗ)
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            # Берем фото с наивысшим разрешением (последнее в массиве)
            photo = photos.photos[0][-1]
            user_meta["profile_photo_file_id"] = photo.file_id
            logger.debug(f"Получено фото профиля для {user.id}: {photo.file_id[:20]}...")
    except Exception as e:
        logger.debug(f"Не удалось получить фото профиля для {user.id}: {e}")

    # Создаем карточку
    card = CardManager.create_card(user_meta, user.id, city)

    if not card:
        await query.edit_message_text("Ошибка создания заявки. Попробуйте снова /start")
        return ConversationHandler.END

    # Сохраняем сессию
    user_sessions[user.id] = {
        "card_number": card["number"],
        "city": city,
        "step": "fio"
    }

    await query.edit_message_text(
        f"Выбран город: {city}\n\n{Config.FIO_REQUEST}"
    )

    return ENTERING_FIO


async def handle_fio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода ФИО (асинхронная версия)"""
    user = update.effective_user

    if user.id not in user_sessions:
        await update.message.reply_text("Пожалуйста, начните с /start")
        return ConversationHandler.END

    session = user_sessions[user.id]
    card_number = session["card_number"]

    # Сохраняем ФИО
    fio = update.message.text.strip()

    # Создаем запись истории
    history_entry = create_history_entry(
        source="user",
        entry_type="text",
        text=f"Введено ФИО: {fio}",
        meta={"message_id": update.message.message_id}
    )

    # Обновляем карточку
    success = CardManager.update_card(
        card_number,
        {"fio": fio, "status": "fio_added"},
        history_entry
    )

    if not success:
        await update.message.reply_text("Ошибка сохранения. Попробуйте снова /start")
        del user_sessions[user.id]
        return ConversationHandler.END

    # Обновляем сессию
    session["fio"] = fio
    session["step"] = "extra"

    await update.message.reply_text(Config.EXTRA_REQUEST)

    return ENTERING_EXTRA


async def handle_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка дополнительной информации (асинхронная версия)"""
    user = update.effective_user

    if user.id not in user_sessions:
        await update.message.reply_text("Пожалуйста, начните с /start")
        return ConversationHandler.END

    session = user_sessions[user.id]
    card_number = session["card_number"]

    # Сохраняем дополнительную информацию
    extra = update.message.text.strip()

    # Создаем запись истории
    history_entry = create_history_entry(
        source="user",
        entry_type="text",
        text=f"Дополнительная информация: {extra}",
        meta={"message_id": update.message.message_id}
    )

    # Обновляем карточку
    success = CardManager.update_card(
        card_number,
        {"extra": extra, "status": "sent_to_review"},
        history_entry
    )

    if not success:
        await update.message.reply_text("Ошибка сохранения. Попробуйте снова /start")
        del user_sessions[user.id]
        return ConversationHandler.END

    # Отправляем заявку в группу модерации
    card = CardManager.load_card(card_number)
    if card:
        await send_to_moderation_group(card, context)

    await update.message.reply_text(
        "Ваша заявка отправлена на модерацию. "
        "Вы можете отправлять дополнительные материалы в этот чат."
    )

    # Завершаем диалог, оставляем сессию для дальнейших сообщений
    session["step"] = "completed"

    return ConversationHandler.END


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка сообщений пользователя после регистрации (асинхронная версия)"""
    user = update.effective_user

    # Проверяем, есть ли активная сессия
    if user.id not in user_sessions:
        return

    session = user_sessions[user.id]
    if session.get("step") != "completed":
        return

    card_number = session["card_number"]
    message = update.message

    # Определяем тип сообщения
    if message.text:
        # Текстовое сообщение
        await forward_text_to_moderation(message, card_number, context)

        # Записываем в историю
        history_entry = create_history_entry(
            source="user",
            entry_type="text",
            text=message.text,
            meta={"message_id": message.message_id}
        )

        CardManager.update_card(card_number, {}, history_entry)

    elif message.photo or message.document or message.voice or message.video or message.audio:
        # Медиа сообщение
        await handle_user_media(update, context, card_number)


async def handle_user_media(update: Update, context: ContextTypes.DEFAULT_TYPE, card_number: str) -> None:
    """Обработка медиа от пользователя (асинхронная версия)"""
    message = update.message

    # Определяем тип медиа
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
        caption = message.caption or ""
    elif message.document:
        file_id = message.document.file_id
        media_type = "file"
        caption = message.caption or ""
    elif message.voice:
        file_id = message.voice.file_id
        media_type = "voice"
        caption = ""
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
        caption = message.caption or ""
    elif message.audio:
        file_id = message.audio.file_id
        media_type = "audio"
        caption = message.caption or ""
    else:
        return

    # Пересылаем в группу модерации
    try:
        await message.forward(chat_id=Config.MODERATION_CHAT_ID)

        # Отправляем текстовое уведомление
        caption_text = f" ({caption})" if caption else ""
        text = f"[{card_number}] пользователь: {media_type}{caption_text}"

        await context.bot.send_message(
            chat_id=Config.MODERATION_CHAT_ID,
            text=text
        )
    except Exception as e:
        logger.error(f"Ошибка пересылки медиа: {e}")

    # Записываем в историю
    history_entry = create_history_entry(
        source="user",
        entry_type=media_type,
        text=caption,
        meta={
            "message_id": message.message_id,
            "file_id": file_id,
            "has_caption": bool(caption)
        }
    )

    CardManager.update_card(card_number, {}, history_entry)


async def send_to_moderation_group(card: dict, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправка заявки в группу модерации С ФОТО ПРОФИЛЯ по ТЗ"""
    try:
        # 1. ОТПРАВЛЯЕМ ФОТО ПРОФИЛЯ ЕСЛИ ЕСТЬ (по ТЗ)
        photo_file_id = card['account_meta'].get('profile_photo_file_id')
        if photo_file_id:
            try:
                await context.bot.send_photo(
                    chat_id=Config.MODERATION_CHAT_ID,
                    photo=photo_file_id,
                    caption=f"[{card['number']}] Фото профиля"  # Префикс по ТЗ
                )
            except Exception as e:
                logger.error(f"Ошибка отправки фото профиля: {e}")

        # 2. Отправляем текстовое сообщение
        message = format_card_for_moderation(card)

        for part in split_long_message(message):
            await context.bot.send_message(
                chat_id=Config.MODERATION_CHAT_ID,
                text=part
            )

        logger.info(f"Заявка {card['number']} отправлена в группу модерации")

    except Exception as e:
        logger.error(f"Ошибка отправки в группу модерации: {e}")


async def forward_text_to_moderation(message, card_number: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пересылка текста в группу модерации (асинхронная версия)"""
    text = f"[{card_number}] пользователь: {message.text}"

    # Разделяем если длинное
    for part in split_long_message(text):
        await context.bot.send_message(
            chat_id=Config.MODERATION_CHAT_ID,
            text=part
        )


# ============================= АДМИН КОМАНДЫ =============================

async def admin_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /info <NNNN> (асинхронная версия)"""
    # Проверяем, что команда из группы модерации
    if update.effective_chat.id != Config.MODERATION_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("Использование: /info <номер>")
        return

    input_number = context.args[0]

    # Проверяем формат
    match = re.match(Config.INFO_PATTERN, f"/info {input_number}")
    if not match:
        await update.message.reply_text("Неверный формат номера. Используйте: /info 123")
        return

    card_number = match.group(1).zfill(4)
    card = CardManager.load_card(card_number)

    if not card:
        await update.message.reply_text(f"Заявка {card_number} не найдена")
        return

    # Отправляем информацию о карточке
    info_text = CardManager.format_detailed(card)

    for part in split_long_message(info_text):
        await update.message.reply_text(part)

    # Логируем команду
    log_admin_command(update, "info", card_number)


async def admin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /msg <NNNN> <текст> (асинхронная версия)"""
    if update.effective_chat.id != Config.MODERATION_CHAT_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /msg <номер> <текст>")
        return

    input_number = context.args[0]
    text = " ".join(context.args[1:])

    # Проверяем формат
    match = re.match(Config.MSG_PATTERN, f"/msg {input_number} {text}")
    if not match:
        await update.message.reply_text("Неверный формат. Используйте: /msg 123 Текст сообщения")
        return

    card_number = match.group(1).zfill(4)
    card = CardManager.load_card(card_number)

    if not card:
        await update.message.reply_text(f"Заявка {card_number} не найдена")
        return

    user_id = card["account_meta"]["user_id"]

    try:
        # Отправляем сообщение пользователю
        await context.bot.send_message(
            chat_id=user_id,
            text=text
        )

        # Записываем в историю
        history_entry = create_history_entry(
            source="admin",
            entry_type="command",
            text=f"Сообщение от модератора: {text}",
            meta={
                "admin_id": update.effective_user.id,
                "admin_username": update.effective_user.username or "",
                "command": "msg"
            }
        )

        CardManager.update_card(card_number, {}, history_entry)

        await update.message.reply_text(f"Сообщение отправлено пользователю {card_number}")

        # Логируем команду
        log_admin_command(update, "msg", card_number)

    except Exception as e:
        await update.message.reply_text(f"Ошибка отправки: {str(e)}")


async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /approve <NNNN> (асинхронная версия)"""
    if update.effective_chat.id != Config.MODERATION_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("Использование: /approve <номер>")
        return

    input_number = context.args[0]

    # Проверяем формат
    match = re.match(Config.APPROVE_PATTERN, f"/approve {input_number}")
    if not match:
        await update.message.reply_text("Неверный формат. Используйте: /approve 123")
        return

    card_number = match.group(1).zfill(4)
    card = CardManager.load_card(card_number)

    if not card:
        await update.message.reply_text(f"Заявка {card_number} не найдена")
        return

    # Создаем запись истории
    history_entry = create_history_entry(
        source="admin",
        entry_type="command",
        text="Заявка одобрена",
        meta={
            "admin_id": update.effective_user.id,
            "admin_username": update.effective_user.username or "",
            "command": "approve"
        }
    )

    # Обновляем статус
    success = CardManager.update_card(
        card_number,
        {
            "status": "approved",
            "decision": "approved"
        },
        history_entry
    )

    if not success:
        await update.message.reply_text("Ошибка обновления статуса")
        return

    # Отправляем сообщение пользователю
    user_id = card["account_meta"]["user_id"]
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=Config.APPROVE_MESSAGE.format(
                number=card_number,
                url=Config.PAYMENT_URL
            )
        )
    except Exception as e:
        await update.message.reply_text(f"Заявка одобрена, но не удалось уведомить пользователя: {e}")

    await update.message.reply_text(f"Заявка {card_number} одобрена")

    # Логируем команду
    log_admin_command(update, "approve", card_number)


async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /reject <NNNN> (асинхронная версия)"""
    if update.effective_chat.id != Config.MODERATION_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("Использование: /reject <номер>")
        return

    input_number = context.args[0]

    # Проверяем формат
    match = re.match(Config.REJECT_PATTERN, f"/reject {input_number}")
    if not match:
        await update.message.reply_text("Неверный формат. Используйте: /reject 123")
        return

    card_number = match.group(1).zfill(4)
    card = CardManager.load_card(card_number)

    if not card:
        await update.message.reply_text(f"Заявка {card_number} не найдена")
        return

    # Создаем запись истории
    history_entry = create_history_entry(
        source="admin",
        entry_type="command",
        text="Заявка отклонена",
        meta={
            "admin_id": update.effective_user.id,
            "admin_username": update.effective_user.username or "",
            "command": "reject"
        }
    )

    # Обновляем статус
    success = CardManager.update_card(
        card_number,
        {
            "status": "rejected",
            "decision": "rejected"
        },
        history_entry
    )

    if not success:
        await update.message.reply_text("Ошибка обновления статуса")
        return

    # Отправляем сообщение пользователю
    user_id = card["account_meta"]["user_id"]
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=Config.REJECT_MESSAGE.format(number=card_number)
        )
    except Exception as e:
        await update.message.reply_text(f"Заявка отклонена, но не удалось уведомить пользователя: {e}")

    await update.message.reply_text(f"Заявка {card_number} отклонена")

    # Логируем команду
    log_admin_command(update, "reject", card_number)


async def admin_list_moscow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /list_moscow (асинхронная версия)"""
    if update.effective_chat.id != Config.MODERATION_CHAT_ID:
        return

    cards = CardManager.get_cards_by_city("Москва")

    if not cards:
        await update.message.reply_text("Нет заявок из Москвы")
        return

    # Формируем список
    lines = [f"Заявки из Москвы ({len(cards)}):"]
    for card in cards:
        lines.append(CardManager.format_for_list(card))

    result = "\n".join(lines)

    # Разделяем на части если длинно
    for part in split_long_message(result, 3000):
        await update.message.reply_text(part)

    log_admin_command(update, "list_moscow", "")


async def admin_list_nomoscow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /list_nomoscow (асинхронная версия)"""
    if update.effective_chat.id != Config.MODERATION_CHAT_ID:
        return

    cards = CardManager.get_cards_by_city("Не Москва")

    if not cards:
        await update.message.reply_text("Нет заявок не из Москвы")
        return

    # Формируем список
    lines = [f"Заявки не из Москвы ({len(cards)}):"]
    for card in cards:
        lines.append(CardManager.format_for_list(card))

    result = "\n".join(lines)

    # Разделяем на части если длинно
    for part in split_long_message(result, 3000):
        await update.message.reply_text(part)

    log_admin_command(update, "list_nomoscow", "")


def log_admin_command(update: Update, command: str, card_number: str) -> None:
    """Логирование админ-команд"""
    admin = update.effective_user
    timestamp = update.message.date.isoformat()

    log_entry = (
        f"{timestamp} - "
        f"admin_id: {admin.id}, "
        f"username: {admin.username or 'нет'}, "
        f"command: {command}, "
        f"card: {card_number}\n"
    )

    try:
        log_file = Config.LOGS_DIR / "commands.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Ошибка записи в лог команд: {e}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок (асинхронная версия)"""
    try:
        raise context.error
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)

        # Записываем в errors.log
        try:
            error_log = Config.LOGS_DIR / "errors.log"
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"{update.update_id if update else 'N/A'} - {type(e).__name__}: {str(e)}\n")
        except:
            pass