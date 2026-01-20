#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы бота с python-telegram-bot 20.7
"""

import sys
import os
import asyncio

print("=" * 60)
print(f"ТЕСТ СОВМЕСТИМОСТИ С python-telegram-bot 20.7")
print(f"Python {sys.version.split()[0]}")
print("=" * 60)


async def test_imports():
    """Тест импортов новой версии"""
    try:
        from telegram import __version__, Update
        from telegram.ext import (
            Application,
            CommandHandler,
            MessageHandler,
            filters,
            CallbackQueryHandler,
            ConversationHandler,
            ContextTypes
        )

        print(f"✅ python-telegram-bot версия: {__version__}")
        print("✅ Все импорты работают")

        # Проверяем, что нет ошибки imghdr
        try:
            import imghdr
            print("⚠️  Модуль imghdr найден (в Python 3.13 он должен быть удален)")
        except ModuleNotFoundError:
            print("✅ Модуль imghdr не найден (нормально для Python 3.13)")

        return True
    except Exception as e:
        print(f"❌ Ошибка импортов: {e}")
        return False


async def test_async_functions():
    """Тест асинхронных функций"""
    try:
        # Тестовая асинхронная функция
        async def test_func():
            return "test"

        # Проверяем, что можем запустить асинхронный код
        result = await test_func()
        print(f"✅ Асинхронные функции работают: {result}")
        return True
    except Exception as e:
        print(f"❌ Ошибка асинхронных функций: {e}")
        return False


async def test_config():
    """Тест конфигурации"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from bot.config import Config
        print(f"✅ Конфигурация загружена")
        print(f"  DATA_DIR: {Config.DATA_DIR}")
        print(f"  DEBUG: {Config.DEBUG}")
        return True
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return False


async def test_database():
    """Тест базы данных"""
    try:
        from bot.database import AtomicOperations, CardManager
        print("✅ Модуль database загружен")
        return True
    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    tests = [
        ("Импорты", test_imports),
        ("Асинхронные функции", test_async_functions),
        ("Конфигурация", test_config),
        ("База данных", test_database),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        result = await test_func()
        results.append((name, result))

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ:")
    print("=" * 60)

    all_passed = all(result for _, result in results)

    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"  {name}: {status}")

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Бота можно запускать.")
        print("\nИнструкция:")
        print("1. Заполните файл .env (скопируйте из .env.example)")
        print("2. Установите зависимости: pip install -r requirements.txt")
        print("3. Запустите бота: python -m bot.main")
    else:
        print("⚠️  ЕСТЬ ОШИБКИ. Пожалуйста, исправьте их перед запуском.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())