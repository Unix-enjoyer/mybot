#!/bin/bash
# Скрипт мониторинга состояния бота
# Можно добавить в crontab: */5 * * * * /opt/mybot/scripts/monitor_bot.sh

BOT_NAME="mybot"
LOG_FILE="/opt/mybot/data/logs/health.log"
STATUS_FILE="/var/www/html/status/health.json"

# Проверяем статус бота
check_bot_status() {
    if systemctl is-active --quiet $BOT_NAME; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Проверяем использование памяти
check_memory() {
    ps aux | grep "python.*bot.main" | grep -v grep | awk '{print $4}' || echo "0"
}

# Проверяем количество карточек
check_cards_count() {
    ls -1 /var/lib/mybot/data/cards/*.json 2>/dev/null | wc -l
}

# Проверяем размер логов
check_logs_size() {
    du -sh /var/lib/mybot/data/logs/ | awk '{print $1}'
}

# Основная функция
main() {
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    STATUS=$(check_bot_status)
    MEMORY=$(check_memory)
    CARDS=$(check_cards_count)
    LOGS_SIZE=$(check_logs_size)

    # Записываем в лог
    echo "[$TIMESTAMP] status=$STATUS, memory=${MEMORY}%, cards=$CARDS, logs=$LOGS_SIZE" >> $LOG_FILE

    # Создаем JSON для веб-интерфейса
    cat > $STATUS_FILE << EOF
{
    "timestamp": "$TIMESTAMP",
    "status": "$STATUS",
    "memory_usage_percent": "$MEMORY",
    "cards_count": "$CARDS",
    "logs_size": "$LOGS_SIZE",
    "python_version": "$(python3.13 --version 2>/dev/null | cut -d' ' -f2)",
    "uptime": "$(uptime -p)"
}
EOF

    # Если бот остановлен, пытаемся перезапустить
    if [ "$STATUS" = "stopped" ]; then
        echo "[$TIMESTAMP] Бот остановлен, пытаюсь перезапустить..." >> $LOG_FILE
        systemctl restart $BOT_NAME
        sleep 5

        if systemctl is-active --quiet $BOT_NAME; then
            echo "[$TIMESTAMP] Бот успешно перезапущен" >> $LOG_FILE
        else
            echo "[$TIMESTAMP] Не удалось перезапустить бота" >> $LOG_FILE
        fi
    fi
}

# Ограничиваем размер лога
trim_log() {
    if [ -f "$LOG_FILE" ] && [ $(wc -l < "$LOG_FILE") -gt 1000 ]; then
        tail -500 "$LOG_FILE" > "${LOG_FILE}.tmp"
        mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
}

# Запускаем
main
trim_log