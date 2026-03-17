from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_RUNTIME_DIR = Path("runtime")
_RUNTIME_FILE = _RUNTIME_DIR / "state.json"


def _load() -> dict[str, Any]:
    if not _RUNTIME_FILE.exists():
        return {}
    try:
        return json.loads(_RUNTIME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_runtime_value(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def set_runtime_value(key: str, value: Any) -> None:
    _RUNTIME_DIR.mkdir(exist_ok=True)
    payload = _load()
    payload[key] = value
    _RUNTIME_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
