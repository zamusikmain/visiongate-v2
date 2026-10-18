"""Пути и настройки. Пользовательские настройки хранятся в storage/settings.json."""
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORAGE = Path(os.environ.get("VG_STORAGE", ROOT / "storage"))
UPLOADS = STORAGE / "uploads"
DB_PATH = STORAGE / "visiongate.db"
SETTINGS_PATH = STORAGE / "settings.json"
CERT_DIR = STORAGE / "certs"
VLM_CACHE = STORAGE / "vlm_cache"
BATCHES = STORAGE / "batches"
STATIC = ROOT / "static"
REPORTS = ROOT / "reports"

DEFAULTS = {
    # Фоновая проверка «фото экрана» и «верх коробки»
    "vlm_provider": "ollama",          # ollama | anthropic | off
    "vlm_for_rejected": False,         # вариант B: не гонять VLM для уже отклонённых заявок
    "require_screen_check": True,      # без VLM одобрение не ставится, заявка уходит на ручную проверку
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen2.5vl:3b",
    "vlm_image_side": 896,
    "vlm_timeout_s": 600,
    # Потоки CPU для Ollama: оставляем ядра быстрой фазе, иначе пока идёт VLM, ответ продавцу
    # замедляется с ~5 до ~10 с. 0 — решает Ollama (быстрее VLM, медленнее быстрая фаза).
    "ollama_num_thread": 4,
    # Внешний API (выключен по умолчанию; ключ берётся из ANTHROPIC_API_KEY)
    "external_allowed": False,
    "anthropic_model": "claude-opus-5-5",
}

_lock = threading.Lock()


def ensure_dirs():
    for p in (STORAGE, UPLOADS, CERT_DIR, REPORTS, VLM_CACHE, BATCHES):
        p.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    s = dict(DEFAULTS)
    if SETTINGS_PATH.exists():
        try:
            s.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return s


def save_settings(update: dict) -> dict:
    with _lock:
        s = load_settings()
        for k, v in update.items():
            if k in DEFAULTS:
                s[k] = type(DEFAULTS[k])(v) if not isinstance(DEFAULTS[k], bool) else bool(v)
        ensure_dirs()
        SETTINGS_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        return s
