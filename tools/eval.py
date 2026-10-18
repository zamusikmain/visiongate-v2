"""Прогон решения по тестовому датасету и HTML-отчёт.

  python tools/eval.py                 # быстрая фаза + VLM для неотклонённых (как в проде)
  python tools/eval.py --no-vlm        # только быстрая фаза
  python tools/eval.py --vlm-all       # VLM для всех фото (для анализа причины PHOTO_OF_SCREEN)

Признаки и ответы VLM кэшируются в reports/cache — повторный прогон после правки правил занимает секунды.
"""
import argparse
import hashlib
import html
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from visiongate import decision, evidence, imaging, imei, pipeline, validation, vlm  # noqa: E402
from visiongate.config import REPORTS, load_settings  # noqa: E402

# IMEI2, напечатанные на этикетках одобренных кейсов (прочитаны глазами с фото) — для теста «ввели IMEI2».
# Это данные датасета, поэтому лежат рядом с ним (data/imei2_reference.json, в git не попадает):
# {"<IMEI1>": "<IMEI2>", ...}. Нет файла — тест пропускается.
def load_imei2(data: Path) -> dict:
    p = data.parent / "imei2_reference.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
# Базовые линии для сравнения (на тех же 14 кейсах): None — не известно
BASELINES = [
    {"name": "Текущий процесс: всё одобряется автоматически", "app_ok": 5, "app_review": 0, "app_rej": 0,
     "rej_ok": 0, "rej_review": 0, "rej_app": 9},
    {"name": "Прошлая версия (v1, данные заказчика)", "app_ok": 0, "app_review": 0, "app_rej": 5,
     "rej_ok": None, "rej_review": None, "rej_app": None},
]
PRED_LABEL = {"APPROVED": "Одобрено", "PRELIMINARY": "Одобрено*", "REVIEW": "Ручная", "REJECTED": "Отклонено"}


def read_validation(path: Path) -> dict:
    return validation.read(path)


def sha(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:16]


def cached(path: Path, fn):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    val = fn()
    path.write_text(json.dumps(val, ensure_ascii=False), encoding="utf-8")
    return val


def get_evidence(img_path: Path, slot: str, cache: Path) -> dict:
    def run():
        t = time.time()
        ev = evidence.collect(imaging.load_bgr(img_path.read_bytes()), slot)
        ev["timing"]["total"] = round(time.time() - t, 2)
        return ev
    return cached(cache / f"{sha(img_path)}_{slot}_ev{evidence.EVIDENCE_VERSION}.json", run)


def get_vlm(img_path: Path, settings: dict) -> dict:
    """Общий с сайтом кэш ответов VLM (storage/vlm_cache): ключ — хеш файла + промпт + модель."""
    raw = img_path.read_bytes()
    r = vlm.check(imaging.load_bgr(raw), settings, raw=raw)
    if not r["ok"]:
        raise RuntimeError(f"VLM не ответила для {img_path.name}: {r['error']}")
    return r


def run_case(case: dict, entered: str, settings: dict, args, cache: Path) -> dict:
    ev = {s: get_evidence(case[s], s, cache) for s in pipeline.SLOTS}
    res = pipeline.fast_check({}, entered, settings, evidences=ev)
    vlm_needed = res["needs_vlm"] or (args.vlm_all and res["final"]["reasons"] != ["INVALID_IMEI"])
    if vlm_needed and settings["vlm_provider"] != "off":
        vr = {s: get_vlm(case[s], settings) for s in pipeline.SLOTS}
        res = pipeline.vlm_check({}, res, settings, vlm_results=vr)
    return res


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    """Верхняя граница Клоппера–Пирсона для доли k/n (двусторонний интервал)."""
    from math import comb
    if k >= n:
        return 1.0
    alpha = (1 - conf) / 2
    lo, hi = k / n, 1.0
    for _ in range(60):  # бисекция: P(X <= k | p) = alpha
        p = (lo + hi) / 2
        cdf = sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
        lo, hi = (p, hi) if cdf > alpha else (lo, p)
    return hi


def slot_pred(d: dict) -> str:
    return {"ok": "OK", "review": "REVIEW"}.get(d["status"], d["reason"])


def matrix_html(rows_lbl, cols_lbl, counts, title, ok_pairs=()):
    h = f"<h3>{html.escape(title)}</h3><table class='m'><tr><th>Эталон \\ Решение</th>" + \
        "".join(f"<th>{html.escape(c)}</th>" for c in cols_lbl) + "</tr>"
    for r in rows_lbl:
        h += f"<tr><th>{html.escape(r)}</th>"
        for c in cols_lbl:
            n = counts.get((r, c), 0)
            cls = "good" if (r, c) in ok_pairs and n else ("bad" if n else "")
            h += f"<td class='{cls}'>{n or ''}</td>"
        h += "</tr>"
    return h + "</table>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "data" / "Test"))
    ap.add_argument("--no-vlm", action="store_true")
    ap.add_argument("--vlm-all", action="store_true")
    ap.add_argument("--photo-only", action="store_true", help="без введённого IMEI: сверка только между фото")
    args = ap.parse_args()
    settings = load_settings()
    if args.no_vlm:
        settings["vlm_provider"] = "off"
    data = Path(args.data)
    cache = REPORTS / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    truth = read_validation(data / "Description" / "VALIDATION.xlsx")

    cases = []
    for d in sorted(list((data / "Approved_cases").glob("*")) + list((data / "Rejected_cases").glob("*"))):
        if not d.is_dir():
            continue
        dev, scn = next(d.glob("device_*")), next(d.glob("scan_*"))
        key = imei.normalize(d.name)
        cases.append({"imei": key, "folder": d.name, "device": dev, "scan": scn, "truth": truth[key]})

    t0 = time.time()
    results = []
    for c in cases:
        r = run_case(c, "" if args.photo_only else c["imei"], settings, args, cache)
        results.append((c, r))
        print(f"{c['imei']} эталон={c['truth']['final']:8} → {r['final']['status']:11} "
              f"device={slot_pred(r['slots']['device']):22} scan={slot_pred(r['slots']['scan'])}", flush=True)

    # --- синтетика ---
    synth = []
    approved = [c for c in cases if c["truth"]["final"] == "APPROVED"]
    for i, c in enumerate([] if args.photo_only else approved):
        other = approved[(i + 1) % len(approved)]["imei"]
        r = run_case(c, other, settings, args, cache)
        synth.append(("IMEI_MISMATCH", c["imei"], other, r["final"]["status"], r["final"]["reasons"],
                      r["final"]["status"] == "REJECTED" and "IMEI_MISMATCH" in r["final"]["reasons"],
                      r["final"]["status"] != "APPROVED" and r["final"]["status"] != "PRELIMINARY"))
    for c in ([] if args.photo_only else cases):
        bad = c["imei"][:-1] + str((int(c["imei"][-1]) + 1) % 10)
        r = run_case(c, bad, settings, args, cache)
        synth.append(("INVALID_IMEI", c["imei"], bad, r["final"]["status"], r["final"]["reasons"],
                      r["final"]["reasons"] == ["INVALID_IMEI"], r["final"]["reasons"] == ["INVALID_IMEI"]))
    for i, c in enumerate(approved):
        # фото коробки одного устройства + скан другого: сверка между фото должна дать IMEI_MISMATCH
        other = approved[(i + 1) % len(approved)]
        mixed = dict(c, scan=other["scan"])
        r = run_case(mixed, "" if args.photo_only else c["imei"], settings, args, cache)
        synth.append(("РАЗНЫЕ УСТРОЙСТВА", f"{c['imei']} + скан {other['imei']}", c["imei"], r["final"]["status"],
                      r["final"]["reasons"], r["final"]["status"] == "REJECTED" and "IMEI_MISMATCH" in r["final"]["reasons"],
                      r["final"]["status"] not in ("APPROVED", "PRELIMINARY")))
    imei2_of = {} if args.photo_only else load_imei2(data)
    for c in approved:
        i2 = imei2_of.get(c["imei"])
        if not i2:
            continue
        assert imei.is_valid_imei(i2), i2
        r = run_case(c, i2, settings, args, cache)
        st = r["final"]["status"]
        synth.append(("ВВЕДЁН IMEI2", c["imei"], i2, st, r["final"]["reasons"], st in ("APPROVED", "PRELIMINARY"),
                      st != "REJECTED"))

    # --- метрики ---
    final_counts = Counter((c["truth"]["final"], r["final"]["status"]) for c, r in results)
    slot_status = Counter()
    reason_counts = Counter()
    for c, r in results:
        for s in pipeline.SLOTS:
            t = c["truth"][s]
            p = slot_pred(r["slots"][s])
            reason_counts[(t, p)] += 1
            slot_status[("OK" if t == "OK" else "Отклонить", {"OK": "OK", "REVIEW": "Ручная"}.get(p, "Отклонено"))] += 1
    n = len(results)
    false_approve = sum(v for (t, p), v in final_counts.items() if t == "REJECTED" and p in ("APPROVED", "PRELIMINARY"))
    false_reject = sum(v for (t, p), v in final_counts.items() if t == "APPROVED" and p == "REJECTED")
    review = sum(v for (t, p), v in final_counts.items() if p == "REVIEW")
    auto = n - review
    auto_ok = sum(v for (t, p), v in final_counts.items()
                  if (t == "APPROVED" and p in ("APPROVED", "PRELIMINARY")) or (t == "REJECTED" and p == "REJECTED"))
    slot_total = 2 * n
    reason_exact = sum(v for (t, p), v in reason_counts.items() if t == p)
    slot_rejected_true = [(c, r, s) for c, r in results for s in pipeline.SLOTS
                          if c["truth"][s] != "OK" and r["slots"][s]["status"] == "reject"]
    reason_right_when_rejected = sum(1 for c, r, s in slot_rejected_true if r["slots"][s]["reason"] == c["truth"][s])
    n_rej = sum(1 for c, _ in results if c["truth"]["final"] == "REJECTED")
    n_app = n - n_rej
    fast_times = [sum(r["evidence"][s]["timing"].get("total", 0) for s in pipeline.SLOTS) for _, r in results]
    vlm_times = [r["vlm"][s]["seconds"] for _, r in results if r.get("vlm") for s in pipeline.SLOTS]

    summary = {
        "generated": datetime.now().isoformat(timespec="seconds"), "cases": n, "photo_only": args.photo_only,
        # IMEI, определённый системой (введённый или с фото), совпал с эталоном (или это IMEI2 того же устройства)
        "imei_detected_ok": sum(1 for c, r in results if r.get("imei") and (r["imei"] == c["imei"]
                                                                            or imei.same_serial(r["imei"], c["imei"]))),
        "imei_detected_wrong": sum(1 for c, r in results if r.get("imei") and r["imei"] != c["imei"]
                                   and not imei.same_serial(r["imei"], c["imei"])),
        "vlm_provider": settings["vlm_provider"], "vlm_all": args.vlm_all,
        "false_approve": false_approve, "false_reject": false_reject, "review": review,
        "n_rejected": n_rej, "n_approved": n_app,
        "false_approve_ci_upper": round(cp_upper(false_approve, n_rej) * 100),
        "false_reject_ci_upper": round(cp_upper(false_reject, n_app) * 100),
        "auto_decided": auto, "auto_correct": auto_ok,
        "slot_reason_exact": reason_exact, "slot_total": slot_total,
        "current": {
            "app_ok": sum(v for (t, p), v in final_counts.items() if t == "APPROVED" and p in ("APPROVED", "PRELIMINARY")),
            "app_review": final_counts.get(("APPROVED", "REVIEW"), 0),
            "app_rej": final_counts.get(("APPROVED", "REJECTED"), 0),
            "rej_ok": final_counts.get(("REJECTED", "REJECTED"), 0),
            "rej_review": final_counts.get(("REJECTED", "REVIEW"), 0),
            "rej_app": sum(v for (t, p), v in final_counts.items() if t == "REJECTED" and p in ("APPROVED", "PRELIMINARY")),
        },
        "rejected_slots_true": len(slot_rejected_true), "rejected_slots_reason_right": reason_right_when_rejected,
        "fast_time_median": round(statistics.median(fast_times), 1) if fast_times else None,
        "fast_time_max": round(max(fast_times), 1) if fast_times else None,
        "vlm_time_median": round(statistics.median(vlm_times), 1) if vlm_times else None,
        "synthetic": [{"test": s[0], "case": s[1], "entered": s[2], "status": s[3], "reasons": s[4],
                       "expected": s[5], "safe": s[6]} for s in synth],
        "elapsed_s": round(time.time() - t0, 1),
    }
    suffix = "_photo" if args.photo_only else ""
    (REPORTS / f"eval_results{suffix}.json").write_text(json.dumps({
        "summary": summary,
        "cases": [{"imei": c["imei"], "truth": c["truth"], "final": r["final"],
                   "slots": {s: {k: r["slots"][s].get(k) for k in ("status", "reason", "message", "read_imeis", "suspected")}
                             for s in pipeline.SLOTS},
                   "vlm": {s: {k: v for k, v in r["vlm"][s].items() if k != "raw"} for s in pipeline.SLOTS} if r.get("vlm") else None}
                  for c, r in results]}, ensure_ascii=False, indent=1), encoding="utf-8")
    (REPORTS / f"eval_report{suffix}.html").write_text(render(summary, results, final_counts, slot_status, reason_counts, synth),
                                              encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "synthetic"}, ensure_ascii=False, indent=1))
    print("Отчёт:", REPORTS / f"eval_report{suffix}.html")


def render(sm, results, final_counts, slot_status, reason_counts, synth) -> str:
    e = html.escape
    reasons = ["OK"] + list(decision.REASONS)
    reason_rows = [r for r in reasons if any(t == r for t, _ in reason_counts)]
    reason_cols = [r for r in reasons + ["REVIEW"] if any(p == r for _, p in reason_counts)]
    case_rows = ""
    for c, r in results:
        def cell(s):
            d = r["slots"][s]
            p = slot_pred(d)
            ok = p == c["truth"][s]
            cls = "good" if ok else ("warn" if p == "REVIEW" else "bad")
            v = (r.get("vlm") or {}).get(s)
            vtxt = f"<br><small>VLM: экран={'да' if v['screen'] else 'нет'}, {v['seconds']} с</small>" if v and v.get("ok") else ""
            return (f"<td class='{cls}'><b>{e(p)}</b> <small>(эталон {e(c['truth'][s])})</small><br>"
                    f"<small>{e(d['message'])}</small><br><small class='mono'>IMEI: {e(', '.join(d.get('read_imeis') or []) or '—')}</small>{vtxt}</td>")
        f = r["final"]["status"]
        t = c["truth"]["final"]
        fcls = "good" if (t == "APPROVED" and f in ("APPROVED", "PRELIMINARY")) or (t == "REJECTED" and f == "REJECTED") \
            else ("warn" if f == "REVIEW" else "bad")
        tt = sum(r["evidence"][s]["timing"].get("total", 0) for s in pipeline.SLOTS)
        case_rows += (f"<tr><td class='mono'>{e(c['imei'])}</td><td>{e(t)}</td><td class='{fcls}'><b>{e(PRED_LABEL[f])}</b></td>"
                      f"{cell('device')}{cell('scan')}<td>{tt:.1f} с</td></tr>")
    synth_rows = "".join(
        f"<tr><td>{e(s[0])}</td><td class='mono'>{e(s[1])}</td><td class='mono'>{e(s[2])}</td>"
        f"<td class='{'good' if s[5] else ('warn' if s[6] else 'bad')}'>{e(PRED_LABEL[s[3]])} {e(', '.join(s[4]))}</td></tr>"
        for s in synth)
    vlm_note = {"off": "VLM выключена (--no-vlm): «фото экрана» проверяется только по признакам интерфейса в OCR.",
                "ollama": "VLM: локальная Ollama" + (" для всех фото (--vlm-all)." if sm["vlm_all"] else " только для заявок, не отклонённых быстрой фазой (как в проде)."),
                "anthropic": "VLM: внешний API Anthropic."}[sm["vlm_provider"]]
    vlm_note += (" Режим: БЕЗ введённого IMEI — номер читается с фото, сверяются фото между собой" if sm["photo_only"]
                 else " Режим: IMEI введён (из имени папки).") + \
        f" IMEI определён верно: {sm['imei_detected_ok']} из {sm['cases']}, неверно: {sm['imei_detected_wrong']}."
    def num(v, total):
        return "—" if v is None else f"{v} из {total}"
    base_rows = ""
    for b in BASELINES + [dict(sm["current"], name="VisionGate v2 (эта версия)")]:
        cur = b["name"].startswith("VisionGate")
        base_rows += (f"<tr{' class=good' if cur else ''}><td>{'<b>' if cur else ''}{e(b['name'])}{'</b>' if cur else ''}</td>"
                      f"<td>{num(b['app_ok'], sm['n_approved'])}</td><td>{num(b['app_review'], sm['n_approved'])}</td>"
                      f"<td>{num(b['app_rej'], sm['n_approved'])}</td><td>{num(b['rej_ok'], sm['n_rejected'])}</td>"
                      f"<td>{num(b['rej_review'], sm['n_rejected'])}</td><td>{num(b['rej_app'], sm['n_rejected'])}</td></tr>")
    compare = (f"<h2>Сравнение с текущим процессом и прошлой версией</h2>"
               f"<table><tr><th rowspan=2>Версия</th><th colspan=3>Одобренные по эталону ({sm['n_approved']})</th>"
               f"<th colspan=3>Отклонённые по эталону ({sm['n_rejected']})</th></tr>"
               f"<tr><th>одобрено ✓</th><th>на ручную</th><th>ложный отказ ✗</th>"
               f"<th>отклонено ✓</th><th>на ручную</th><th>ложное одобрение ✗</th></tr>{base_rows}</table>"
               f"<p><small>«Одобрено» для v2 включает «предварительно одобрено», если VLM не запускалась. "
               f"Цифры прошлой версии — со слов заказчика, на отклонённых кейсах они не известны.</small></p>")
    final_m = matrix_html(["APPROVED", "REJECTED"], ["APPROVED", "PRELIMINARY", "REVIEW", "REJECTED"], final_counts,
                          "Итоговый статус", ok_pairs={("APPROVED", "APPROVED"), ("APPROVED", "PRELIMINARY"), ("REJECTED", "REJECTED")})
    slot_m = matrix_html(["OK", "Отклонить"], ["OK", "Ручная", "Отклонено"], slot_status, "Статус по слотам (28 фото)",
                         ok_pairs={("OK", "OK"), ("Отклонить", "Отклонено")})
    reason_m = matrix_html(reason_rows, reason_cols, reason_counts, "Причина по слотам",
                           ok_pairs={(r, r) for r in reasons})
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Отчёт по датасету</title>
<style>
:root {{ --bg:#f5f6f8; --card:#fff; --text:#1b1f24; --muted:#5d6673; --line:#dde1e6;
  --good:#e5f5ea; --bad:#fdecea; --warn:#fdf3e1; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111418; --card:#1a1e24; --text:#e7eaee; --muted:#9aa4b1;
  --line:#2c323a; --good:#12301e; --bad:#3a1714; --warn:#352610; }} }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.45 system-ui,"Segoe UI",sans-serif; }}
main {{ max-width:1200px; margin:0 auto; padding:16px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; margin-bottom:14px; overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; }} th,td {{ border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }}
table.m {{ width:auto; }} table.m td {{ text-align:center; min-width:60px; }}
.good {{ background:var(--good); }} .bad {{ background:var(--bad); }} .warn {{ background:var(--warn); }}
.kpi {{ display:flex; gap:12px; flex-wrap:wrap; }} .kpi div {{ background:var(--bg); border-radius:10px; padding:10px 14px; }}
.kpi b {{ font-size:22px; display:block; }} .mono {{ font-family:ui-monospace,Consolas,monospace; }}
small {{ color:var(--muted); }} h1 {{ font-size:22px; }}
</style></head><body><main>
<h1>Прогон по тестовому датасету</h1>
<p><small>{e(sm['generated'])} · кейсов: {sm['cases']} · {e(vlm_note)}</small></p>
<div class="card"><div class="kpi">
<div><b>{sm['false_approve']}</b>ложных одобрений</div>
<div><b>{sm['false_reject']}</b>ложных отклонений</div>
<div><b>{sm['review']} из {sm['cases']}</b>на ручную проверку</div>
<div><b>{sm['auto_correct']} из {sm['auto_decided']}</b>верных авто-решений</div>
<div><b>{sm['rejected_slots_reason_right']} из {sm['rejected_slots_true']}</b>верная причина у отклонённых слотов</div>
<div><b>{sm['fast_time_median']} с</b>быстрая фаза, медиана (макс. {sm['fast_time_max']} с)</div>
<div><b>{sm['vlm_time_median'] or '—'} с</b>VLM на фото, медиана</div>
</div><p><small>«Одобрено*» = предварительно одобрено быстрой фазой, VLM не запускалась.</small></p></div>
<div class="card">{compare}</div>
<div class="card">
<h2>Насколько можно доверять этим цифрам</h2>
<ul>
<li><b>14 кейсов — это очень мало.</b> Одна ошибка меняет точность на 7 процентных пунктов. Интервалы неопределённости огромные: {sm['false_approve']} ложных одобрений из {sm['n_rejected']} отклонённых кейсов совместимы с реальной долей ложных одобрений до ~{sm['false_approve_ci_upper']}%, а {sm['false_reject']} ложных отклонений из {sm['n_approved']} одобренных — с долей до ~{sm['false_reject_ci_upper']}% (95% доверительный интервал Клоппера–Пирсона).</li>
<li><b>Возможна невольная подгонка.</b> Правила и параметры (масштабы OCR, извлечение IMEI, детектор областей штрихкодов) я проверял на этих же 28 фото. Я старался не вводить порогов под конкретные файлы, но независимой отложенной выборки нет. Реальные результаты на новых фото, скорее всего, хуже.</li>
<li><b>Промпт VLM выбран по этим же фото.</b> Из двух вариантов оставлен тот, что дал меньше ложных «фото экрана» на одобренных кейсах. Это прямая подгонка под датасет: на новых фото доля ложных подозрений может быть выше. Безопасная сторона: подозрение только отправляет заявку на ручную проверку.</li>
<li><b>Однородность датасета.</b> Все фото — Samsung нескольких моделей, похожие этикетки, 3 магазина и, вероятно, всего несколько продавцов. Другие модели, этикетки, освещение и телефоны продавцов не проверены.</li>
<li><b>Причины IMEI_MISMATCH, INVALID_IMEI и ввод IMEI2 проверены только синтетически</b> (подмена введённого номера). Реальных фото с чужим IMEI в датасете нет.</li>
<li><b>«Фото экрана»:</b> 6 фото экрана, все от одного продавца и, похоже, с одного телефона. Детектор (VLM + признаки интерфейса) на других экранах (мониторы, айфоны, без мессенджера) не проверен.</li>
<li><b>Причины CROPPED и NO_SERIAL против BLURRY</b> определяются эвристиками, на каждую по 3 примера. Верный статус «отклонено» здесь гораздо надёжнее, чем верная формулировка причины.</li>
<li>Время замерено на этом ноутбуке (Core Ultra 5 225U, CPU) на фото датасета, в один поток. При нескольких продавцах одновременно быстрые проверки идут в очередь, VLM — тоже.</li>
</ul></div>
<div class="card">{final_m}</div>
<div class="card">{slot_m}{reason_m}</div>
<div class="card"><h2>Синтетические проверки IMEI</h2>
<p><small>Зелёный — ожидаемый результат, жёлтый — безопасно (ручная проверка), красный — ошибка.</small></p>
<table><tr><th>Тест</th><th>Кейс</th><th>Введено</th><th>Результат</th></tr>{synth_rows}</table></div>
<div class="card"><h2>По кейсам</h2>
<table><tr><th>IMEI</th><th>Эталон</th><th>Итог</th><th>Фото коробки</th><th>Скан</th><th>Быстрая фаза</th></tr>{case_rows}</table></div>
</main></body></html>"""


if __name__ == "__main__":
    main()
