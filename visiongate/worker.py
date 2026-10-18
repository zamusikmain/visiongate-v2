"""Фоновая очередь VLM-проверок: один поток, заявки по порядку."""
import logging
import queue
import threading

from . import db, pipeline
from .config import UPLOADS, load_settings

log = logging.getLogger("visiongate.worker")
_q: "queue.Queue[int]" = queue.Queue()
_current = {"id": None}


def enqueue(sid: int):
    _q.put(sid)


def queue_size() -> int:
    return _q.qsize() + (1 if _current["id"] else 0)


def _process(sid: int):
    rec = db.get(sid)
    if not rec or rec["phase"] not in ("vlm_pending", "vlm_running"):
        return
    db.update(sid, phase="vlm_running")
    raw = {s: (UPLOADS / rec[f"{s}_file"]).read_bytes() for s in pipeline.SLOTS}
    imgs = {s: pipeline.load(raw[s]) for s in pipeline.SLOTS}
    res = pipeline.vlm_check(imgs, rec["result"], load_settings(), raw=raw)
    db.update(sid, phase="final", status=res["final"]["status"], result=res, vlm_seconds=res["vlm_seconds"])
    log.info("submission %s: %s (VLM %.0f s)", sid, res["final"]["status"], res["vlm_seconds"])


def _loop():
    while True:
        sid = _q.get()
        _current["id"] = sid
        try:
            _process(sid)
        except Exception as e:
            log.exception("VLM check failed for submission %s", sid)
            rec = db.get(sid) or {}
            res = rec.get("result") or {}
            res["final"] = {"status": "REVIEW", "reasons": [],
                            "message": f"Фоновая проверка завершилась ошибкой ({type(e).__name__}) — нужна проверка человеком."}
            db.update(sid, phase="final", status="REVIEW", result=res)
        finally:
            _current["id"] = None


def start():
    threading.Thread(target=_loop, daemon=True, name="vlm-worker").start()
    for sid in db.pending_vlm():  # недоделанные после перезапуска
        enqueue(sid)
