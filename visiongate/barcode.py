"""Декодирование штрихкодов zxing-cpp: несколько масштабов и бинаризаторов."""
import cv2
import numpy as np
import zxingcpp

_LINEAR = zxingcpp.BarcodeFormat.Code128 | zxingcpp.BarcodeFormat.EAN13 | zxingcpp.BarcodeFormat.Code39
_MAX_PIXELS = 40e6


def decode(img: np.ndarray) -> list[dict]:
    """Возвращает уникальные штрихкоды: текст, формат, прямоугольник в координатах исходника."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    found: dict[str, dict] = {}
    # маленькие кадры дополнительно увеличиваем: на 540 px полоса ~1 px
    scales = (1, 2, 3) if max(gray.shape) < 2000 else (1, 2)
    for scale in scales:
        im = gray if scale == 1 else cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        if im.size > _MAX_PIXELS:
            continue
        for binarizer in (zxingcpp.Binarizer.LocalAverage, zxingcpp.Binarizer.GlobalHistogram):
            for r in zxingcpp.read_barcodes(im, formats=_LINEAR, try_rotate=True, binarizer=binarizer):
                if not r.valid or r.text in found:
                    continue
                p = r.position
                pts = np.array([[p.top_left.x, p.top_left.y], [p.top_right.x, p.top_right.y],
                                [p.bottom_right.x, p.bottom_right.y], [p.bottom_left.x, p.bottom_left.y]],
                               float) / scale
                x0, y0 = pts.min(0)
                x1, y1 = pts.max(0)
                found[r.text] = {"text": r.text, "format": str(r.format).split(".")[-1],
                                 "box": [round(x0), round(y0), round(x1), round(y1)]}
    return list(found.values())
