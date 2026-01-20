#!/bin/bash
# Скрипт развертывания бота на продакшен-сервере
# Использовать: sudo -u botuser bash deploy.sh

set -e

echo "=== РАЗВЕРТЫВАНИЕ TELEGRAM БОТА ==="
echo "Дата: $(date)"
echo "Пользователь: $(whoami)"
echo "Директория: $(pwd)"
echo ""

# ============================================================================
# 1. ПРОВЕРКА ПРЕДУСЛОВИЙ
# ============================================================================
echo "1. Проверка предварительных условий..."

# Проверяем, что мы в правильной директории
if [ ! -d "/opt/mybot" ]; then
    echo "❌ Ошибка: Скрипт должен запускаться из /opt/mybot"
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Ошибка: Файл .env не найден!"
    echo "   Создайте его: cp .env.example .env"
    echo "   Заполните BOT_TOKEN, MODERATION_CHAT_ID, PAYMENT_URL"
    exit 1
fi

# Проверяем Python версию
PYTHON_VERSION=$(python3.13 --version 2>/dev/null | cut -d' ' -f2)
if [ -z "$PYTHON_VERSION" ]; then
    echo "❌ Ошибка: Python 3.13 не установлен"
    exit 1
fi
echo "✅ Python версия: $PYTHON_VERSION"

# ============================================================================
# 2. СОЗДАНИЕ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ
# ============================================================================
echo ""
echo "2. Создание виртуального окружения..."

if [ -d ".venv" ]; then
    echo "✅ Виртуальное окружение уже существует"
else
    python3.13 -m venv .venv
    echo "✅ Виртуальное окружение создано"
fi

# Активируем виртуальное окружение
source .venv/bin/activate
echo "✅ Виртуальное окружение активировано"

# ============================================================================
# 3. УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================================
echo ""
echo "3. Установка зависимостей..."

# Обновляем pip
pip install --upgrade pip
echo "✅ pip обновлен"

# Устанавливаем зависимости
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Зависимости установлены"
else
    echo "❌ Файл requirements.txt не найден"
    exit 1
fi

# ============================================================================
# 4. ПРОВЕРКА КОНФИГУРАЦИИ
# ============================================================================
echo ""
echo "4. Проверка конфигурации..."

# Проверяем обязательные переменные
REQUIRED_VARS=("BOT_TOKEN" "MODERATION_CHAT_ID" "PAYMENT_URL")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^$var=" .env; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "❌ Отсутствуют обязательные переменные в .env:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    exit 1
fi

# Устанавливаем режим продакшена
if ! grep -q "^ENVIRONMENT=" .env; then
    echo "ENVIRONMENT=production" >> .env
    echo "✅ Добавлена переменная ENVIRONMENT=production"
fi

echo "✅ Конфигурация проверена"

# ============================================================================
# 5. СОЗДАНИЕ ДИРЕКТОРИЙ ДАННЫХ
# ============================================================================
echo ""
echo "5. Проверка директорий данных..."

# Создаем ссылки на данные, если нужно
if [ ! -d "data" ]; then
    ln -sf /var/lib/mybot/data data
    echo "✅ Создана ссылка на данные"
fi

# Проверяем существование директорий
for dir in data data/cards data/logs data/tmp; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "✅ Создана директория $dir"
    fi
done

# Проверяем counter.txt
if [ ! -f "data/counter.txt" ]; then
    echo "0" > data/counter.txt
    echo "✅ Создан counter.txt"
fi

echo "✅ Директории данных проверены"

# ============================================================================
# 6. ТЕСТИРОВАНИЕ ИМПОРТОВ
# ============================================================================
echo ""
echo "6. Тестирование импортов..."

# Создаем тестовый скрипт
cat > test_imports.py << 'EOF'
import sys
print(f"Python: {sys.version}")

try:
    from telegram import __version__
    print(f"✅ python-telegram-bot: {__version__}")
except Exception as e:
    print(f"❌ Ошибка импорта telegram: {e}")
    sys.exit(1)

try:
    from bot.config import Config
    print(f"✅ Конфигурация: {Config.DATA_DIR}")
except Exception as e:
    print(f"❌ Ошибка импорта конфигурации: {e}")
    sys.exit(1)

print("✅ Все импорты работают")
EOF

# Запускаем тест
if python test_imports.py; then
    echo "✅ Импорты работают корректно"
    rm test_imports.py
else
    echo "❌ Ошибка тестирования импортов"
    exit 1
fi

# ============================================================================
# 7. ПРИМЕНЕНИЕ SYSTEMD КОНФИГУРАЦИИ
# ============================================================================
echo ""
echo "7. Настройка systemd..."

# Перезагружаем systemd
sudo systemctl daemon-reload
echo "✅ Systemd перезагружен"

# ============================================================================
# 8. ЗАПУСК БОТА
# ============================================================================
echo ""
echo "8. Запуск бота..."

# Останавливаем бота если запущен
sudo systemctl stop mybot 2>/dev/null || true

# Запускаем бота
sudo systemctl start mybot
sleep 3

# Проверяем статус
if sudo systemctl is-active --quiet mybot; then
    echo "✅ Бот успешно запущен"
else
    echo "❌ Ошибка запуска бота"
    sudo systemctl status mybot --no-pager
    exit 1
fi

# ============================================================================
# 9. ФИНАЛЬНАЯ ПРОВЕРКА
# ============================================================================
echo ""
echo "9. Финальная проверка..."

# Проверяем логи
if [ -f "data/logs/info.log" ]; then
    echo "✅ Логи созданы"
    echo "Последние строки лога:"
    tail -5 data/logs/info.log || true
else
    echo "⚠️  Файл логов не создан (возможно бот еще не писал логи)"
fi

# Проверяем процессы
if pgrep -f "python.*bot.main" > /dev/null; then
    echo "✅ Процесс бота запущен"
else
    echo "❌ Процесс бота не найден"
fi

# ============================================================================
# 10. ВЫВОД ИНФОРМАЦИИ
# ============================================================================
echo ""
echo "=" * 60
echo "РАЗВЕРТЫВАНИЕ УСПЕШНО ЗАВЕРШЕНО!"
echo "=" * 60
echo ""
echo "Бот запущен и работает."
echo ""
echo "КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ:"
echo "  sudo systemctl status mybot      # Статус бота"
echo "  sudo systemctl stop mybot        # Остановить бота"
echo "  sudo systemctl start mybot       # Запустить бота"
echo "  sudo systemctl restart mybot     # Перезапустить бота"
echo "  sudo journalctl -u mybot -f      # Логи в реальном времени"
echo ""
echo "ЛОГИ ПРИЛОЖЕНИЯ:"
echo "  tail -f /opt/mybot/data/logs/info.log    # Основные логи"
echo "  tail -f /opt/mybot/data/logs/errors.log  # Логи ошибок"
echo ""
echo "МОНИТОРИНГ:"
echo "  htop                                 # Нагрузка системы"
echo "  df -h                                # Дисковое пространство"
echo "  sudo systemctl list-timers           # Таймеры systemd"
echo ""
echo "ДИРЕКТОРИИ:"
echo "  /opt/mybot/                          # Код бота"
echo "  /var/lib/mybot/data/                 # Данные (карточки, логи)"
echo "  /etc/systemd/system/mybot.service    # Конфиг службы"
echo ""
echo "=" * 60
echo "Следующие шаги:"
echo "1. Проверьте бота в Telegram: отправьте /start"
echo "2. Проверьте логи на наличие ошибок"
echo "3. Настройте мониторинг (опционально)"
echo "=" * 60