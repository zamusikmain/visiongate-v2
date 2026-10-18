"""OCR на CPU: RapidOCR (PP-OCRv3 в ONNX). Свой конвейер поверх его детектора и распознавателя:
детекция на уменьшенной копии → отброс диагональных строк водяного знака → распознавание
кропов из полноразмерного кадра без классификатора ориентации."""
import math
import threading

import cv2
import numpy as np

DET_MAX_SIDE = 1600   # детекция: длинная сторона не больше (крупный кадр уменьшаем)
DET_MIN_SIDE = 736    # мелкий кадр увеличиваем до этой короткой стороны (как в PP-OCR по умолчанию)
WATERMARK_ANGLES = (20, 70)  # диагональный хеш ИБ; текст этикетки — около 0° или 90°
TEXT_SCORE = 0.5
USE_CLS = True  # классификатор 0/180°: строки, снятые «вверх ногами»

_engine = None
_lock = threading.Lock()


def _get():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
        # размер задаём сами (resize перед детекцией), детектор не должен масштабировать повторно
        resize_op = _engine.text_detector.preprocess_op[0]  # DetResizeForTest
        resize_op.limit_type = "max"
        resize_op.limit_side_len = 100000
    return _engine


def _det_scale(h: int, w: int) -> float:
    if max(h, w) > DET_MAX_SIDE:
        return DET_MAX_SIDE / max(h, w)
    if min(h, w) < DET_MIN_SIDE:
        return DET_MIN_SIDE / min(h, w)
    return 1.0


def _angle(box: np.ndarray) -> float:
    """Угол длинной стороны рамки к горизонтали, 0–90°."""
    a, b, c = box[0], box[1], box[3]
    v = b - a if np.linalg.norm(b - a) >= np.linalg.norm(c - a) else c - a
    ang = abs(math.degrees(math.atan2(v[1], v[0]))) % 180
    return min(ang, 180 - ang)


def read(img: np.ndarray) -> list[dict]:
    h, w = img.shape[:2]
    s = _det_scale(h, w)
    small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC) \
        if s != 1 else img
    with _lock:  # движок не потокобезопасен
        eng = _get()
        boxes, _ = eng.text_detector(small)
        if boxes is None or len(boxes) == 0:
            return []
        boxes = [b / s for b in eng.sorted_boxes(boxes)]
        keep = [b.astype(np.float32) for b in boxes
                if not (WATERMARK_ANGLES[0] < _angle(b) < WATERMARK_ANGLES[1])]
        if not keep:
            return []
        crops = eng.get_crop_img_list(img, keep)  # кропы всегда из исходного кадра
        if USE_CLS:
            crops, _, _ = eng.text_cls(crops)
        rec, _ = eng.text_recognizer(crops)
    out = []
    for b, (text, score) in zip(keep, rec):
        if float(score) < TEXT_SCORE or not text.strip():
            continue
        x0, y0 = b.min(0)
        x1, y1 = b.max(0)
        out.append({"text": text, "score": round(float(score), 3),
                    "box": [round(float(x0)), round(float(y0)), round(float(x1)), round(float(y1))]})
    return out


def crop(img: np.ndarray, box, pad_x: float, pad_y: float) -> tuple[np.ndarray, int, int]:
    """Вырезает область вокруг box с полями (в долях размера box). Возвращает кроп и смещение."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    h, w = img.shape[:2]
    xs, ys = max(0, int(x0 - bw * pad_x)), max(0, int(y0 - bh * pad_y))
    xe, ye = min(w, int(x1 + bw * pad_x)), min(h, int(y1 + bh * pad_y))
    return img[ys:ye, xs:xe], xs, ys


def read_region(img: np.ndarray, box, pad_x: float, pad_y: float) -> list[dict]:
    c, ox, oy = crop(img, box, pad_x, pad_y)
    if c.size == 0:
        return []
    lines = read(c)
    for ln in lines:
        b = ln["box"]
        ln["box"] = [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy]
    return lines
