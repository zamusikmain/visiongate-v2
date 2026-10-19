"""Загрузка изображения с учётом EXIF-поворота и вспомогательные преобразования."""
import io
import cv2
import numpy as np
from PIL import Image, ImageOps


def load_bgr(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def resize_max(img: np.ndarray, side: int) -> np.ndarray:
    s = side / max(img.shape[:2])
    if s >= 1:
        return img
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)


def to_jpeg(img: np.ndarray, quality: int = 90) -> bytes:
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


def dhash(img: np.ndarray) -> str:
    """Перцептивный difference-hash 64 бита (hex). Устойчив к пересжатию, изменению размера
    и тонкому тексту водяного знака: кадр сводится к 9×8 пикселям яркости."""
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def dhash_distance(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def green_watermark_mask(img: np.ndarray) -> np.ndarray:
    """Маска ярко-зелёного текста водяного знака (дата/GPS/хеш внизу)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (40, 120, 120), (85, 255, 255))


def luminance_stats(img: np.ndarray) -> dict:
    """Средняя яркость и контраст без зелёного текста водяного знака.
    Используется только для пояснения причины («слишком темно»), не для решения о резкости."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    keep = green_watermark_mask(img) == 0
    vals = gray[keep] if keep.any() else gray.ravel()
    return {"mean": float(vals.mean()), "std": float(vals.std())}
