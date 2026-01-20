#!/bin/bash
# Скрипт резервного копирования данных бота
# Добавить в crontab: 0 2 * * * /opt/mybot/scripts/backup.sh

BACKUP_DIR="/var/backups/mybot"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Создаем директорию для бэкапов
mkdir -p "$BACKUP_DIR"

# Создаем бэкап данных
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" -C /var/lib/mybot/data .

# Создаем бэкап кода (без виртуального окружения)
tar -czf "$BACKUP_DIR/code_$DATE.tar.gz" \
    --exclude=".venv" \
    --exclude="data" \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    -C /opt/mybot .

# Создаем бэкап конфигурации
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    /etc/systemd/system/mybot.service \
    /opt/mybot/.env \
    /opt/mybot/requirements.txt

# Удаляем старые бэкапы
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Записываем лог
echo "[$(date)] Создан бэкап: data_$DATE.tar.gz, code_$DATE.tar.gz, config_$DATE.tar.gz" >> "$BACKUP_DIR/backup.log"