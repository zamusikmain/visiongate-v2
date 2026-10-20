"""Запись результатов проверки в БД из любых путей (пакет на сайте, tools/exam.py, tools/import_dataset.py),
чтобы всё было видно в админ-панели. Решения не меняются: сохраняется результат pipeline как есть."""
import io
import uuid

from PIL import Image

from . import db, exam, pipeline
from .config import UPLOADS, ensure_dirs

_init_done = False


def _ensure():
    global _init_done
    if not _init_done:
        ensure_dirs()
        db.init()
        _init_done = True


def _ext(data: bytes) -> str:
    try:
        fmt = (Image.open(io.BytesIO(data)).format or "jpeg").lower()
    except Exception:
        fmt = "jpg"
    return {"jpeg": "jpg"}.get(fmt, fmt)


def _status_phase(res: dict, vlm_pending: bool) -> tuple[str, str]:
    return res["final"]["status"], ("vlm_pending" if vlm_pending else "final")


def save(raw: dict, res: dict | None, source: str, batch_id: str | None = None, entered: str = "",
         error: str | None = None, vlm_pending: bool = False) -> int:
    """Новая заявка с фото и результатом. vlm_pending — фоновая проверка экрана ещё предстоит (видно в очереди)."""
    _ensure()
    imei = ((res or {}).get("imei") or entered or "")
    sid = db.create(imei, None, source=source, batch_id=batch_id)
    names = {}
    (UPLOADS / str(sid)).mkdir(parents=True, exist_ok=True)
    for slot in pipeline.SLOTS:
        if raw and raw.get(slot):
            names[f"{slot}_file"] = f"{sid}/{slot}_{uuid.uuid4().hex[:8]}.{_ext(raw[slot])}"
            (UPLOADS / names[f"{slot}_file"]).write_bytes(raw[slot])
    if res:
        status, phase = _status_phase(res, vlm_pending)
        db.update(sid, status=status, phase=phase, result=res, fast_seconds=res.get("fast_seconds"),
                  vlm_seconds=res.get("vlm_seconds"), **names)
    else:
        db.update(sid, status="REJECTED", phase="final", **names,
                  result={"final": {"status": "REJECTED", "reasons": [], "message": f"Ошибка обработки: {error}",
                                    "message_en": f"Processing error: {error}"}})
    return sid


def update(sid: int, res: dict, vlm_pending: bool = False):
    """Обновить заявку после фоновой проверки экрана."""
    status, phase = _status_phase(res, vlm_pending)
    db.update(sid, status=status, phase=phase, result=res, vlm_seconds=res.get("vlm_seconds"))


def mark_running(sid: int):
    db.update(sid, phase="vlm_running")


def wants_vlm(res: dict, mode: str) -> bool:
    """auto — только кейсы, которые без проверки экрана стали бы Approved; all — все неотклонённые; off — нет."""
    if mode == "off" or not res or not res.get("needs_vlm"):
        return False
    return mode == "all" or exam.resolve(res)["final"] == exam.APPROVED
