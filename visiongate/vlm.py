"""Vision-LLM для фоновой проверки: «фото экрана» и «виден ли верх коробки».
Локально — Ollama (по умолчанию), опционально — Anthropic API (только при явном разрешении в настройках)."""
import base64
import hashlib
import json
import os
import re
import time
import urllib.request

from . import imaging
from .config import VLM_CACHE

# Короткий промпт с плоскими вопросами. Вариант с полем «evidence» и длинными определениями давал
# у Qwen2.5-VL 3B ложные «screen» на обычных фото этикеток — маленькая модель хуже держит сложные инструкции.
PROMPT = """You inspect a photo taken in a phone shop. IGNORE watermarks: a semi-transparent diagonal hex hash repeated over the image, green date/GPS/hash text at the bottom, a blue SAMSUNG logo top-left.
Answer strictly as JSON with keys:
"photo_of_screen": true if the photo shows the screen of another phone/monitor (device bezel around the picture, messenger UI, status bar, moire, screen glare), else false;
"box_top_visible": true if the large model name on the box top (e.g. "Galaxy A17") is visible;
"label_visible": true if a white sticker with barcodes and IMEI numbers is visible.
"""


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    data = json.loads(m.group(0)) if m else {}
    def as_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str) and v.strip().lower() in ("true", "false"):
            return v.strip().lower() == "true"
        return None
    return {"screen": as_bool(data.get("photo_of_screen")), "box_top": as_bool(data.get("box_top_visible")),
            "evidence": ""}


def _ollama(jpeg: bytes, s: dict) -> str:
    options = {"temperature": 0, "num_predict": 80, "num_ctx": 4096}
    if int(s.get("ollama_num_thread") or 0) > 0:
        options["num_thread"] = int(s["ollama_num_thread"])
    body = json.dumps({
        "model": s["ollama_model"], "prompt": PROMPT, "format": "json", "stream": False,
        "images": [base64.b64encode(jpeg).decode()], "keep_alive": "60m", "options": options,
    }).encode()
    req = urllib.request.Request(s["ollama_url"].rstrip("/") + "/api/generate", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=s["vlm_timeout_s"]) as r:
        return json.loads(r.read())["response"]


def _anthropic(jpeg: bytes, s: dict) -> str:
    if not s.get("external_allowed"):
        raise RuntimeError("внешний API не разрешён в настройках")
    import anthropic  # опциональная зависимость
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.beta.messages.create(
        model=s["anthropic_model"], max_tokens=1024,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(jpeg).decode()}},
            {"type": "text", "text": PROMPT},
        ]}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("модель отказалась отвечать")
    return "".join(b.text for b in resp.content if b.type == "text")


def _cache_path(raw: bytes, settings: dict):
    model = settings["ollama_model"] if settings["vlm_provider"] == "ollama" else settings["anthropic_model"]
    key = hashlib.sha1((PROMPT + model + str(settings["vlm_image_side"])).encode()).hexdigest()[:8]
    return VLM_CACHE / f"{hashlib.sha1(raw).hexdigest()[:16]}_vlm_{key}.json"


def check(img, settings: dict, raw: bytes | None = None) -> dict:
    """Возвращает {"ok", "screen", "box_top", "evidence", "provider", "seconds", "error"}.
    raw — байты исходного файла: тот же файл + тот же промпт/модель → ответ из кэша (temperature 0)."""
    provider = settings.get("vlm_provider", "off")
    out = {"ok": False, "screen": None, "box_top": None, "evidence": "", "provider": provider,
           "seconds": 0.0, "error": None}
    if provider == "off":
        out["error"] = "VLM выключена в настройках"
        return out
    cache = _cache_path(raw, settings) if raw else None
    if cache and cache.exists():
        try:
            return dict(json.loads(cache.read_text(encoding="utf-8")), cached=True)
        except (OSError, ValueError):
            pass
    out = _run(img, settings, out)
    if cache and out["ok"]:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _run(img, settings: dict, out: dict) -> dict:
    provider = settings["vlm_provider"]
    t = time.time()
    try:
        jpeg = imaging.to_jpeg(imaging.resize_max(img, int(settings["vlm_image_side"])))
        raw = _ollama(jpeg, settings) if provider == "ollama" else _anthropic(jpeg, settings)
        out.update(_parse(raw))
        out["raw"] = raw[:500]
        out["ok"] = out["screen"] is not None
        if not out["ok"]:
            out["error"] = "не удалось разобрать ответ модели"
    except Exception as e:  # сеть, таймаут, отказ — заявка уйдёт на ручную проверку
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    out["seconds"] = round(time.time() - t, 1)
    return out
