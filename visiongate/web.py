"""HTTP-API и раздача страниц."""
import io
import json
import logging
import urllib.request
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from starlette.concurrency import run_in_threadpool

from . import batch, db, decision, imei, pipeline, worker
from .config import REPORTS, STATIC, UPLOADS, ensure_dirs, load_settings, save_settings

log = logging.getLogger("visiongate")
MAX_UPLOAD = 25 * 1024 * 1024

app = FastAPI(title="VisionGate")


@app.on_event("startup")
def _startup():
    ensure_dirs()
    db.init()
    worker.start()
    # прогрев OCR в фоне: первая заявка не должна ждать загрузки моделей
    import threading
    import numpy as np
    from . import ocr
    threading.Thread(target=lambda: ocr.read(np.full((64, 256, 3), 255, np.uint8)), daemon=True).start()


def _page(name):
    return FileResponse(STATIC / name, headers={"Cache-Control": "no-cache"})


@app.get("/")
def index():
    return _page("index.html")


@app.get("/s/{sid}")
def submission_page(sid: int):
    return _page("submission.html")


@app.get("/review")
def review_page():
    return _page("review.html")


@app.get("/settings")
def settings_page():
    return _page("settings.html")


async def _read_image(f: UploadFile) -> tuple[bytes, str]:
    data = await f.read()
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(400, f"Файл {f.filename!r}: пустой или больше 25 МБ")
    try:
        fmt = (Image.open(io.BytesIO(data)).format or "jpeg").lower()
    except Exception:
        raise HTTPException(400, f"Файл {f.filename!r} не является изображением")
    return data, {"jpeg": "jpg"}.get(fmt, fmt)


def _public(rec: dict) -> dict:
    """Ответ для страницы продавца: без сырых OCR-строк."""
    res = rec.get("result") or {}
    slots = {}
    for s, d in (res.get("slots") or {}).items():
        ev = (res.get("evidence") or {}).get(s, {})
        slots[s] = {"status": d["status"], "reason": d.get("reason"), "message": d.get("message"),
                    "message_en": d.get("message_en", d.get("message")),
                    "read_imeis": d.get("read_imeis", []), "matched_by": d.get("matched_by", []),
                    "barcodes": [b["text"] for b in ev.get("barcodes", [])]}
    final = res.get("final") or {}
    st = decision.STATUS.get(rec["status"], (rec["status"], rec["status"]))
    reasons = final.get("reasons", [])
    return {"id": rec["id"], "imei": rec["imei"], "created_at": rec["created_at"], "status": rec["status"],
            "status_ru": st[0], "status_en": st[1], "phase": rec["phase"],
            "message": final.get("message", ""), "message_en": final.get("message_en", final.get("message", "")),
            "reasons": reasons,
            "reasons_ru": [decision.REASONS[r][0] for r in reasons if r in decision.REASONS],
            "reasons_en": [decision.REASONS[r][1] for r in reasons if r in decision.REASONS],
            "slots": slots, "client_barcode": rec.get("client_barcode"),
            "fast_seconds": rec.get("fast_seconds"), "vlm_seconds": rec.get("vlm_seconds"),
            "queue": worker.queue_size() if rec["phase"] in ("vlm_pending", "vlm_running") else 0,
            "manual_status": rec.get("manual_status"), "manual_comment": rec.get("manual_comment")}


@app.post("/api/submissions")
async def create_submission(imei_value: str = Form(..., alias="imei"), device: UploadFile = File(...),
                            scan: UploadFile = File(...), client_barcode: str = Form("")):
    entered = imei.normalize(imei_value)
    if len(entered) != 15:
        raise HTTPException(400, "IMEI должен состоять из 15 цифр")
    files = {"device": await _read_image(device), "scan": await _read_image(scan)}
    sid = db.create(entered, imei.normalize(client_barcode) or None)
    names = {}
    (UPLOADS / str(sid)).mkdir(parents=True, exist_ok=True)
    for slot, (data, ext) in files.items():
        names[slot] = f"{sid}/{slot}_{uuid.uuid4().hex[:8]}.{ext}"
        (UPLOADS / names[slot]).write_bytes(data)
    settings = load_settings()
    def work():
        images = {s: pipeline.load(files[s][0]) for s in pipeline.SLOTS}
        return pipeline.fast_check(images, entered, settings)
    try:
        res = await run_in_threadpool(work)
    except Exception as e:
        log.exception("быстрая проверка упала")
        db.update(sid, status="REVIEW", phase="final", device_file=names["device"], scan_file=names["scan"],
                  result={"final": {"status": "REVIEW", "reasons": [],
                                    "message": f"Ошибка автоматической проверки ({type(e).__name__}) — нужна проверка человеком."}})
        return _public(db.get(sid))
    phase = "vlm_pending" if res["needs_vlm"] else "final"
    db.update(sid, status=res["final"]["status"], phase=phase, result=res, fast_seconds=res["fast_seconds"],
              device_file=names["device"], scan_file=names["scan"])
    if phase == "vlm_pending":
        worker.enqueue(sid)
    return _public(db.get(sid))


@app.get("/api/submissions")
def list_submissions(status: str | None = None, limit: int = 200):
    rows = db.list_(status, min(limit, 1000))
    for r in rows:
        r["status_ru"], r["status_en"] = decision.STATUS.get(r["status"], (r["status"], r["status"]))
    return rows


@app.get("/api/submissions/{sid}")
def get_submission(sid: int, full: bool = False):
    rec = db.get(sid)
    if not rec:
        raise HTTPException(404, "Заявка не найдена")
    out = _public(rec)
    if full:  # для страницы разбора: все признаки
        out["result"] = rec.get("result")
    return out


@app.get("/api/submissions/{sid}/photo/{slot}")
def photo(sid: int, slot: str):
    rec = db.get(sid)
    if not rec or slot not in pipeline.SLOTS or not rec.get(f"{slot}_file"):
        raise HTTPException(404)
    return FileResponse(UPLOADS / rec[f"{slot}_file"])


@app.post("/api/submissions/{sid}/review")
async def manual_review(sid: int, body: dict):
    st = body.get("status")
    if st not in ("APPROVED", "REJECTED"):
        raise HTTPException(400, "status: APPROVED или REJECTED")
    reason = body.get("reason") or None
    if st == "REJECTED" and reason not in decision.REASONS:
        raise HTTPException(400, "Для отклонения выберите причину")
    if not db.get(sid):
        raise HTTPException(404)
    db.update(sid, manual_status=st, manual_reason=reason, manual_comment=(body.get("comment") or "")[:1000],
              reviewed_at=db.now())
    return {"ok": True}


@app.get("/batch")
def batch_page():
    return _page("batch.html")


@app.post("/api/batches")
async def create_batch(file: UploadFile = File(...), use_vlm: bool = Form(True)):
    data = await file.read()
    try:
        job = batch.start(data, file.filename or "batch.zip", use_vlm)
    except batch.BatchError as e:
        raise HTTPException(400, str(e))
    return {k: v for k, v in job.items() if k != "rows"}


@app.get("/api/batches/{job_id}")
def get_batch(job_id: str):
    job = batch.get(job_id)
    if not job:
        raise HTTPException(404, "Пакет не найден")
    return job


@app.get("/api/batches/{job_id}/xlsx")
def batch_xlsx(job_id: str, lang: str = "ru"):
    job = batch.get(job_id)
    if not job:
        raise HTTPException(404, "Пакет не найден")
    return Response(batch.to_xlsx(job, lang), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="visiongate_{job_id}.xlsx"'})


@app.get("/api/settings")
def get_settings():
    return load_settings()


@app.post("/api/settings")
async def set_settings(body: dict):
    if body.get("vlm_provider") == "anthropic" and not body.get("external_allowed", load_settings()["external_allowed"]):
        raise HTTPException(400, "Внешний API нужно сначала явно разрешить (согласование с ИБ)")
    return save_settings(body)


@app.get("/api/health")
def health():
    s = load_settings()
    ollama = None
    if s["vlm_provider"] == "ollama":
        try:
            with urllib.request.urlopen(s["ollama_url"].rstrip("/") + "/api/tags", timeout=3) as r:
                names = [m["name"] for m in json.loads(r.read()).get("models", [])]
            ollama = {"ok": s["ollama_model"] in names, "models": names}
        except Exception as e:
            ollama = {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "vlm_provider": s["vlm_provider"], "ollama": ollama, "queue": worker.queue_size(),
            "reasons": {k: {"ru": v[0], "en": v[1]} for k, v in decision.REASONS.items()},
            "statuses": {k: {"ru": v[0], "en": v[1]} for k, v in decision.STATUS.items()}}


app.mount("/static", StaticFiles(directory=STATIC), name="static")
REPORTS.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=REPORTS, html=True), name="reports")
