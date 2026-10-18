"""IMEI: проверка Луна и извлечение кандидатов из распознанного текста."""
import re
from dataclasses import dataclass, asdict

# Кириллические двойники латинских букв, которые OCR путает
_LOOKALIKE = str.maketrans("АВЕКМНОРСТХІМЕІ", "ABEKMHOPCTXIMEI")
# Токен «IMEI» с типичными ошибками OCR: IME1, INEI, TNE, MEI ...
_TOKEN = re.compile(r"(IMEI|IME|INEI|MEI|NEI|INE|TNE|IHEI|1MEI|LMEI)")
# Цепочка цифр, допускаем одиночные пробелы/точки внутри
_RUN = re.compile(r"\d(?:[ .]?\d){13,}")


def luhn_ok(s: str) -> bool:
    if not s.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(s)):
        d = int(ch)
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def is_valid_imei(s: str) -> bool:
    return len(s) == 15 and luhn_ok(s)


def normalize(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b))
    return sum(x != y for x, y in zip(a, b))


def same_serial(a: str, b: str) -> bool:
    """У двухсимочных Samsung IMEI1 и IMEI2 обычно совпадает серийная часть (цифры 9–14).
    Используется только чтобы НЕ объявлять несовпадение, когда продавец ввёл IMEI2."""
    return len(a) == len(b) == 15 and a[8:14] == b[8:14]


@dataclass
class Candidate:
    digits: str
    luhn: bool
    has_token: bool  # перед цифрами стоит «IMEI»-подобный токен
    source: str      # ocr | ocr_refine | vlm | barcode
    text: str = ""

    def to_dict(self):
        return asdict(self)


def candidates_from_text(text: str, source: str) -> list[Candidate]:
    """Все 15-значные кандидаты из строки. Хеш водяного знака (hex) редко даёт
    15 цифр подряд, а если даёт — его отсекают Луна и сверка с введённым IMEI."""
    out: list[Candidate] = []
    norm = (text or "").upper().translate(_LOOKALIKE)
    for m in _RUN.finditer(norm):
        digits = normalize(m.group(0))
        ctx = norm[max(0, m.start() - 8):m.start()]
        has_token = bool(_TOKEN.search(ctx))
        windows = set()
        if len(digits) == 15:
            windows.add(digits)
        elif len(digits) == 16 and has_token and digits[0] in "12":
            windows.add(digits[1:])  # «IMEI1352...» — индекс слипся с номером
        elif len(digits) > 15:
            # длинная цепочка: берём только окна, проходящие Луна
            windows.update(digits[i:i + 15] for i in range(len(digits) - 14)
                           if luhn_ok(digits[i:i + 15]))
        elif len(digits) == 14:
            # недочитанный номер: Луна не пройдёт, но полезно как «почти прочитано»
            out.append(Candidate(digits, False, has_token, source, text))
        for w in windows:
            out.append(Candidate(w, luhn_ok(w), has_token, source, text))
    return out
