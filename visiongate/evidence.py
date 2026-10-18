"""Быстрая фаза: сбор признаков по одному фото (штрихкоды, OCR, яркость).
Признаки не зависят от введённого IMEI — решение принимает decision.py."""
import re
import time

import cv2
import numpy as np

from . import barcode, imaging, imei, ocr

EVIDENCE_VERSION = 6

_LABEL_WORDS = ("IMEI", "SM-", "EID", "S/N", "MODEL", "МОДЕЛЬ", "ЦВЕТ", "COLOR", "MADE IN",
                "ИЗГОТОВ", "СТРАНА", "РАЗМЕР", "ВЕС")
# Признаки интерфейса телефона на снимке экрана — по ТИПАМ, без привязки к конкретным номерам/странам.
# На этикетке Samsung ничего из этого не печатается. Сработавший тип — только повод для ручной проверки.
_UI_PATTERNS = {
    "номер телефона": re.compile(r"\+\s?\d{1,3}[\s(.-]{0,2}\d{2,4}[\s).-]{0,2}\d{2,4}[\s.-]?\d{2,4}"),
    "заряд батареи": re.compile(r"\b\d{1,3}\s?%"),
    "интерфейс мессенджера": re.compile(
        r"ОТВЕТИТЬ|ПЕРЕСЛАТЬ|ТОЛЬКО ЧТО|В СЕТИ|БЫЛ\(А\)|СООБЩЕНИ|ГАЛЕРЕ|ФОТО\b|"   # ru
        r"ЖАУАП|ХАБАРЛАМА|"                                                        # kk
        r"JAVOB|XABAR|"                                                            # uz
        r"\bREPLY\b|FORWARD|ONLINE|LAST SEEN|TYPING|MESSAGE|GALLERY|\bPHOTO\b"),   # en
}
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
        "cut_lines": cut_lines,
        "barcode_regions": barcode_regions(img),
        "box_top": box_top(lines, full_frame=(mode != "crop")) if slot == "device" else None,
        "label_words": sorted({k for k in _LABEL_WORDS if k in text_all}),
        "ui_hits": sorted(name for name, p in _UI_PATTERNS.items() if p.search(text_all)),
        "luminance": imaging.luminance_stats(imaging.resize_max(img, 800)),
        "timing": {"barcode": round(t_bar, 2), "ocr": round(t_ocr, 2)},
    }
