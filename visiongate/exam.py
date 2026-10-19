"""Режим экзамена: каждый кейс — строго Approved или Rejected, выгрузка в формате VALIDATION.xlsx.

Логика проверок не меняется: здесь только перевод итогов VisionGate (включая «На ручную проверку»
и «Предварительно одобрено») в два итоговых класса + уверенность, и запись в шаблон Samsung.

Правило разрешения сомнительных случаев (подобрано по смыслу и по тестовому датасету, см. README):
  1. Подозрение на фото экрана (признак интерфейса или VLM)      → Rejected, «photo of photo…», низкая.
  2. Одно и то же фото в обоих слотах                             → Rejected, низкая.
  3. IMEI прочитан, но блок IMEI1+IMEI2 не подтверждён (скан)      → Rejected, «Cutted photo», низкая.
  4. Совпал только штрихкод / только «соседний» IMEI2:
       другое фото подтвердило IMEI текстом                        → Approved, низкая;
       иначе                                                       → Rejected, «blurry/dark/unreadable», низкая.
  5. Проверка экрана не выполнялась (VLM выключена/не ответила)    → Approved, низкая.
Отказ с конкретным дефектом и одобрение с пройденной проверкой экрана — высокая уверенность.
"""
import io
from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font

# Значения причин — как в эталоне VALIDATION.xlsx
TEMPLATE_REASON = {
    "NO_SERIAL": "Photo without serial number",
    "BLURRY_DARK_UNREADABLE": "blurry/dark/unreadable",
    "CROPPED": "Cutted photo",
    "PHOTO_OF_SCREEN": "photo of photo from other device",
}
OK = "OK"
APPROVED, REJECTED = "Approved", "Rejected"
HEADER = ["№", "SN/IMEI", "Create Date", "Registration Status", "Description", "Scan (not a photo)",
          "Final_Status", "Reason of rejection"]
WIDTHS = [8.4, 18, 14.3, 12, 34, 34, 16, 48]
EXTRA_REASON = {  # ошибки, для которых в шаблоне нет значения по фото, — только в «Reason of rejection»
    "IMEI_MISMATCH": "IMEI mismatch (photos / entered IMEI)",
    "INVALID_IMEI": "Invalid IMEI (Luhn check failed)",
    "DUPLICATE": "Same photo uploaded to both slots",
}


def _slot_errors(d: dict) -> list[str]:
    """Все найденные ошибки по одному фото (значения шаблона)."""
    errs = []
    if d.get("status") == "reject" and d.get("reason") in TEMPLATE_REASON:
        errs.append(TEMPLATE_REASON[d["reason"]])
    # фото «на ручную» с предполагаемой причиной: в отклонённом кейсе это тоже найденная проблема
    if d.get("status") == "review" and d.get("suspected") in TEMPLATE_REASON:
        errs.append(TEMPLATE_REASON[d["suspected"]])
    screen = (d.get("screen_check") in ("suspected", "ui_detected") or bool(d.get("ui_hits"))
              or d.get("suspected") == "PHOTO_OF_SCREEN")
    if screen and TEMPLATE_REASON["PHOTO_OF_SCREEN"] not in errs:
        errs.append(TEMPLATE_REASON["PHOTO_OF_SCREEN"])
    return errs


def resolve(res: dict) -> dict:
    """Итог VisionGate → {final, confidence, device, scan, reason, note}."""
    final = res["final"]
    status = final["status"]
    slots = res.get("slots") or {}
    errs = {s: _slot_errors(slots.get(s, {})) for s in ("device", "scan")}
    extra = [EXTRA_REASON[r] for r in final.get("reasons", []) if r in EXTRA_REASON]
    if final.get("duplicate"):
        extra.append(EXTRA_REASON["DUPLICATE"])
    note = ""

    if status == "REJECTED":
        out, conf = REJECTED, "high"
    elif status == "APPROVED":
        out, conf = APPROVED, "high"
    elif status == "PRELIMINARY":
        out, conf, note = APPROVED, "low", "screen-photo check not run"
    else:  # REVIEW — разрешаем по правилу из docstring
        conf = "low"
        susp = {s: slots.get(s, {}).get("suspected") for s in ("device", "scan")}
        text_ok = any(slots.get(s, {}).get("status") == "ok" and "text" in slots.get(s, {}).get("matched_by", [])
                      for s in ("device", "scan"))
        if any(v == "PHOTO_OF_SCREEN" for v in susp.values()) or any(errs[s] and TEMPLATE_REASON["PHOTO_OF_SCREEN"] in errs[s] for s in errs):
            out, note = REJECTED, "suspected photo of a screen"
        elif final.get("duplicate"):
            out, note = REJECTED, "same photo in both slots"
        elif any(v == "CROPPED" for v in susp.values()):
            out, note = REJECTED, "IMEI1+IMEI2 block not confirmed (label may be cut)"
            for s, v in susp.items():
                if v == "CROPPED" and TEMPLATE_REASON["CROPPED"] not in errs[s]:
                    errs[s].append(TEMPLATE_REASON["CROPPED"])
        elif any(slots.get(s, {}).get("status") == "review" and (susp[s] == "BLURRY_DARK_UNREADABLE"
                                                                or slots.get(s, {}).get("sibling_only"))
                 for s in ("device", "scan")):
            if text_ok:
                out, note = APPROVED, "IMEI matched by barcode only on one photo; text-confirmed on the other"
            else:
                out, note = REJECTED, "IMEI not readable as text on any photo (barcode only)"
                for s in ("device", "scan"):
                    if slots.get(s, {}).get("status") == "review" and TEMPLATE_REASON["BLURRY_DARK_UNREADABLE"] not in errs[s]:
                        errs[s].append(TEMPLATE_REASON["BLURRY_DARK_UNREADABLE"])
        else:  # VLM недоступна / выключена: проверка экрана не выполнена
            out, note = APPROVED, "screen-photo check not completed"

    if out == APPROVED:
        dev, scn, reason = OK, OK, ""
    else:
        dev = ", ".join(errs["device"]) or OK
        scn = ", ".join(errs["scan"]) or OK
        all_errs = []
        for e in errs["device"] + errs["scan"] + extra:
            if e not in all_errs:
                all_errs.append(e)
        if not all_errs and note:
            all_errs.append(note)
        reason = "; ".join(all_errs)
    return {"final": out, "confidence": conf, "device": dev, "scan": scn, "reason": reason, "note": note}


def write_xlsx(rows: list[dict], template: bytes | None = None) -> bytes:
    """rows: {imei, date, device, scan, final, reason, confidence, note, device_file, scan_file, imei_source}.
    Первый лист — точно колонки шаблона VALIDATION.xlsx (заголовки берутся из шаблона, если он дан).
    Второй лист «Details» — уверенность и пояснения (в шаблоне таких колонок нет)."""
    header = HEADER
    if template:
        try:
            tws = load_workbook(io.BytesIO(template), read_only=True).active
            th = [c.value for c in next(tws.iter_rows(min_row=1, max_row=1))]
            if len(th) >= 8 and str(th[1]).strip() == "SN/IMEI":
                header = [str(v) if v is not None else "" for v in th[:8]]
        except Exception:
            pass
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, r in enumerate(rows, 1):
        ws.append([i, r["imei"], r["date"], "Approved", r["device"], r["scan"], r["final"], r["reason"] or None])
    for i, w in enumerate(WIDTHS):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    d = wb.create_sheet("Details")
    d.append(["№", "SN/IMEI", "Final_Status", "Confidence", "Why (low confidence)", "IMEI source",
              "Box photo file", "Scan file"])
    for c in d[1]:
        c.font = Font(bold=True)
    for i, r in enumerate(rows, 1):
        d.append([i, r["imei"], r["final"], r["confidence"], r["note"], r.get("imei_source", ""),
                  r.get("device_file", ""), r.get("scan_file", "")])
    for col, w in zip("ABCDEFGH", (6, 18, 12, 11, 60, 14, 50, 50)):
        d.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def fmt_date(dt) -> str:
    """Дата в формате шаблона: 01.09.2026."""
    if isinstance(dt, tuple):
        dt = datetime(*dt[:6])
    return dt.strftime("%d.%m.%Y") if dt else ""
