import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class Config:
    # Базовые пути
    BASE_DIR = Path(__file__).parent.parent

    # ПАПКИ ПО ТЗ - для разработки на Windows
    DATA_DIR = BASE_DIR / "data"
    CARDS_DIR = DATA_DIR / "cards"
    LOGS_DIR = DATA_DIR / "logs"
    TMP_DIR = DATA_DIR / "tmp"
    COUNTER_FILE = DATA_DIR / "counter.txt"

    # Токен бота (ОБЯЗАТЕЛЬНО заполнить в .env)
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

    # ID группы модерации
    MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID", "-1000000000000"))

    # URL для оплаты
    PAYMENT_URL = os.getenv("PAYMENT_URL", "https://payment.example.com/standard")

    # Тексты сообщений ТОЧНО ПО ТЗ
    START_MESSAGE = "Привет! Для регистрации выбери город:\n[Москва] [Не Москва]"
    FIO_REQUEST = "Спасибо, теперь назови своё ФИО."
    EXTRA_REQUEST = "Спасибо. Укажи, пожалуйста, дополнительную информацию для ускорения процесса или расскажи анекдот."
    APPROVE_MESSAGE = "Ваша заявка [{number}] одобрена. Ссылка для оплаты: {url}"
    REJECT_MESSAGE = "К сожалению, заявка [{number}] отклонена. Для вопросов ответьте в этом чате."

    # Регулярные выражения ТОЧНО ПО ТЗ
    INFO_PATTERN = r"^/info\s+(\d{1,4})$"
    MSG_PATTERN = r"^/msg\s+(\d{1,4})\s+(.+)$"
    APPROVE_PATTERN = r"^/approve\s+(\d{1,4})$"
    REJECT_PATTERN = r"^/reject\s+(\d{1,4})$"

    # Настройки
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_HISTORY_SIZE = 1000
    MAX_MESSAGE_LENGTH = 4096

    # Режим разработки
    DEBUG = os.getenv("ENVIRONMENT", "development") == "development"


def init_directories():
    """Инициализация всех директорий по ТЗ"""
    directories = [
        Config.DATA_DIR,
        Config.CARDS_DIR,
        Config.LOGS_DIR,
        Config.TMP_DIR
    ]

    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if Config.DEBUG:
                print(f"[CONFIG] Создана директория: {directory}")
        except Exception as e:
            print(f"[CONFIG] Ошибка создания директории {directory}: {e}")

    # Создаем counter.txt если нет (по ТЗ)
    if not Config.COUNTER_FILE.exists():
        try:
            Config.COUNTER_FILE.write_text("0\n")
            if Config.DEBUG:
                print(f"[CONFIG] Создан {Config.COUNTER_FILE}")
        except Exception as e:
            print(f"[CONFIG] Ошибка создания counter.txt: {e}")


def check_config():
    """Проверка конфигурации"""
    errors = []
    warnings = []

    # Критические ошибки
    if not Config.BOT_TOKEN:
        errors.append("❌ BOT_TOKEN не установлен в .env файле!")

    if Config.MODERATION_CHAT_ID == -1000000000000:
        warnings.append("⚠️ MODERATION_CHAT_ID не установлен в .env файле (бот не сможет отправлять в группу)")

    if Config.PAYMENT_URL == "https://payment.example.com/standard":
        warnings.append("⚠️ PAYMENT_URL не изменен в .env файле (используется тестовый URL)")

    # Вывод ошибок
    if errors:
        print("\n" + "=" * 60)
        print("ОШИБКИ КОНФИГУРАЦИИ:")
        for error in errors:
            print(f"  {error}")
        print("=" * 60)

    # Вывод предупреждений
    if warnings and Config.DEBUG:
        print("\n" + "=" * 60)
        print("ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"  {warning}")
        print("=" * 60)

    return len(errors) == 0


# Инициализируем директории при импорте
init_directories()