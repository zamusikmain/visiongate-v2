"""Правила решения. Принцип: отклоняем только при явных признаках, при сомнении — ручная проверка.
Ни одно правило не завязано на конкретные файлы датасета: только IMEI-логика, наличие/отсутствие
признаков и общие свойства этикетки Samsung (IMEI1 + IMEI2 со штрихкодами).
Все тексты — парами RU/EN: поле message (рус.) и message_en."""
from . import imei

# Порядок = приоритет причины в итоговом статусе
REASONS = {
    "INVALID_IMEI": ("Введённый IMEI не проходит проверку контрольной цифры (алгоритм Луна). Проверьте номер.",
                     "The entered IMEI fails the check digit test (Luhn algorithm). Please check the number."),
    "PHOTO_OF_SCREEN": ("Похоже на фото экрана другого устройства. Сфотографируйте саму коробку.",
                        "Looks like a photo of another device's screen. Please photograph the box itself."),
    "IMEI_MISMATCH": ("IMEI на фото не совпадает с введённым.",
                      "The IMEI in the photo does not match the entered one."),
    "NO_SERIAL": ("На фото нет этикетки с IMEI и штрихкодом. Сфотографируйте боковую этикетку коробки.",
                  "No label with IMEI and barcode in the photo. Please photograph the side label of the box."),
    "CROPPED": ("Этикетка обрезана: блок IMEI1 и IMEI2 со штрихкодами должен целиком помещаться в кадр.",
                "The label is cropped: the IMEI1 and IMEI2 block with barcodes must be fully in the frame."),
    "BLURRY_DARK_UNREADABLE": ("IMEI на этикетке размыт, слишком тёмный или нечитаем. Переснимите ближе, "
                               "при хорошем освещении и без бликов.",
                               "The IMEI on the label is blurry, too dark or unreadable. Retake the photo closer, "
                               "in good light and without glare."),
}
STATUS = {
    "APPROVED": ("Одобрено", "Approved"),
    "REJECTED": ("Отклонено", "Rejected"),
    "REVIEW": ("На ручную проверку", "Manual review"),
    "PRELIMINARY": ("Предварительно одобрено — идёт проверка на фото экрана",
                    "Preliminarily approved — screen-photo check in progress"),
    "PROCESSING": ("Проверяется", "Processing"),
}
SLOT_NAME = {"device": ("Фото коробки", "Box photo"), "scan": ("Скан этикетки", "Label scan")}
# совместимость со старыми импортами
STATUS_RU = {k: v[0] for k, v in STATUS.items()}
SLOT_RU = {k: v[0] for k, v in SLOT_NAME.items()}

MSG = {
    "ok": ("IMEI распознан и совпадает с введённым.", "IMEI recognised and matches the entered one."),
    "mismatch": ("IMEI на фото ({read}) не совпадает с введённым ({entered}).",
                 "The IMEI in the photo ({read}) does not match the entered one ({entered})."),
    "ui_review": ("IMEI читается, но на фото есть элементы интерфейса телефона ({ui}) — возможна съёмка экрана.",
                  "The IMEI is readable, but phone UI elements are visible ({ui}) — possibly a photo of a screen."),
    "pair_review": ("IMEI читается, но не удалось подтвердить, что блок IMEI1 + IMEI2 со штрихкодами виден целиком.",
                    "The IMEI is readable, but it could not be confirmed that the IMEI1 + IMEI2 block is fully visible."),
    "barcode_review": ("Штрихкод совпадает с введённым IMEI, но цифры на этикетке не читаются уверенно — "
                       "нужна проверка человеком.",
                       "The barcode matches the entered IMEI, but the digits are not clearly readable — "
                       "a human check is needed."),
    "sibling_review": ("На фото прочитан второй IMEI того же устройства, а введённый номер не найден — "
                       "нужна проверка человеком.",
                       "The other IMEI of the same device was read, but the entered number was not found — "
                       "a human check is needed."),
    "sibling_ok": ("Здесь прочитан второй IMEI того же устройства, а введённый номер подтверждён на другом фото.",
                   "The other IMEI of the same device was read here; the entered number is confirmed on the other photo."),
    "dark": (" Кадр слишком тёмный.", " The image is too dark."),
    "vlm_failed": ("Проверка на фото экрана не выполнена ({err}) — нужна проверка человеком.",
                   "The screen-photo check failed ({err}) — a human check is needed."),
    "vlm_screen": ("Модель подозревает фото экрана другого устройства — нужна проверка человеком.",
                   "The model suspects a photo of another device's screen — a human check is needed."),
    "invalid_entry": ("Не проверялось: введён некорректный IMEI.", "Not checked: the entered IMEI is invalid."),
    "invalid_seen": (" На фото распознано: {read}.", " Recognised in the photo: {read}."),
    "cross_mismatch": ("IMEI на фото коробки ({dev}) и на скане этикетки ({scan}) не совпадают — "
                       "похоже, это разные устройства.",
                       "The IMEI on the box photo ({dev}) and on the label scan ({scan}) do not match — "
                       "they appear to be different devices."),
    "final_ok": ("IMEI распознан на обоих фото и совпадает с введённым.",
                 "IMEI recognised on both photos and matches the entered one."),
    "final_prelim": ("IMEI распознан на обоих фото и совпадает с введённым. Идёт фоновая проверка на фото экрана — "
                     "итоговый статус появится через несколько минут.",
                     "IMEI recognised on both photos and matches the entered one. A background screen-photo check "
                     "is running — the final status will appear in a few minutes."),
    "final_no_vlm": ("IMEI совпадает, но проверка на фото экрана выключена — нужна проверка человеком.",
                     "The IMEI matches, but the screen-photo check is disabled — a human check is needed."),
    # --- режим без введённого IMEI: сверка только между фото (опорный номер — с фото) ---
    "ok_photo": ("IMEI {entered} распознан и совпадает с IMEI на другом фото.",
                 "IMEI {entered} recognised and matches the IMEI on the other photo."),
    "mismatch_photo": ("На этом фото прочитан IMEI {read}, а на другом фото — {entered}.",
                       "This photo shows IMEI {read}, while the other photo shows {entered}."),
    "barcode_review_photo": ("Штрихкод совпадает с IMEI на другом фото, но цифры на этикетке не читаются уверенно — "
                             "нужна проверка человеком.",
                             "The barcode matches the IMEI on the other photo, but the digits are not clearly readable — "
                             "a human check is needed."),
    "sibling_review_photo": ("Здесь прочитан второй IMEI того же устройства, но совпадение не подтверждено текстом — "
                             "нужна проверка человеком.",
                             "The other IMEI of the same device was read here, but the match is not confirmed by text — "
                             "a human check is needed."),
    "sibling_ok_photo": ("Здесь прочитан второй IMEI того же устройства (IMEI1/IMEI2) — это одно устройство.",
                         "The other IMEI of the same device (IMEI1/IMEI2) was read here — it is the same device."),
    "final_ok_photo": ("IMEI {imei} распознан на обоих фото, номера совпадают.",
                       "IMEI {imei} recognised on both photos, the numbers match."),
    "final_prelim_photo": ("IMEI {imei} распознан на обоих фото, номера совпадают. Идёт фоновая проверка на фото экрана — "
                           "итоговый статус появится через несколько минут.",
                           "IMEI {imei} recognised on both photos, the numbers match. A background screen-photo check "
                           "is running — the final status will appear in a few minutes."),
    "final_no_vlm_photo": ("IMEI {imei} совпадает на обоих фото, но проверка на фото экрана выключена — "
                           "нужна проверка человеком.",
                           "IMEI {imei} matches on both photos, but the screen-photo check is disabled — "
                           "a human check is needed."),
}
_LABEL_WORDS = {"IMEI", "SM-", "EID"}
DARK_MEAN = 45  # средняя яркость 0–255 без зелёного текста: ниже — кадр явно тёмный


def _t(key, **p):
    ru, en = MSG[key] if key in MSG else REASONS[key]
    return ru.format(**p), en.format(**p)


def _slot(status, reason=None, key=None, extra_key=None, params=None, **extra):
    """key — ключ MSG; без key берётся текст причины."""
    params = params or {}
    ru, en = _t(key or reason, **params) if (key or reason) else ("", "")
    if extra_key:
        r2, e2 = _t(extra_key, **params)
        ru, en = ru + r2, en + e2
    d = {"status": status, "reason": reason, "message": ru, "message_en": en, "msg_key": key or reason}
    d.update(extra)
    return d


def _set_msg(d, key, **p):
    d["message"], d["message_en"] = _t(key, **p)
    d["msg_key"] = key


def _cut_evidence(ev) -> bool:
    """Строка «IMEI…» или длинная цепочка цифр упирается в край кадра.
    Края областей штрихкодов не используем: по правилам правая часть этикетки (дублирующий блок,
    EID) может быть обрезана, и на одобренных фото такие полосы часто уходят за край."""
    return bool(ev.get("cut_lines")) or any(l["touches_edge"] for l in ev.get("imei_lines", []))


def _pair_complete(ev, matched: str) -> bool:
    """Виден ли второй IMEI того же блока: либо прочитан полностью (тот же серийный номер),
    либо есть строка «IMEI…» с 15+ цифрами целиком внутри кадра, отличная от первого номера."""
    for c in ev["candidates"]:
        if c["luhn"] and c["digits"] != matched and imei.same_serial(c["digits"], matched):
            return True
    for ln in ev.get("imei_lines", []):
        d = imei.normalize(ln["text"])
        if ln["touches_edge"] or len(d) < 15:
            continue
        if imei.hamming(d[-15:], matched) > 3:
            return True
    return False


def slot_imeis(ev: dict) -> tuple[set, set]:
    """(все номера с Луна, надёжно прочитанные: штрихкод или текст, прочитанный дважды).
    Одиночное чтение даже с токеном «IMEI» сюда не входит: OCR иногда склеивает цифры так,
    что Луна случайно сходится (1 шанс из 10)."""
    text_luhn, counts = set(), {}
    for c in ev["candidates"]:
        if c["luhn"]:
            text_luhn.add(c["digits"])
            counts[c["digits"]] = counts.get(c["digits"], 0) + 1
    bars = set(ev["barcode_imeis"])
    return bars | text_luhn, bars | {d for d, n in counts.items() if n >= 2}


def _shown(all_imeis: set, reliable: set, entered: str) -> list:
    """Номера для показа: надёжные + любые, совпадающие с введённым или «соседние» к нему."""
    return sorted(reliable | {x for x in all_imeis if x == entered or imei.same_serial(x, entered)})


def _k(key: str, mode: str) -> str:
    """Ключ сообщения с учётом режима: в режиме «по фото» — вариант *_photo, если он есть."""
    return f"{key}_photo" if mode == "photo" and f"{key}_photo" in MSG else key


def pick_anchor(ev_dev: dict, ev_scan: dict) -> str:
    """Опорный IMEI, когда пользователь его не ввёл. Приоритет:
    1) номер, прочитанный на обоих фото (случайно совпасть мусор на двух фото не может);
    2) IMEI1/IMEI2 одного устройства на разных фото (та же серийная часть) — берём надёжный;
    3) надёжно прочитанный номер на одном из фото (штрихкод или текст дважды).
    Нет ничего — пустая строка: на фото не удалось прочитать ни одного IMEI."""
    all_d, rel_d = slot_imeis(ev_dev)
    all_s, rel_s = slot_imeis(ev_scan)
    bars = set(ev_dev["barcode_imeis"]) | set(ev_scan["barcode_imeis"])
    common = all_d & all_s
    if common:
        return sorted(common, key=lambda x: (x not in bars, x not in rel_d | rel_s, x))[0]
    for x in sorted(rel_d | rel_s, key=lambda x: (x not in bars, x)):
        other = all_s if x in all_d else all_d
        if any(imei.same_serial(x, y) for y in other):
            return x
    rel = sorted(rel_d | rel_s, key=lambda x: (x not in bars, x))
    return rel[0] if rel else ""


def decide_slot(ev: dict, entered: str, slot: str, vlm: dict | None = None, mode: str = "entered") -> dict:
    """Решение по слоту. vlm=None — быстрая фаза (VLM ещё не запускалась).
    mode: entered — сверка с введённым IMEI; photo — entered здесь опорный номер с фото (pick_anchor)."""
    k = lambda key: _k(key, mode)  # noqa: E731
    cands = ev["candidates"]
    text_luhn = {c["digits"] for c in cands if c["luhn"]}
    bars = set(ev["barcode_imeis"])
    all_imeis, reliable = slot_imeis(ev)
    match_text = entered in text_luhn
    match_bar = entered in bars
    # «соседний» IMEI того же устройства: любой номер с Луна и той же серийной частью
    # (случайная строка, прошедшая и Луна, и совпадение 6 цифр серийника, практически невозможна)
    sibling = any(x != entered and imei.same_serial(entered, x) for x in all_imeis)
    # чужой IMEI для отказа — только надёжно прочитанный (штрихкод или текст дважды)
    foreign = sorted(x for x in reliable if x != entered and not imei.same_serial(entered, x)
                     and imei.hamming(entered, x) > 2)
    label_present = bool(bars) or bool(_LABEL_WORDS & set(ev["label_words"])) \
        or len(ev.get("barcode_regions", [])) >= 2 or bool(ev.get("imei_lines"))
    dark = ev["luminance"]["mean"] < DARK_MEAN
    ui = ev.get("ui_hits", [])
    info = {"read_imeis": _shown(all_imeis, reliable, entered), "reliable_imeis": sorted(reliable),
            "all_imeis": sorted(all_imeis), "barcode_imeis": sorted(bars),
            "matched": match_text or match_bar,
            "matched_by": [s for s, ok in (("text", match_text), ("barcode", match_bar)) if ok]}

    # --- быстрая фаза ---
    if not match_text and not match_bar and foreign and not sibling:
        fast = _slot("reject", "IMEI_MISMATCH", k("mismatch"), params={"read": ", ".join(foreign), "entered": entered},
                     **info)
    elif match_text:
        if ui:
            fast = _slot("review", None, "ui_review", params={"ui": ", ".join(ui)}, suspected="PHOTO_OF_SCREEN",
                         **info)
        elif slot == "scan" and not _pair_complete(ev, entered):
            # IMEI прочитан, но второй номер блока не подтверждён: обрезка или OCR не дочитал — не отклоняем
            fast = _slot("review", None, "pair_review", suspected="CROPPED", **info)
        else:
            fast = _slot("ok", None, k("ok"), params={"entered": entered}, **info)
    elif match_bar:
        fast = _slot("review", None, k("barcode_review"), suspected="BLURRY_DARK_UNREADABLE", **info)
    elif sibling:
        fast = _slot("review", None, k("sibling_review"), sibling_only=True, **info)
    elif ui:
        fast = _slot("reject", "PHOTO_OF_SCREEN", **info)
    elif label_present:
        # на фото коробки этикетка — малая часть сцены, «обрезку» по краю кадра там не ищем
        if slot == "scan" and _cut_evidence(ev):
            fast = _slot("reject", "CROPPED", **info)
        else:
            fast = _slot("reject", "BLURRY_DARK_UNREADABLE", extra_key="dark" if dark else None, **info)
    else:
        fast = _slot("reject", "NO_SERIAL", **info)

    if vlm is None:
        return fast

    # --- фоновая фаза: учитываем VLM ---
    out = dict(fast, vlm=vlm)
    if not vlm.get("ok"):
        if fast["status"] == "ok":
            out["status"] = "review"
            _set_msg(out, "vlm_failed", err=vlm.get("error") or "no answer")
        return out
    if vlm["screen"]:
        if fast["status"] == "reject":
            out["reason"] = "PHOTO_OF_SCREEN"
            _set_msg(out, "PHOTO_OF_SCREEN")
        else:
            out.update(status="review", suspected="PHOTO_OF_SCREEN")
            _set_msg(out, "vlm_screen")
    # «Виден верх коробки» в решении НЕ участвует: VLM отвечала «да» почти на любое фото, а OCR-надпись
    # «Galaxy» на угловых фото с водяным знаком находилась на 1 из 5 одобренных — оба признака ненадёжны.
    # Признак из OCR показывается проверяющему как подсказка (evidence.box_top).
    return out


def cross_check(slots: dict, entered: str, mode: str = "entered") -> dict | None:
    """Сверка IMEI между фото коробки и сканом. Меняет slots на месте.
    Возвращает описание несовпадения или None."""
    d, s = slots.get("device"), slots.get("scan")
    if not d or not s or "all_imeis" not in d or "all_imeis" not in s:
        return None
    def related(a, b):
        return any(x == y or imei.same_serial(x, y) for x in a for y in b)
    dev_conf, scan_conf = set(d.get("reliable_imeis", [])), set(s.get("reliable_imeis", []))
    if dev_conf and scan_conf and not related(set(d["all_imeis"]), set(s["all_imeis"])):
        return {"device": sorted(dev_conf), "scan": sorted(scan_conf)}
    # на одном фото подтверждён введённый номер, на другом — второй IMEI того же устройства → это одно устройство
    for a, b in ((d, s), (s, d)):
        if a.get("sibling_only") and a["status"] == "review" and b["status"] == "ok" \
                and "text" in b.get("matched_by", []) and related(set(a["all_imeis"]), {entered}):
            a["status"] = "ok"
            _set_msg(a, _k("sibling_ok", mode))
    return None


def invalid_entry_slot(ev: dict) -> dict:
    """Введён номер с ошибкой: фото не сверяем, но показываем, что на нём прочитано, — продавцу проще исправить."""
    all_imeis, reliable = slot_imeis(ev)
    reads = sorted(reliable)
    return _slot("reject", "INVALID_IMEI", "invalid_entry", extra_key="invalid_seen" if reads else None,
                 params={"read": ", ".join(reads)}, read_imeis=reads, reliable_imeis=reads, all_imeis=sorted(all_imeis),
                 barcode_imeis=sorted(ev["barcode_imeis"]), matched=False, matched_by=[])


def _final(status, reasons, key=None, ru="", en="", **params):
    if key:
        ru, en = _t(key, **params)
    return {"status": status, "reasons": reasons, "message": ru, "message_en": en}


def combine(slots: dict, entered: str, phase: str, settings: dict, cross: dict | None = None,
            mode: str = "entered") -> dict:
    """Итог по двум слотам. phase: fast | final. cross — результат cross_check.
    mode=photo: entered — опорный IMEI с фото (может быть пустым), проверки Луна по вводу нет."""
    if mode == "entered" and not imei.is_valid_imei(entered):
        return _final("REJECTED", ["INVALID_IMEI"], "INVALID_IMEI")
    st = [s["status"] for s in slots.values()]
    reasons = {s["reason"] for s in slots.values() if s["status"] == "reject" and s["reason"]}
    if cross:
        reasons.add("IMEI_MISMATCH")
    reasons = sorted(reasons, key=list(REASONS).index)
    def join(which):
        ru = " ".join(f"{SLOT_NAME[k][0]}: {v['message']}" for k, v in slots.items() if v["status"] == which)
        en = " ".join(f"{SLOT_NAME[k][1]}: {v['message_en']}" for k, v in slots.items() if v["status"] == which)
        return ru, en
    if "reject" in st or cross:
        ru, en = join("reject")
        if cross:
            cr, ce = _t("cross_mismatch", dev=", ".join(cross["device"]), scan=", ".join(cross["scan"]))
            ru, en = (cr + " " + ru).strip(), (ce + " " + en).strip()
        return _final("REJECTED", reasons, ru=ru, en=en)
    if "review" in st:
        ru, en = join("review")
        return _final("REVIEW", [], ru=ru, en=en)
    k = lambda key: _k(key, mode)  # noqa: E731
    if phase == "fast":
        if settings.get("vlm_provider", "off") != "off":
            return _final("PRELIMINARY", [], k("final_prelim"), imei=entered)
        if settings.get("require_screen_check", True):
            return _final("REVIEW", [], k("final_no_vlm"), imei=entered)
    return _final("APPROVED", [], k("final_ok"), imei=entered)


def needs_vlm(fast_final: dict, settings: dict) -> bool:
    if settings.get("vlm_provider", "off") == "off":
        return False
    if fast_final["status"] == "REJECTED":
        return bool(settings.get("vlm_for_rejected")) and fast_final["reasons"] != ["INVALID_IMEI"]
    return True
