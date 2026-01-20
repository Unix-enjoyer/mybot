import jsonschema
from jsonschema import validate
from datetime import datetime

CARD_SCHEMA = {
    "type": "object",
    "required": [
        "id", "number", "city", "fio", "account_meta",
        "extra", "status", "decision", "history"
    ],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "number": {"type": "string", "pattern": "^\\d{4}$"},
        "city": {"type": "string", "enum": ["Москва", "Не Москва"]},
        "fio": {"type": "string"},
        "account_meta": {
            "type": "object",
            "required": ["user_id"],
            "properties": {
                "username": {"type": "string"},
                "user_id": {"type": "integer"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "bio": {"type": "string"},
                "language_code": {"type": "string"},
                "is_premium": {"type": "boolean"},
                "is_bot": {"type": "boolean"},
                "link": {"type": "string"},
                "additional_profile_info": {"type": "string"},
                "profile_photo_file_id": {"type": "string"}
            }
        },
        "extra": {"type": "string"},
        "status": {
            "type": "string",
            "enum": [
                "new", "city_selected", "fio_added", "extra_added",
                "sent_to_review", "approved", "rejected"
            ]
        },
        "decision": {
            "type": "string",
            "enum": ["pending", "approved", "rejected"]
        },
        "history": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["ts", "source", "type"],
                "properties": {
                    "ts": {"type": "string", "format": "date-time"},
                    "source": {"type": "string", "enum": ["user", "admin", "system"]},
                    "type": {"type": "string", "enum": ["text", "photo", "file", "voice", "command"]},
                    "text": {"type": "string"},
                    "meta": {"type": "object"}
                }
            }
        }
    }
}

def validate_card(data: dict) -> tuple[bool, str]:
    """Валидация карточки по схеме"""
    try:
        validate(instance=data, schema=CARD_SCHEMA)
        return True, ""
    except jsonschema.exceptions.ValidationError as e:
        return False, f"Ошибка валидации: {e.message}"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"

def create_history_entry(source: str, entry_type: str, text: str = "", meta: dict = None) -> dict:
    """Создание записи истории (ISO8601 UTC по ТЗ)"""
    return {
        "ts": datetime.utcnow().isoformat() + "Z",
        "source": source,
        "type": entry_type,
        "text": text,
        "meta": meta or {}
    }