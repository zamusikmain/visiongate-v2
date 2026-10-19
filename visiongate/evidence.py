"""Быстрая фаза: сбор признаков по одному фото (штрихкоды, OCR, яркость).
Признаки не зависят от введённого IMEI — решение принимает decision.py."""
import re
import time

import cv2
import numpy as np

from . import barcode, imaging, imei, ocr

EVIDENCE_VERSION = 9

_LABEL_WORDS = ("IMEI", "SM-", "EID", "S/N", "MODEL", "МОДЕЛЬ", "ЦВЕТ", "COLOR", "MADE IN",
                "ИЗГОТОВ", "СТРАНА", "РАЗМЕР", "ВЕС")
# Признаки интерфейса телефона на снимке экрана — по ТИПАМ, без привязки к конкретным номерам/странам.
# На этикетке Samsung ничего из этого не печатается. Учитываются OCR-искажения: «+» часто читается как «4»,
# «%» — как «3», кириллица (модель OCR китайско-английская) — латинскими двойниками.
_PHONE_FMT = re.compile(r"\+\s?\d{1,3}[\s(.-]{0,2}\d{2,4}[\s).-]{0,2}\d{2,4}[\s.-]?\d{2,4}")
_BATTERY = re.compile(r"(?<!\d)\d{1,3}\s?%")
_CLOCK = re.compile(r"(?<!\d)([01]?\d|2[0-3]):[0-5]\d(?!\d)")   # только с двоеточием: даты с точками — не время
_MESSENGER = re.compile(
    r"ОТВЕТИТЬ|ПЕРЕСЛАТЬ|ТОЛЬКО ЧТО|В СЕТИ|БЫЛ\(А\)|СООБЩЕНИ|ГАЛЕРЕ|ФОТО\b|"   # ru
    r"ЖАУАП|ХАБАРЛАМА|"                                                        # kk
    r"JAVOB|XABAR|"                                                            # uz
    r"\bREPLY\b|FORWARD|ONLINE|LAST SEEN|TYPING|MESSAGE|GALLERY|\bPHOTO\b")    # en
WATERMARK_GREEN = 0.05  # доля ярко-зелёных пикселей в рамке строки: выше — это текст водяного знака


def _ean_ok(d: str) -> bool:
    """Контрольная цифра EAN-13 / UPC-A (12): цифры штрихкода товара с наклейки — не телефон."""
    if len(d) not in (12, 13) or not d.isdigit():
        return False
    body, check = d[:-1], int(d[-1])
    s = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(body)))
    return (10 - s % 10) % 10 == check


def _green_share(mask: np.ndarray, box) -> float:
    x0, y0, x1, y1 = (max(0, int(v)) for v in box)
    m = mask[y0:y1, x0:x1]
    return float((m > 0).mean()) if m.size else 0.0


def ui_signals(lines: list[dict], img: np.ndarray, label_top: float | None) -> tuple[list[str], list[dict]]:
    """Типы признаков интерфейса телефона и строки-доказательства. Строки водяного знака исключаются.
    label_top — верхняя граница текста наклейки (y), если наклейка найдена."""
    h = img.shape[0]
    mask = imaging.green_watermark_mask(img)
    found, proof = set(), []
    for ln in lines:
        t = ln["text"].strip()
        if not t or _green_share(mask, ln["box"]) > WATERMARK_GREEN:
            continue
        up = t.upper()
        compact = re.sub(r"\s", "", t)
        digits = imei.normalize(t)
        kinds = []
        if _PHONE_FMT.search(t) or (re.fullmatch(r"[+4]?\d{10,12}", compact) and 11 <= len(digits) <= 13
                                    and not _ean_ok(digits) and not imei.is_valid_imei(digits)):
            kinds.append("phone")
        if _BATTERY.search(t):
            kinds.append("battery")
        if _CLOCK.search(t):
            kinds.append("clock")
        if _MESSENGER.search(up):
            kinds.append("messenger")
        # строка состояния: короткая строка из цифр (время/заряд, «%» и «:» OCR часто теряет)
        # в верхней части кадра и выше текста наклейки
        if (label_top is not None and re.fullmatch(r"[\d:%.]{4,9}", compact) and len(digits) >= 4
                and ln["box"][3] < label_top and ln["box"][1] < 0.25 * h):
            kinds.append("status_bar")
        for k in kinds:
            found.add(k)
            proof.append({"kind": k, "text": t})
    return sorted(found), proof
_TOKEN = re.compile(r"(IMEI|IME|INEI|MEI|TNE)", re.I)


def _imei_lines(lines, w, h):
    """Строки с токеном IMEI: сколько цифр прочитано и касается ли строка края кадра."""
    mx, my = w * 0.012, h * 0.008
    out = []
    for ln in lines:
        if not _TOKEN.search(ln["text"].upper()):
            continue
        x0, y0, x1, y1 = ln["box"]
        out.append({"text": ln["text"], "digits": len(imei.normalize(ln["text"])),
                    "touches_edge": x0 < mx or y0 < my or x1 > w - mx or y1 > h - my,
                    "box": ln["box"]})
    return out


# Строки заводской наклейки Samsung, которые узнаются даже при искажённом OCR (модель OCR латинская,
# кириллицу читает двойниками): код модели (SM-A175F…; OCR путает M/N/U) и многоязычные поля
# «Түсі/Цвет/Rangi: …» — слеши OCR сохраняет, даже когда буквы искажены.
_MODEL_CODE = re.compile(r"\bS[MNU]-?[A-Z0-9]{4,}")
_MULTI_FIELD = re.compile(r"[^\W\d_]{2,}\s*/\s*[^\W\d_]{2,}\s*/\s*[^\W\d_]{2,}")


def _label_lines(lines, w, h):
    """Строки, похожие на текст наклейки, и касаются ли они края кадра (признак обрезки)."""
    mx, my = w * 0.012, h * 0.008
    out = []
    for ln in lines:
        t = ln["text"]
        if not (_MODEL_CODE.search(t.upper()) or _MULTI_FIELD.search(t)):
            continue
        x0, y0, x1, y1 = ln["box"]
        out.append({"text": t, "touches_edge": x0 < mx or y0 < my or x1 > w - mx or y1 > h - my})
    return out


def barcode_regions(img: np.ndarray) -> list[dict]:
    """Области, похожие на штрихкод (плотные вертикальные штрихи), даже если декодер не справился.
    Этикетка Samsung содержит 3+ полосы штрихкодов; на лицевой стороне коробки их нет."""
    s = 1200 / max(img.shape[:2])
    im = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    s = min(s, 1.0)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    H, W = g.shape
    out = []
    for rot in (False, True):  # штрихи вертикальные или (этикетка повёрнута) горизонтальные
        gg = cv2.rotate(g, cv2.ROTATE_90_CLOCKWISE) if rot else g
        gx = cv2.convertScaleAbs(cv2.Sobel(gg, cv2.CV_32F, 1, 0, ksize=3))
        gy = cv2.convertScaleAbs(cv2.Sobel(gg, cv2.CV_32F, 0, 1, ksize=3))
        d = cv2.blur(cv2.subtract(gx, gy), (7, 7))
        _, th = cv2.threshold(d, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3)))
        th = cv2.dilate(cv2.erode(th, None, iterations=2), None, iterations=2)
        area = gg.shape[0] * gg.shape[1]
        for c in cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, w, h = cv2.boundingRect(c)
            if w * h < area * 0.0015 or w < 3 * h or h < 6 or cv2.contourArea(c) / (w * h) < 0.6:
                continue
            if rot:  # обратно в координаты неповёрнутого кадра
                x, y, w, h = y, H - x - w, h, w
            edge = x <= 2 or y <= 2 or x + w >= W - 2 or y + h >= H - 2
            out.append({"box": [round(x / s), round(y / s), round((x + w) / s), round((y + h) / s)],
                        "touches_edge": edge})
    return out


# Название модели на верхней грани коробок Samsung: «Galaxy …». Допускаем типичные ошибки OCR (4/A, V/Y, 1/l).
_GALAXY = re.compile(r"G[A4][L1I][A4][XK][YV]")
def box_top(lines: list[dict], full_frame: bool) -> dict:
    """Подсказка для проверяющего (в решении не участвует): на кадре есть надпись «Galaxy»,
    заметно крупнее текста этикетки. Только по уже прочитанным строкам всего кадра — без лишнего OCR.
    Надёжность низкая: на угловых фото с водяным знаком надпись читается редко."""
    if not full_frame:
        return {"found": None, "text": "", "height": 0, "label_text_height": 0}
    digit_h = [ln["box"][3] - ln["box"][1] for ln in lines if len(imei.normalize(ln["text"])) >= 8]
    ref = float(np.median(digit_h)) if digit_h else 0.0
    best = None
    for ln in lines:
        if not _GALAXY.search(ln["text"].upper().replace(" ", "")):
            continue
        hgt = ln["box"][3] - ln["box"][1]
        if ref and hgt < 1.8 * ref:
            continue  # такого же размера, как текст этикетки, — это не надпись на верхней грани
        if not best or hgt > best["height"]:
            best = {"text": ln["text"], "height": hgt}
    return {"found": best is not None, "text": best["text"] if best else "", "height": best["height"] if best else 0,
            "label_text_height": round(ref, 1)}


def _label_box(b, w, h):
    """Прямоугольник вокруг штрихкода IMEI, в котором должна поместиться вся этикетка."""
    x0, y0, x1, y1 = b["box"]
    bw = max(x1 - x0, 10)
    bh = max(y1 - y0, bw * 0.25)  # zxing для 1D часто отдаёт линию, а не прямоугольник
    cy = (y0 + y1) / 2
    return [x0, cy - bh / 2, x0 + bw, cy + bh / 2]


def collect(img: np.ndarray, slot: str) -> dict:
    h, w = img.shape[:2]
    t0 = time.time()
    bars = barcode.decode(img)
    t_bar = time.time() - t0
    bar_imeis = sorted({b["text"] for b in bars if imei.is_valid_imei(b["text"])})

    t1 = time.time()
    lines, mode = [], "full"
    imei_bars = [b for b in bars if b["text"] in bar_imeis]
    if slot == "device" and max(h, w) > 1600 and imei_bars:
        # крупный кадр + найден штрихкод IMEI: читаем только окрестность этикетки (в разы быстрее)
        lines = ocr.read_region(img, _label_box(imei_bars[0], w, h), pad_x=1.6, pad_y=6)
        mode = "crop"
        cands = [c for ln in lines for c in imei.candidates_from_text(ln["text"], "ocr")]
        if not any(c.luhn and (c.has_token or c.digits in bar_imeis) for c in cands):
            lines, mode = ocr.read(img), "crop+full"
    else:
        lines = ocr.read(img)
    t_ocr = time.time() - t1

    cands = []
    for ln in lines:
        cands += imei.candidates_from_text(ln["text"], "ocr")
    text_all = " ".join(ln["text"] for ln in lines).upper()
    # верх наклейки: самая верхняя строка со словами наклейки, токеном IMEI или длинным номером
    label_ys = [ln["box"][1] for ln in lines
                if any(k in ln["text"].upper() for k in _LABEL_WORDS) or _TOKEN.search(ln["text"])
                or len(imei.normalize(ln["text"])) >= 14]
    ui_hits, ui_proof = ui_signals(lines, img, min(label_ys) if label_ys else None)
    mx = w * 0.012
    # строки с длинной цепочкой цифр, упирающиеся в левый/правый край — признак обрезки
    cut_lines = [ln["text"] for ln in lines
                 if len(imei.normalize(ln["text"])) >= 8 and (ln["box"][0] < mx or ln["box"][2] > w - mx)]
    return {
        "version": EVIDENCE_VERSION,
        "slot": slot,
        "size": [w, h],
        "barcodes": bars,
        "barcode_imeis": bar_imeis,
        "ocr_mode": mode,
        "ocr_lines": lines,
        "candidates": [c.to_dict() for c in cands],
        "imei_lines": _imei_lines(lines, w, h),
        "label_lines": _label_lines(lines, w, h),
        "cut_lines": cut_lines,
        "barcode_regions": barcode_regions(img),
        "box_top": box_top(lines, full_frame=(mode != "crop")) if slot == "device" else None,
        "dhash": imaging.dhash(img),
        "label_words": sorted({k for k in _LABEL_WORDS if k in text_all}),
        "ui_hits": ui_hits,
        "ui_proof": ui_proof,
        "luminance": imaging.luminance_stats(imaging.resize_max(img, 800)),
        "timing": {"barcode": round(t_bar, 2), "ocr": round(t_ocr, 2)},
    }
