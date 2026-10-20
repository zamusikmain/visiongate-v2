"""Данные для админ-панели: краткая сводка заявки (для списков и графиков) и агрегаты.
Только чтение результатов проверки — логика решений здесь не меняется и не вызывается повторно."""
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from . import decision, exam

# Порядок причин в отчётах; DUPLICATE — флаг «одно фото в обоих слотах»
REASON_CODES = list(decision.REASONS) + ["DUPLICATE"]
_MODEL = re.compile(r"\bS[MNU]-?([A-Z][0-9]{3}[A-Z]?)")  # SM-A175F (без суффикса SKU)


def bucket(status: str, phase: str) -> str:
    """Группа для дашборда: approved | rejected | review | processing."""
    if phase in ("vlm_pending", "vlm_running") or status == "PROCESSING":
        return "processing"
    return {"APPROVED": "approved", "REJECTED": "rejected"}.get(status, "review")  # REVIEW и PRELIMINARY без VLM


def _model(res: dict) -> str:
    for s in ("scan", "device"):
        for ln in ((res.get("evidence") or {}).get(s) or {}).get("ocr_lines", []):
            m = _MODEL.search(ln.get("text", "").upper().replace(" ", ""))
            if m:
                return "SM-" + m.group(1)
    return ""


def summarize(res: dict | None) -> dict:
    """Сводка по результату проверки: модель, причины, уверенность экзаменационного вывода, ошибки по фото."""
    if not res or "final" not in res:
        return {}
    final = res["final"]
    reasons = list(final.get("reasons") or [])
    if final.get("duplicate"):
        reasons.append("DUPLICATE")
    try:
        ex = exam.resolve(res) if res.get("slots") else {}
    except Exception:
        ex = {}
    return {"model": _model(res), "reasons": reasons, "confidence": ex.get("confidence", ""),
            "exam_final": ex.get("final", ""), "device_errors": ex.get("device", ""), "scan_errors": ex.get("scan", ""),
            "imei_source": res.get("imei_source", ""),
            "screen_check": {s: ((res.get("slots") or {}).get(s) or {}).get("screen_check", "") for s in ("device", "scan")}}


def mask_imei(v: str) -> str:
    v = v or ""
    return v if len(v) < 8 else v[:2] + "x" * (len(v) - 6) + v[-4:]


def _day(ts: str) -> str:
    return (ts or "")[:10]


def _days(n: int) -> list[str]:
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def overview(rows: list[dict], days: int = 14) -> dict:
    """rows: строки БД со сводкой (summary). Карточки, по дням, итоги, причины, средние."""
    counts = Counter(bucket(r["status"], r["phase"]) for r in rows)
    total = len(rows)
    received, processed = Counter(), Counter()
    for r in rows:
        received[_day(r["created_at"])] += 1
        if bucket(r["status"], r["phase"]) != "processing":
            processed[_day(r["updated_at"])] += 1
    span = _days(days)
    reasons = Counter()
    for r in rows:
        for c in (r.get("summary") or {}).get("reasons", []):
            reasons[c] += 1
    fast = [r["fast_seconds"] for r in rows if r.get("fast_seconds")]
    vlm = [r["vlm_seconds"] for r in rows if r.get("vlm_seconds")]
    conf = [(r.get("summary") or {}).get("confidence") for r in rows]
    conf = [c for c in conf if c]
    return {
        "total": total,
        "buckets": {k: counts.get(k, 0) for k in ("approved", "rejected", "review", "processing")},
        "daily": [{"day": d, "received": received.get(d, 0), "processed": processed.get(d, 0)} for d in span],
        "reasons": [{"code": c, "count": reasons[c]} for c in sorted(reasons, key=lambda c: (-reasons[c], c))],
        "avg_fast_s": round(sum(fast) / len(fast), 1) if fast else None,
        "avg_vlm_s": round(sum(vlm) / len(vlm), 1) if vlm else None,
        "high_conf_share": round(100 * sum(c == "high" for c in conf) / len(conf)) if conf else None,
        "rejected_total": counts.get("rejected", 0),
    }


def reasons_report(rows: list[dict], days: int = 30) -> dict:
    """Разбивка причин отказа: количество, доля от отклонённых, динамика по дням."""
    span = _days(days)
    per_day = defaultdict(Counter)
    totals = Counter()
    rejected = sum(1 for r in rows if r["status"] == "REJECTED")
    for r in rows:
        d = _day(r["created_at"])
        for c in (r.get("summary") or {}).get("reasons", []):
            totals[c] += 1
            per_day[c][d] += 1
    items = []
    for c in sorted(totals, key=lambda c: (-totals[c], c)):
        items.append({"code": c, "count": totals[c],
                      "share": round(100 * totals[c] / rejected) if rejected else 0,
                      "daily": [per_day[c].get(d, 0) for d in span]})
    return {"days": span, "rejected_total": rejected, "total": len(rows), "items": items}


def parse_day(s: str | None):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat() if s else None
    except ValueError:
        return None


# ---------- страница «Точность модели»: отчёт tools/eval.py как есть, без пересчёта ----------
# Базовые линии — те же, что BASELINES в tools/eval.py (текущий процесс: всё одобряется; прошлая версия — данные заказчика)
BASELINES = [
    {"key": "current_process", "app_ok": 5, "app_review": 0, "app_rej": 0, "rej_ok": 0, "rej_review": 0, "rej_app": 9},
    {"key": "v1", "app_ok": 0, "app_review": 0, "app_rej": 5, "rej_ok": None, "rej_review": None, "rej_app": None},
]
SYNTH_ORDER = ["INVALID_IMEI", "IMEI_MISMATCH", "ВВЕДЁН IMEI2", "РАЗНЫЕ УСТРОЙСТВА", "ОДНО ФОТО В ОБА СЛОТА"]


def accuracy_report(reports_dir) -> dict:
    """Сводки reports/eval_results*.json. Без построчных кейсов и IMEI: синтетика — только итоги по тестам."""
    import json
    out = {"baselines": BASELINES}
    for mode, name in (("entered", "eval_results.json"), ("photo", "eval_results_photo.json")):
        p = reports_dir / name
        if not p.exists():
            out[mode] = None
            continue
        sm = json.loads(p.read_text(encoding="utf-8"))["summary"]
        syn = defaultdict(lambda: {"n": 0, "expected": 0, "safe": 0})
        for t in sm.pop("synthetic", []):
            g = syn[t["test"]]
            g["n"] += 1
            g["expected"] += bool(t["expected"])
            g["safe"] += bool(t["safe"])
        sm["synthetic"] = [dict(test=k, **syn[k]) for k in SYNTH_ORDER + sorted(set(syn) - set(SYNTH_ORDER)) if k in syn]
        sm["exam"] = {k: v for k, v in (sm.get("exam") or {}).items() if k != "wrong_cases"}
        out[mode] = sm
    return out