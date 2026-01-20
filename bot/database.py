import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Для блокировок
if os.name == 'nt':  # Windows
    import msvcrt
else:  # Linux/Mac
    import fcntl

from .config import Config
from .schemas import validate_card, create_history_entry

logger = logging.getLogger(__name__)


class AtomicOperations:
    """Атомарные операции по ТЗ"""

    @staticmethod
    def get_next_number() -> int:
        """
        Получение следующего номера атомарно
        Для Windows используем msvcrt.locking, для Linux - fcntl.flock
        """
        try:
            # Создаем lock файл
            lock_file = Config.COUNTER_FILE.with_suffix('.lock')

            if os.name == 'nt':  # Windows
                # Для Windows используем msvcrt
                import time

                # Попытка получить блокировку
                lock_acquired = False
                start_time = time.time()

                while not lock_acquired and (time.time() - start_time) < 10:
                    try:
                        # Пытаемся создать lock файл
                        lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                        lock_acquired = True
                    except FileExistsError:
                        time.sleep(0.1)

                if not lock_acquired:
                    raise TimeoutError("Не удалось получить блокировку counter.txt")

                try:
                    return AtomicOperations._increment_counter()
                finally:
                    os.close(lock_fd)
                    if lock_file.exists():
                        os.unlink(lock_file)
            else:  # Linux/Mac
                # Используем fcntl.flock как в ТЗ
                with open(lock_file, 'w') as lock_f:
                    fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
                    try:
                        return AtomicOperations._increment_counter()
                    finally:
                        fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
                        if lock_file.exists():
                            lock_file.unlink()

        except Exception as e:
            logger.error(f"Ошибка атомарного счетчика: {e}")
            raise

    @staticmethod
    def _increment_counter() -> int:
        """Увеличение счетчика (внутренний метод)"""
        # Читаем текущее значение
        if Config.COUNTER_FILE.exists():
            with open(Config.COUNTER_FILE, 'r') as f:
                content = f.read().strip()
                current = int(content) if content.isdigit() else 0
        else:
            current = 0

        next_value = current + 1

        # Записываем во временный файл
        temp_file = Config.COUNTER_FILE.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            f.write(f"{next_value}\n")
            f.flush()
            os.fsync(f.fileno())

        # Атомарная замена
        os.replace(temp_file, Config.COUNTER_FILE)

        return next_value

    @staticmethod
    def write_json_atomic(file_path: Path, data: dict) -> bool:
        """Атомарная запись JSON файла"""
        temp_path = file_path.with_suffix('.json.tmp')

        try:
            # Записываем во временный файл
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                if hasattr(f, 'fileno'):
                    os.fsync(f.fileno())

            # Валидация JSON перед заменой
            with open(temp_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                is_valid, error_msg = validate_card(loaded_data)
                if not is_valid:
                    logger.error(f"Невалидный JSON: {error_msg}")
                    os.remove(temp_path)
                    return False

            # Атомарная замена
            os.replace(temp_path, file_path)
            return True

        except Exception as e:
            logger.error(f"Ошибка атомарной записи {file_path}: {e}")
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False


class CardManager:
    """Управление карточками заявок"""

    @staticmethod
    def create_card(user_data: dict, user_id: int, city: str) -> Optional[Dict[str, Any]]:
        """Создание новой карточки"""
        try:
            # Получаем следующий номер
            card_id = AtomicOperations.get_next_number()
            card_number = str(card_id).zfill(4)

            # Формируем карточку
            card = {
                "id": card_id,
                "number": card_number,
                "city": city,
                "fio": "",
                "account_meta": user_data,
                "extra": "",
                "status": "city_selected",
                "decision": "pending",
                "history": [
                    create_history_entry(
                        source="system",
                        entry_type="command",
                        text=f"Создана заявка. Город: {city}"
                    )
                ]
            }

            # Сохраняем
            file_path = Config.CARDS_DIR / f"{card_number}.json"
            if AtomicOperations.write_json_atomic(file_path, card):
                logger.info(f"Создана карточка {card_number}")
                return card

            return None

        except Exception as e:
            logger.error(f"Ошибка создания карточки: {e}")
            return None

    @staticmethod
    def load_card(card_number: str) -> Optional[Dict[str, Any]]:
        """Загрузка карточки"""
        try:
            card_number = card_number.zfill(4)
            file_path = Config.CARDS_DIR / f"{card_number}.json"

            if not file_path.exists():
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Валидация
            is_valid, error_msg = validate_card(data)
            if not is_valid:
                logger.error(f"Невалидная карточка {card_number}: {error_msg}")
                # Логируем ошибку
                error_log = Config.LOGS_DIR / "errors.log"
                with open(error_log, 'a', encoding='utf-8') as err_file:
                    timestamp = datetime.utcnow().isoformat() + "Z"
                    err_file.write(f"{timestamp} - Invalid card {card_number}: {error_msg}\n")
                return None

            return data

        except Exception as e:
            logger.error(f"Ошибка загрузки карточки {card_number}: {e}")
            return None

    @staticmethod
    def update_card(card_number: str, updates: dict, history_entry: dict = None) -> bool:
        """Обновление карточки"""
        card = CardManager.load_card(card_number)
        if not card:
            return False

        # Обновляем поля
        card.update(updates)

        # Добавляем историю
        if history_entry:
            card["history"].append(history_entry)

        # Сохраняем
        file_path = Config.CARDS_DIR / f"{card_number.zfill(4)}.json"
        return AtomicOperations.write_json_atomic(file_path, card)

    @staticmethod
    def get_cards_by_city(city: str) -> List[Dict[str, Any]]:
        """Получение карточек по городу"""
        cards = []

        try:
            for file_path in Config.CARDS_DIR.glob("*.json"):
                try:
                    card = CardManager.load_card(file_path.stem)
                    if card and card.get("city") == city:
                        cards.append(card)
                except Exception as e:
                    logger.error(f"Ошибка чтения {file_path}: {e}")
                    continue

            # Сортировка по номеру
            cards.sort(key=lambda x: x["id"])
            return cards

        except Exception as e:
            logger.error(f"Ошибка получения карточек: {e}")
            return []