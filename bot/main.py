import asyncio
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes
)

from .config import Config, check_config
from .handlers import (
    start_command, city_callback, handle_fio, handle_extra,
    handle_user_message, admin_info, admin_msg, admin_approve,
    admin_reject, admin_list_moscow, admin_list_nomoscow,
    error_handler, SELECTING_CITY, ENTERING_FIO, ENTERING_EXTRA
)


def setup_logging():
    """Настройка логирования с RotatingFileHandler"""
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Создаем логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))

    # 1. info.log - основной лог
    info_handler = RotatingFileHandler(
        Config.LOGS_DIR / "info.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    logger.addHandler(info_handler)

    # 2. errors.log - ошибки
    error_handler_file = RotatingFileHandler(
        Config.LOGS_DIR / "errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler_file.setLevel(logging.ERROR)
    error_handler_file.setFormatter(formatter)
    logger.addHandler(error_handler_file)

    # 3. Консольный вывод для разработки
    if Config.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота (асинхронная)"""
    print(f"\n{'=' * 60}")
    print(f"ЗАПУСК БОТА С python-telegram-bot 20.7")
    print(f"Python: {Config.PYTHON_VERSION if hasattr(Config, 'PYTHON_VERSION') else 'Unknown'}")
    print(f"Режим: {'РАЗРАБОТКИ' if Config.DEBUG else 'ПРОДАКШЕНА'}")
    print(f"Директория данных: {Config.DATA_DIR}")
    print(f"{'=' * 60}\n")

    # Проверка конфигурации
    if not check_config():
        print("\n❌ Пожалуйста, исправьте ошибки в конфигурации и перезапустите бота")
        print("   Проверьте файл .env и наличие BOT_TOKEN")
        return

    # Настройка логирования
    logger = setup_logging()
    logger.info("Бот запускается...")

    try:
        # Создаем Application (асинхронная версия)
        application = Application.builder().token(Config.BOT_TOKEN).build()
        logger.info("Application создан успешно")
    except Exception as e:
        logger.error(f"Ошибка создания Application: {e}", exc_info=True)
        print(f"\n❌ Ошибка создания бота: {e}")
        print("   Проверьте BOT_TOKEN в файле .env")
        return

    # ConversationHandler для регистрации
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            SELECTING_CITY: [CallbackQueryHandler(city_callback, pattern='^city_')],
            ENTERING_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fio)],
            ENTERING_EXTRA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_extra)]
        },
        fallbacks=[CommandHandler('start', start_command)],
    )

    # Регистрируем все обработчики
    try:
        # Обработчик регистрации
        application.add_handler(conv_handler)

        # Обработчики сообщений после регистрации
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                handle_user_message
            )
        )

        # Обработчики медиа после регистрации
        application.add_handler(
            MessageHandler(
                filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.VIDEO | filters.AUDIO,
                handle_user_message
            )
        )

        # Админ команды (ТОЛЬКО в группе модерации)
        application.add_handler(CommandHandler('info', admin_info))
        application.add_handler(CommandHandler('msg', admin_msg))
        application.add_handler(CommandHandler('approve', admin_approve))
        application.add_handler(CommandHandler('reject', admin_reject))
        application.add_handler(CommandHandler('list_moscow', admin_list_moscow))
        application.add_handler(CommandHandler('list_nomoscow', admin_list_nomoscow))

        # Обработчик ошибок
        application.add_error_handler(error_handler)

        logger.info("Все обработчики зарегистрированы")

    except Exception as e:
        logger.error(f"Ошибка регистрации обработчиков: {e}", exc_info=True)
        print(f"\n❌ Ошибка настройки обработчиков: {e}")
        return

    # Запуск бота
    try:
        logger.info("Бот запущен и готов к работе!")

        if Config.DEBUG:
            print("\n" + "=" * 60)
            print("✅ БОТ УСПЕШНО ЗАПУЩЕН")
            print(f"   Python-telegram-bot: 20.7")
            print(f"   Токен: {Config.BOT_TOKEN[:10]}...")
            print(f"   Группа модерации: {Config.MODERATION_CHAT_ID}")
            print(f"   Директория данных: {Config.DATA_DIR}")
            print(f"\n   Папки проверены:")
            print(f"     ✓ data/ существует: {(Config.BASE_DIR / 'data').exists()}")
            print(f"     ✓ cards/ существует: {Config.CARDS_DIR.exists()}")
            print(f"     ✓ logs/ существует: {Config.LOGS_DIR.exists()}")
            print(f"     ✓ tmp/ существует: {Config.TMP_DIR.exists()}")
            print("=" * 60)
            print("\n📱 Теперь вы можете:")
            print("   1. Написать боту в Telegram команду /start")
            print("   2. Проверить логи в папке data/logs/")
            print("   3. Для остановки нажмите Ctrl+C\n")

        # Запускаем бота в режиме polling
        await application.run_polling()

    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        print("\n\n🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ Критическая ошибка: {e}")


if __name__ == '__main__':
    # Запускаем асинхронную функцию
    asyncio.run(main())