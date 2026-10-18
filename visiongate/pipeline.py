"""Оркестрация: быстрая фаза (≤10 с) и фоновая VLM-фаза."""
import time

from . import decision, evidence, imaging, imei, vlm

SLOTS = ("device", "scan")


def _decide(ev: dict, entered: str, settings: dict, phase: str, vr: dict | None = None):
    if imei.is_valid_imei(entered):
        slots = {s: decision.decide_slot(ev[s], entered, s, vr[s] if vr else None) for s in SLOTS}
        cross = decision.cross_check(slots, entered)
    else:
        slots = {s: decision.invalid_entry_slot(ev[s]) for s in SLOTS}
        cross = None
    return slots, cross, decision.combine(slots, entered, phase, settings, cross)


def fast_check(images: dict, entered: str, settings: dict, evidences: dict | None = None) -> dict:
    """images: {"device": ndarray, "scan": ndarray}. evidences — готовые признаки (для прогона датасета)."""
    t = time.time()
    entered = imei.normalize(entered)
    ev = evidences or {s: evidence.collect(images[s], s) for s in SLOTS}
    slots, cross, final = _decide(ev, entered, settings, "fast")
    return {"entered": entered, "evidence": ev, "slots": slots, "cross": cross, "final": final,
            "needs_vlm": decision.needs_vlm(final, settings), "fast_seconds": round(time.time() - t, 2)}


def vlm_check(images: dict, result: dict, settings: dict, vlm_results: dict | None = None,
              raw: dict | None = None) -> dict:
    """Дополняет результат быстрой фазы ответами VLM и пересчитывает итог.
    raw — исходные байты фото (для кэша ответов VLM)."""
    t = time.time()
    vr = vlm_results or {s: vlm.check(images[s], settings, raw=(raw or {}).get(s)) for s in SLOTS}
    slots, cross, final = _decide(result["evidence"], result["entered"], settings, "final", vr)
    return dict(result, slots=slots, cross=cross, final=final, vlm=vr, needs_vlm=False,
                vlm_seconds=round(time.time() - t, 1))


def load(data: bytes):
    return imaging.load_bgr(data)
