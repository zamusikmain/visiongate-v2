"""Пакетная проверка: ZIP с парами device/scan → таблица результатов → XLSX.
Фото читаются из архива в памяти (без распаковки на диск), архив удаляется после обработки."""
import io
import json
import logging
import re
import threading
import time
import uuid
import zipfile
from pathlib import PurePosixPath

from . import decision, imei, pipeline, validation
from .config import BATCHES, load_settings

log = logging.getLogger("visiongate.batch")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_ZIP = 500 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 ** 3
MAX_FILE = 25 * 1024 * 1024
MAX_PAIRS = 300

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class BatchError(ValueError):
    pass


def _role(name: str) -> str | None:
    n = name.lower()
    if n.startswith("device") or n.startswith("box"):
        return "device"
    if n.startswith("scan") or n.startswith("label"):
        return "scan"
    return None


def _suffix(stem: str) -> str:
    """Общая часть имени без префикса роли: device_abc / scan-abc → abc."""
    return re.sub(r"^(device|box|scan|label)[\s_\-.]*", "", stem, flags=re.I).lower()


def parse_zip(data: bytes) -> tuple[list[dict], dict, list[str]]:
    """Возвращает (пары, эталон, предупреждения). Пара: {key, folder, imei_name, device, scan} (имена в архиве).
    IMEI в именах не нужен: пара — это единственные device*/scan* в папке или файлы с одинаковым окончанием
    (device_123.jpg ↔ scan_123.jpg). Если в имени есть 15 цифр, они запоминаются (imei_name) — для сверки
    по желанию пользователя и для сопоставления с эталоном."""
    if len(data) > MAX_ZIP:
        raise BatchError("ZIP больше 500 МБ")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise BatchError("Файл не является ZIP-архивом")
    infos = [i for i in zf.infolist() if not i.is_dir() and "__MACOSX" not in i.filename]
    if sum(i.file_size for i in infos) > MAX_UNPACKED:
        raise BatchError("Распакованный размер архива больше 2 ГБ")
    folders: dict[str, dict[str, list]] = {}
    truth, warnings = {}, []
    for i in infos:
        p = PurePosixPath(i.filename.replace("\\", "/"))
        if p.name.lower() == "validation.xlsx":
            try:
                truth = validation.read(zf.read(i))
            except Exception as e:
                warnings.append(f"VALIDATION.xlsx не прочитан: {e}")
            continue
        if p.suffix.lower() not in IMAGE_EXT:
            continue
        role = _role(p.name)
        if not role:
            warnings.append(f"Пропущен {i.filename}: имя должно начинаться с device_ или scan_")
            continue
        if i.file_size > MAX_FILE:
            warnings.append(f"Пропущен {i.filename}: больше 25 МБ")
            continue
        folders.setdefault(str(p.parent), {"device": [], "scan": []})[role].append(i.filename)
    pairs = []
    for folder, roles in sorted(folders.items()):
        devs, scans = roles["device"], roles["scan"]
        if len(devs) == 1 and len(scans) == 1:
            matched = [(devs[0], scans[0])]
        else:  # несколько пар в одной папке — по одинаковому окончанию имени
            by_suffix = {_suffix(PurePosixPath(s).stem): s for s in scans}
            matched = [(d, by_suffix[_suffix(PurePosixPath(d).stem)]) for d in devs
                       if _suffix(PurePosixPath(d).stem) in by_suffix]
            used = {f for pair in matched for f in pair}
            for f in devs + scans:
                if f not in used:
                    warnings.append(f"Нет пары для {f}: в папке несколько фото, окончания имён должны совпадать "
                                    f"(device_X.jpg ↔ scan_X.jpg)")
        for d, s in matched:
            m = re.search(r"\d{15}", PurePosixPath(d).stem) or re.search(r"\d{15}", PurePosixPath(folder).name)
            pairs.append({"folder": folder, "imei_name": m.group(0) if m else "", "device": d, "scan": s,
                          "key": f"{folder}/{PurePosixPath(d).name}"})
    if not pairs:
        raise BatchError("В архиве не найдено ни одной пары device_*/scan_*")
    if len(pairs) > MAX_PAIRS:
        raise BatchError(f"Слишком много пар ({len(pairs)}), максимум {MAX_PAIRS}")
    return pairs, truth, warnings


def _truth_for(truth: dict, *nums: str):
    """Эталон по IMEI: из имени файла или определённому с фото (в т.ч. IMEI2 того же устройства)."""
    for n in nums:
        if not n:
            continue
        if n in truth:
            return truth[n]
        for k, v in truth.items():
            if imei.same_serial(k, n):
                return v
    return None


def _row(pair, res, truth, error=None) -> dict:
    num = (res or {}).get("imei") or ""
    t = _truth_for(truth, pair["imei_name"], num) if truth else None
    row = {"folder": pair["folder"], "imei": num, "imei_source": (res or {}).get("imei_source", ""),
           "imei_name": pair["imei_name"], "device_file": pair["device"], "scan_file": pair["scan"],
           "error": error, "truth": t}
    if res:
        f = res["final"]
        row.update(status=f["status"], reasons=f["reasons"], message=f["message"], message_en=f.get("message_en", ""),
                   fast_seconds=res.get("fast_seconds"), vlm_seconds=res.get("vlm_seconds"),
                   vlm_cached=all((res.get("vlm") or {}).get(s, {}).get("cached") for s in pipeline.SLOTS)
                   if res.get("vlm") else None,
                   slots={s: {k: res["slots"][s].get(k) for k in ("status", "reason", "message", "message_en",
                                                                   "read_imeis", "barcode_imeis")}
                          for s in pipeline.SLOTS})
    else:
        row.update(status="ERROR", reasons=[], message=error, message_en=error, slots={})
    if t:
        ok_pred = row["status"] in ("APPROVED", "PRELIMINARY")
        row["agree"] = None if row["status"] in ("REVIEW", "ERROR") else \
            (ok_pred == (t["final"] == "APPROVED"))
    return row


def _save(job):
    (BATCHES / f"{job['id']}.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")


def _run(job_id: str, data: bytes, pairs, truth, use_vlm: bool, use_name_imei: bool):
    job = _jobs[job_id]
    settings = dict(load_settings())
    if not use_vlm:
        settings["vlm_provider"] = "off"
        settings["require_screen_check"] = False  # без VLM показываем «предварительно одобрено», а не «на ручную»
    zf = zipfile.ZipFile(io.BytesIO(data))
    for pair in pairs:
        try:
            raw = {s: zf.read(pair[s]) for s in pipeline.SLOTS}
            imgs = {s: pipeline.load(raw[s]) for s in pipeline.SLOTS}
            # по умолчанию IMEI из имён не используется: номер читается с фото, фото сверяются между собой
            res = pipeline.fast_check(imgs, pair["imei_name"] if use_name_imei else "", settings)
            if res["needs_vlm"]:
                job["stage"] = f"VLM: {PurePosixPath(pair['device']).name}"
                res = pipeline.vlm_check(imgs, res, settings, raw=raw)
            if not use_vlm and res["final"]["status"] == "APPROVED":
                res["final"]["status"] = "PRELIMINARY"  # проверка экрана не выполнялась
            row = _row(pair, res, truth)
        except Exception as e:
            log.exception("batch %s: %s", job_id, pair["key"])
            row = _row(pair, None, truth, error=str(e)[:300])
        with _lock:
            job["rows"].append(row)
            job["done"] += 1
            job["stage"] = ""
        _save(job)
    job["state"] = "done"
    job["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save(job)


def start(data: bytes, filename: str, use_vlm: bool, use_name_imei: bool = False) -> dict:
    pairs, truth, warnings = parse_zip(data)
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "filename": filename, "state": "running", "total": len(pairs), "done": 0, "stage": "",
           "use_vlm": use_vlm, "use_name_imei": use_name_imei, "has_truth": bool(truth), "warnings": warnings, "rows": [],
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _jobs[job_id] = job
    BATCHES.mkdir(parents=True, exist_ok=True)
    _save(job)
    threading.Thread(target=_run, args=(job_id, data, pairs, truth, use_vlm, use_name_imei), daemon=True,
                     name=f"batch-{job_id}").start()
    return job


def get(job_id: str) -> dict | None:
    if not re.fullmatch(r"[0-9a-f]{10}", job_id or ""):
        return None
    if job_id in _jobs:
        return _jobs[job_id]
    p = BATCHES / f"{job_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# --- XLSX ---
_FILL = {"APPROVED": "E5F5EA", "PRELIMINARY": "E5F5EA", "REJECTED": "FDECEA", "REVIEW": "FDF3E1", "ERROR": "EEEEEE"}
_HDR = {
    "ru": ["Файл фото коробки", "IMEI", "Источник IMEI", "Итог", "Причины", "Пояснение", "Фото коробки", "Скан этикетки",
           "IMEI на фото коробки", "IMEI на скане", "Быстрая фаза, с", "VLM, с", "Эталон", "Совпало с эталоном"],
    "en": ["Box photo file", "IMEI", "IMEI source", "Result", "Reasons", "Explanation", "Box photo", "Label scan",
           "IMEI on box photo", "IMEI on scan", "Fast phase, s", "VLM, s", "Reference", "Matches reference"],
}


def to_xlsx(job: dict, lang: str = "ru") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    li = 1 if lang == "en" else 0
    slot_st = {"ok": ("OK", "OK"), "review": ("На ручную", "Review"), "reject": ("Отклонено", "Rejected")}
    wb = Workbook()
    ws = wb.active
    ws.title = "Results" if li else "Результаты"
    ws.append(_HDR["en" if li else "ru"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in job["rows"]:
        def slot(s):
            d = r["slots"].get(s) or {}
            if not d:
                return ""
            st = slot_st.get(d["status"], (d["status"],) * 2)[li]
            return f"{st}{' — ' + d['reason'] if d.get('reason') else ''}"
        t = r.get("truth")
        status = decision.STATUS.get(r["status"], (r["status"], r["status"]))[li] if r["status"] != "ERROR" else "ERROR"
        src = {"photo": ("с фото", "from photo"), "entered": ("из имени файла", "from file name"),
               "none": ("не найден", "not found")}.get(r.get("imei_source") or "none", ("", ""))[li]
        ws.append([r.get("device_file") or r["folder"], r["imei"], src, status, ", ".join(r.get("reasons") or []),
                   r.get("message_en" if li else "message") or "", slot("device"), slot("scan"),
                   ", ".join((r["slots"].get("device") or {}).get("read_imeis") or []),
                   ", ".join((r["slots"].get("scan") or {}).get("read_imeis") or []),
                   r.get("fast_seconds"), r.get("vlm_seconds"),
                   f"{t['final']} ({t['device']} / {t['scan']})" if t else "",
                   "" if r.get("agree") is None else (("yes" if li else "да") if r["agree"] else ("no" if li else "нет"))])
        ws.cell(ws.max_row, 4).fill = PatternFill("solid", fgColor=_FILL.get(r["status"], "FFFFFF"))
    widths = [44, 18, 16, 22, 30, 70, 30, 30, 34, 34, 12, 10, 40, 12]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    # сводка
    s = wb.create_sheet("Summary" if li else "Сводка")
    from collections import Counter
    cnt = Counter(r["status"] for r in job["rows"])
    s.append(["File" if li else "Файл", job["filename"]])
    s.append(["Pairs" if li else "Пар", job["total"]])
    for k in ("APPROVED", "PRELIMINARY", "REVIEW", "REJECTED", "ERROR"):
        if cnt.get(k):
            s.append([decision.STATUS.get(k, (k, k))[li], cnt[k]])
    if job.get("has_truth"):
        agree = [r["agree"] for r in job["rows"] if r.get("agree") is not None]
        s.append([])
        s.append(["Auto decisions matching reference" if li else "Авто-решений совпало с эталоном",
                  f"{sum(agree)} / {len(agree)}"])
        s.append(["False approvals" if li else "Ложных одобрений",
                  sum(1 for r in job["rows"] if r.get("truth") and r["truth"]["final"] == "REJECTED"
                      and r["status"] in ("APPROVED", "PRELIMINARY"))])
        s.append(["False rejections" if li else "Ложных отказов",
                  sum(1 for r in job["rows"] if r.get("truth") and r["truth"]["final"] == "APPROVED"
                      and r["status"] == "REJECTED")])
    s.column_dimensions["A"].width = 36
    s.column_dimensions["B"].width = 40
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
