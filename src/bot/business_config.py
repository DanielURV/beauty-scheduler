import json, os

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "business_config.json")

_DEFAULTS = {
    "emoji": "✂️",
}


def load() -> dict:
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**_DEFAULTS, **json.load(f)}
    except Exception:
        return dict(_DEFAULTS)


def save(data: dict):
    os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
    current = load()
    current.update({k: v for k, v in data.items() if k in _DEFAULTS})
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
