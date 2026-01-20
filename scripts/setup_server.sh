#!/bin/bash
# Скрипт настройки сервера Ubuntu для Telegram бота с Python 3.13.7
# Использовать: sudo bash setup_server.sh

set -e

echo "=== НАСТРОЙКА СЕРВЕРА ДЛЯ TELEGRAM БОТА ==="
echo "Дата: $(date)"
echo "Система: $(lsb_release -ds)"
echo ""

# ============================================================================
# 1. ОБНОВЛЕНИЕ СИСТЕМЫ
# ============================================================================
echo "1. Обновление системы..."
sudo apt update
sudo apt upgrade -y
echo "✅ Система обновлена"

# ============================================================================
# 2. УСТАНОВКА PYTHON 3.13.7
# ============================================================================
echo ""
echo "2. Установка Python 3.13.7..."

# Проверяем текущую версию Python
if command -v python3.13 &> /dev/null; then
    echo "✅ Python 3.13 уже установлен"
else
    echo "Установка Python 3.13.7..."

    # Устанавливаем зависимости для сборки Python
    sudo apt install -y \
        build-essential \
        zlib1g-dev \
        libncurses5-dev \
        libgdbm-dev \
        libnss3-dev \
        libssl-dev \
        libreadline-dev \
        libffi-dev \
        libsqlite3-dev \
        libbz2-dev \
        wget \
        curl \
        git

    # Скачиваем исходный код Python 3.13.7
    PYTHON_VERSION="3.13.7"
    cd /tmp
    wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz
    tar -xf Python-${PYTHON_VERSION}.tar.xz
    cd Python-${PYTHON_VERSION}

    # Конфигурируем и собираем
    ./configure --enable-optimizations
    make -j $(nproc)
    sudo make altinstall

    # Проверяем установку
    if command -v python3.13 &> /dev/null; then
        echo "✅ Python 3.13.7 успешно установлен"
    else
        echo "❌ Ошибка установки Python 3.13.7"
        exit 1
    fi
fi

# ============================================================================
# 3. УСТАНОВКА ОСНОВНЫХ ПАКЕТОВ
# ============================================================================
echo ""
echo "3. Установка основных пакетов..."
sudo apt install -y \
    python3-pip \
    python3.13-venv \
    nginx \
    supervisor \
    ufw \
    curl \
    git \
    tree \
    htop \
    nano \
    vim
echo "✅ Основные пакеты установлены"

# ============================================================================
# 4. СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ ДЛЯ БОТА
# ============================================================================
echo ""
echo "4. Создание пользователя botuser..."
if id "botuser" &>/dev/null; then
    echo "✅ Пользователь botuser уже существует"
else
    sudo useradd -m -s /bin/bash botuser
    echo "✅ Пользователь botuser создан"
fi

# Добавляем в группу sudo (для удобства администрирования)
sudo usermod -a -G sudo botuser || true
echo "✅ Пользователь добавлен в группу sudo"

# ============================================================================
# 5. СОЗДАНИЕ ДИРЕКТОРИЙ ПО ТЗ (КРИТИЧЕСКИ ВАЖНО!)
# ============================================================================
echo ""
echo "5. Создание директорий по ТЗ..."

# Создаем структуру папок ТОЧНО как в ТЗ
sudo mkdir -p /var/lib/mybot/data
sudo mkdir -p /var/lib/mybot/data/cards
sudo mkdir -p /var/lib/mybot/data/logs
sudo mkdir -p /var/lib/mybot/data/tmp

echo "✅ Директории созданы:"
echo "   /var/lib/mybot/data"
echo "   /var/lib/mybot/data/cards"
echo "   /var/lib/mybot/data/logs"
echo "   /var/lib/mybot/data/tmp"

# ============================================================================
# 6. НАСТРОЙКА ПРАВ ДОСТУПА
# ============================================================================
echo ""
echo "6. Настройка прав доступа..."

# Назначаем владельца botuser для всех папок
sudo chown -R botuser:botuser /var/lib/mybot

# Устанавливаем правильные права
sudo chmod 755 /var/lib/mybot
sudo chmod 755 /var/lib/mybot/data
sudo chmod 755 /var/lib/mybot/data/cards
sudo chmod 755 /var/lib/mybot/data/logs
sudo chmod 755 /var/lib/mybot/data/tmp

# Создаем counter.txt (по ТЗ)
if [ ! -f /var/lib/mybot/data/counter.txt ]; then
    echo "0" | sudo tee /var/lib/mybot/data/counter.txt > /dev/null
    sudo chown botuser:botuser /var/lib/mybot/data/counter.txt
    sudo chmod 644 /var/lib/mybot/data/counter.txt
    echo "✅ counter.txt создан"
else
    echo "✅ counter.txt уже существует"
fi

echo "✅ Права доступа настроены"

# ============================================================================
# 7. СОЗДАНИЕ ДИРЕКТОРИИ ДЛЯ КОДА ПРОЕКТА
# ============================================================================
echo ""
echo "7. Создание директории для кода проекта..."
sudo mkdir -p /opt/mybot
sudo chown botuser:botuser /opt/mybot
sudo chmod 755 /opt/mybot
echo "✅ Директория /opt/mybot создана"

# ============================================================================
# 8. НАСТРОЙКА БРАНДМАУЭРА (UFW)
# ============================================================================
echo ""
echo "8. Настройка брандмауэра..."
sudo ufw --force enable
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp    # HTTP (если будет веб-интерфейс)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force reload
echo "✅ Брандмауэр настроен"

# ============================================================================
# 9. НАСТРОЙКА NGINX (ОПЦИОНАЛЬНО, для мониторинга/статуса)
# ============================================================================
echo ""
echo "9. Настройка Nginx (опционально)..."
if [ -d /etc/nginx ]; then
    # Создаем конфиг для бота
    sudo tee /etc/nginx/sites-available/mybot > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        return 404;
    }

    location /status {
        # Простая страница статуса
        alias /var/www/html/status;
        try_files $uri $uri/ =404;
    }

    location /logs {
        # Защищенный доступ к логам через nginx
        alias /var/lib/mybot/data/logs;
        autoindex off;

        # Базовая аутентификация
        auth_basic "Restricted Access";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
EOF

    # Создаем директорию для статуса
    sudo mkdir -p /var/www/html/status
    echo "Бот работает" | sudo tee /var/www/html/status/index.html > /dev/null

    # Создаем файл с паролем (пароль: admin)
    echo "admin:\$apr1\$rRj7C8fX\$j3jDf7qLq2vYQ8Xq3Z8nZ0" | sudo tee /etc/nginx/.htpasswd > /dev/null

    # Активируем конфиг
    sudo ln -sf /etc/nginx/sites-available/mybot /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    echo "✅ Nginx настроен"
else
    echo "⚠️ Nginx не установлен, пропускаем"
fi

# ============================================================================
# 10. НАСТРОЙКА SYSTEMD ДЛЯ АВТОЗАПУСКА БОТА
# ============================================================================
echo ""
echo "10. Настройка systemd для автозапуска бота..."

# Создаем systemd службу для бота
sudo tee /etc/systemd/system/mybot.service > /dev/null << 'EOF'
[Unit]
Description=Telegram Registration Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/opt/mybot
Environment="PYTHONPATH=/opt/mybot"
Environment="PATH=/opt/mybot/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Команда запуска
ExecStart=/opt/mybot/.venv/bin/python -m bot.main

# Перезапуск при сбоях
Restart=always
RestartSec=10

# Ограничения безопасности
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/mybot/data

# Логирование
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mybot

[Install]
WantedBy=multi-user.target
EOF

# Создаем сервис для мониторинга состояния
sudo tee /etc/systemd/system/mybot-watcher.service > /dev/null << 'EOF'
[Unit]
Description=Bot Status Watcher
After=mybot.service
Requires=mybot.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'echo "Bot is running" > /var/www/html/status/index.html'
ExecStop=/bin/bash -c 'echo "Bot is stopped" > /var/www/html/status/index.html'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/mybot-watcher.path > /dev/null << 'EOF'
[Unit]
Description=Monitor bot service state

[Path]
PathChanged=/etc/systemd/system/mybot.service

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Systemd службы созданы"

# ============================================================================
# 11. НАСТРОЙКА ЛОГИРОВАНИЯ И РОТАЦИИ ЛОГОВ
# ============================================================================
echo ""
echo "11. Настройка логирования..."

# Создаем конфиг logrotate для логов бота
sudo tee /etc/logrotate.d/mybot > /dev/null << 'EOF'
/var/lib/mybot/data/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 640 botuser botuser
    sharedscripts
    postrotate
        systemctl reload mybot > /dev/null 2>&1 || true
    endscript
}
EOF

# Создаем директорию для systemd логов
sudo mkdir -p /var/log/mybot
sudo chown botuser:botuser /var/log/mybot

echo "✅ Логирование настроено"

# ============================================================================
# 12. ФИНАЛЬНЫЕ ШАГИ
# ============================================================================
echo ""
echo "12. Финальные шаги..."

# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозагрузку служб
sudo systemctl enable mybot
sudo systemctl enable mybot-watcher.service
sudo systemctl enable mybot-watcher.path

echo "✅ Все службы добавлены в автозагрузку"

# ============================================================================
# 13. ВЫВОД ИНСТРУКЦИЙ
# ============================================================================
echo ""
echo "=" * 60
echo "НАСТРОЙКА СЕРВЕРА ЗАВЕРШЕНА!"
echo "=" * 60
echo ""
echo "Следующие шаги:"
echo ""
echo "1. КОПИРОВАНИЕ КОДА НА СЕРВЕР:"
echo "   На вашем компьютере (Windows):"
echo "   scp -r D:\\TopProjects\\mybot\\* botuser@ВАШ_СЕРВЕР_IP:/opt/mybot/"
echo ""
echo "2. НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:"
echo "   На сервере:"
echo "   sudo -u botuser bash -c 'cd /opt/mybot && cp .env.example .env'"
echo "   sudo -u botuser bash -c 'cd /opt/mybot && nano .env'"
echo ""
echo "3. ЗАПОЛНИТЕ .env ФАЙЛ:"
echo "   BOT_TOKEN=ваш_токен_бота"
echo "   MODERATION_CHAT_ID=-1001234567890"
echo "   PAYMENT_URL=https://payment.example.com/standard"
echo "   ENVIRONMENT=production"
echo ""
echo "4. ЗАПУСК БОТА:"
echo "   sudo -u botuser bash /opt/mybot/scripts/deploy.sh"
echo ""
echo "5. КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ:"
echo "   • Статус бота:        sudo systemctl status mybot"
echo "   • Запуск бота:        sudo systemctl start mybot"
echo "   • Остановка бота:     sudo systemctl stop mybot"
echo "   • Перезапуск бота:    sudo systemctl restart mybot"
echo "   • Просмотр логов:     sudo journalctl -u mybot -f"
echo "   • Логи приложения:    tail -f /var/lib/mybot/data/logs/info.log"
echo ""
echo "6. ПРОВЕРКА РАБОТОСПОСОБНОСТИ:"
echo "   • Python версия:      python3.13 --version"
echo "   • Структура папок:    tree /var/lib/mybot/"
echo "   • Логи:               ls -la /var/lib/mybot/data/logs/"
echo ""
echo "=" * 60
echo "ВРЕМЯ ВЫПОЛНЕНИЯ СКРИПТА: $(date)"
echo "=" * 60