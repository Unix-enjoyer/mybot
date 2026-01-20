import asyncio
import logging
import sys
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
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))

    # info.log
    info_handler = RotatingFileHandler(
        Config.LOGS_DIR / "info.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    logger.addHandler(info_handler)

    # errors.log
    error_handler_file = RotatingFileHandler(
        Config.LOGS_DIR / "errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler_file.setLevel(logging.ERROR)
    error_handler_file.setFormatter(formatter)
    logger.addHandler(error_handler_file)

    # Console
    if Config.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logging.getLogger(__name__)


def main():
    """Основная функция запуска бота (синхронная)"""
    print(f"\n{'=' * 60}")
    print(f"ЗАПУСК БОТА С python-telegram-bot 20.7")
    print(f"Режим: {'РАЗРАБОТКИ' if Config.DEBUG else 'ПРОДАКШЕНА'}")
    print(f"Директория данных: {Config.DATA_DIR}")
    print(f"{'=' * 60}\n")

    # Проверка конфигурации
    if not check_config():
        print("\n❌ Ошибки конфигурации. Проверьте .env файл")
        return 1

    # Настройка логирования
    logger = setup_logging()
    logger.info("Бот запускается...")

    try:
        # Создаем Application
        application = Application.builder().token(Config.BOT_TOKEN).build()
        logger.info("Application создан")
    except Exception as e:
        logger.error(f"Ошибка создания бота: {e}")
        print(f"\n❌ Ошибка создания бота: {e}")
        return 1

    # ConversationHandler для регистрации
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            SELECTING_CITY: [CallbackQueryHandler(city_callback, pattern='^city_')],
            ENTERING_FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fio)],
            ENTERING_EXTRA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_extra)]
        },
        fallbacks=[CommandHandler('start', start_command)],
        per_message=False,  # Явно указываем
    )

    try:
        # Регистрируем все обработчики
        application.add_handler(conv_handler)
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message)
        )
        application.add_handler(
            MessageHandler(
                filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.VIDEO | filters.AUDIO,
                handle_user_message
            )
        )

        # Админ команды
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
        logger.error(f"Ошибка регистрации обработчиков: {e}")
        print(f"\n❌ Ошибка настройки обработчиков: {e}")
        return 1

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
            print(f"     ✓ data/ существует: {Config.DATA_DIR.exists()}")
            print(f"     ✓ cards/ существует: {Config.CARDS_DIR.exists()}")
            print(f"     ✓ logs/ существует: {Config.LOGS_DIR.exists()}")
            print(f"     ✓ tmp/ существует: {Config.TMP_DIR.exists()}")
            print("=" * 60)
            print("\n📱 Теперь вы можете:")
            print("   1. Написать боту в Telegram команду /start")
            print("   2. Проверить логи в папке data/logs/")
            print("   3. Для остановки нажмите Ctrl+C\n")

        # ЗАПУСКАЕМ БОТА - СИНХРОННО
        application.run_polling()

    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        print("\n\n🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ Критическая ошибка: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())