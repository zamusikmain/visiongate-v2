"""Оркестрация: быстрая фаза (≤10 с) и фоновая VLM-фаза.
IMEI можно не вводить: тогда опорный номер берётся с фото (decision.pick_anchor) и сверяются только фото."""
import time

from . import decision, evidence, imaging, imei, vlm

SLOTS = ("device", "scan")


def _decide(ev: dict, entered: str, settings: dict, phase: str, vr: dict | None = None):
    """Возвращает (slots, cross, final, imei, source). source: entered | photo | none."""
    def slot(s, target, mode):
        return decision.decide_slot(ev[s], target, s, vr[s] if vr else None, mode=mode)
    duplicate = decision.is_duplicate(ev["device"], ev["scan"])  # одно фото в обоих слотах
    if entered:
        if imei.is_valid_imei(entered):
            slots = {s: slot(s, entered, "entered") for s in SLOTS}
            cross = decision.cross_check(slots, entered)
        else:
            slots = {s: decision.invalid_entry_slot(ev[s]) for s in SLOTS}
            cross = None
        final = decision.with_duplicate(decision.combine(slots, entered, phase, settings, cross), duplicate)
        return slots, cross, final, entered, "entered"
    anchor = decision.pick_anchor(ev["device"], ev["scan"])
    slots = {s: slot(s, anchor, "photo") for s in SLOTS}
    cross = decision.cross_check(slots, anchor, mode="photo")
    final = decision.with_duplicate(decision.combine(slots, anchor, phase, settings, cross, mode="photo"), duplicate)
    return slots, cross, final, anchor, "photo" if anchor else "none"


def fast_check(images: dict, entered: str, settings: dict, evidences: dict | None = None) -> dict:
    """images: {"device": ndarray, "scan": ndarray}. entered — введённый IMEI или "" (сверка только по фото).
    evidences — готовые признаки (для прогона датасета)."""
    t = time.time()
    entered = imei.normalize(entered)
    ev = evidences or {s: evidence.collect(images[s], s) for s in SLOTS}
    slots, cross, final, num, source = _decide(ev, entered, settings, "fast")
    return {"entered": entered, "imei": num, "imei_source": source, "evidence": ev, "slots": slots, "cross": cross,
            "final": final, "needs_vlm": decision.needs_vlm(final, settings), "fast_seconds": round(time.time() - t, 2)}


def vlm_check(images: dict, result: dict, settings: dict, vlm_results: dict | None = None,
              raw: dict | None = None) -> dict:
    """Дополняет результат быстрой фазы ответами VLM и пересчитывает итог.
    raw — исходные байты фото (для кэша ответов VLM)."""
    t = time.time()
    vr = vlm_results or {s: vlm.check(images[s], settings, raw=(raw or {}).get(s)) for s in SLOTS}
    slots, cross, final, num, source = _decide(result["evidence"], result["entered"], settings, "final", vr)
    return dict(result, slots=slots, cross=cross, final=final, imei=num, imei_source=source, vlm=vr,
                needs_vlm=False, vlm_seconds=round(time.time() - t, 1))


def load(data: bytes):
    return imaging.load_bgr(data)
