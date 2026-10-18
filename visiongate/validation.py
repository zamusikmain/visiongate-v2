"""Чтение эталона VALIDATION.xlsx (формат тестового датасета)."""
import io

import openpyxl

from . import imei

REASON_MAP = {
    "ok": "OK",
    "photo without serial number": "NO_SERIAL",
    "blurry/dark/unreadable": "BLURRY_DARK_UNREADABLE",
    "cutted photo": "CROPPED",
    "photo of photo from other device": "PHOTO_OF_SCREEN",
}


def read(data) -> dict:
    """data — путь или байты. Возвращает {imei: {"device", "scan", "final"}}; нераспознанные причины — как есть."""
    src = io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
    ws = openpyxl.load_workbook(src, data_only=True, read_only=True).active
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < 7 or not row[1]:
            continue
        key = imei.normalize(str(row[1]))
        if len(key) != 15:
            continue
        def reason(v):
            s = str(v or "").strip()
            return REASON_MAP.get(s.lower(), s)
        out[key] = {"device": reason(row[4]), "scan": reason(row[5]), "final": str(row[6] or "").strip().upper()}
    return out
