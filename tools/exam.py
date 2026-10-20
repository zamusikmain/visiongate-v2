"""Exam mode: check a folder or ZIP of cases and write the result in VALIDATION.xlsx format.

  .venv\\Scripts\\python.exe tools\\exam.py <folder-or-zip> [--out result.xlsx] [--vlm auto|off] [--threads 0]

Input: the same structure as the provided dataset, labels not needed: any folders with device_*.jpg and
scan_*.jpg (one pair per folder, or pairs with matching name endings). The IMEI is read from the photos;
if a folder/file name contains a 15-digit IMEI it is written to the SN/IMEI column.

Every case is strictly Approved or Rejected (see visiongate/exam.py and README for the rule).
Two passes so a result file always exists early:
  1) fast checks for all cases (~6 s per case) -> result file written;
  2) screen-photo check (local VLM, ~3 min per case on this CPU) only for cases that would otherwise be
     Approved -> result file rewritten after every case. Ctrl+C keeps the file from the last finished case.
"""
import argparse
import io
import os
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from visiongate import batch, exam, ingest, pipeline  # noqa: E402
from visiongate.config import load_settings  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def folder_to_zip(folder: Path) -> tuple[bytes, dict]:
    """Папка → ZIP в памяти (тот же разбор пар, что и для загруженного архива) + даты файлов."""
    buf, dates = io.BytesIO(), {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file() and (p.suffix.lower() in IMG_EXT or p.name.lower() == "validation.xlsx"):
                arc = p.relative_to(folder).as_posix()
                z.write(p, arc)
                dates[arc] = datetime.fromtimestamp(p.stat().st_mtime)
    return buf.getvalue(), dates


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="folder or .zip with case folders (device_*.jpg + scan_*.jpg)")
    ap.add_argument("--out", default="", help="output .xlsx (default: <input>_result.xlsx next to the input)")
    ap.add_argument("--vlm", choices=["auto", "off"], default="auto",
                    help="auto: screen-photo check only for cases that would otherwise be Approved; off: fast checks only")
    ap.add_argument("--threads", type=int, default=0, help="CPU threads for Ollama (0 = all, best when nothing else runs)")
    ap.add_argument("--name-imei", action="store_true", help="also compare photos with the IMEI from folder/file names")
    ap.add_argument("--no-db", action="store_true", help="do not record cases in the dashboard database")
    a = ap.parse_args()

    src = Path(a.input).resolve()
    if src.is_dir():
        data, dates = folder_to_zip(src)
    elif src.suffix.lower() == ".zip":
        data, dates = src.read_bytes(), {}
    else:
        sys.exit("Input must be a folder or a .zip file")
    out = Path(a.out) if a.out else src.with_name(src.stem + "_result.xlsx")
    pairs, _truth, warnings = batch.parse_zip(data)  # эталон, если он есть в папке, здесь не используется
    for w in warnings:
        print("WARNING:", w)
    zf = zipfile.ZipFile(io.BytesIO(data))
    settings = dict(load_settings())
    settings["ollama_num_thread"] = a.threads
    if a.vlm == "off":
        settings["vlm_provider"] = "off"
        settings["require_screen_check"] = False
    print(f"{len(pairs)} cases found. Output: {out}")

    rows, results, raws, sids = [], [], [], []
    exam_batch = "exam-" + time.strftime("%Y%m%d-%H%M%S")

    def record(raw, res, err=None, pending=False):
        """Заявка в БД админ-панели (решение не меняется)."""
        if a.no_db:
            return None
        try:
            return ingest.save(raw or {}, res, "exam", exam_batch, error=err, vlm_pending=pending)
        except Exception as ex:
            print("WARNING: dashboard DB write failed:", ex)
            return None

    def row_for(pair, res, err=None):
        e = exam.resolve(res) if res else {"final": exam.REJECTED, "confidence": "low", "device": exam.OK,
                                           "scan": exam.OK, "reason": f"Processing error: {err}",
                                           "note": "processing error"}
        dt = dates.get(pair["device"]) or datetime(*zf.getinfo(pair["device"]).date_time)
        return {"imei": pair["imei_name"] or (res or {}).get("imei") or "", "date": exam.fmt_date(dt),
                "device": e["device"], "scan": e["scan"], "final": e["final"], "reason": e["reason"],
                "confidence": e["confidence"], "note": e["note"], "imei_source": (res or {}).get("imei_source", ""),
                "device_file": pair["device"], "scan_file": pair["scan"]}

    def save():
        tmp = out.with_suffix(".tmp.xlsx")
        tmp.write_bytes(exam.write_xlsx(rows))
        os.replace(tmp, out)

    # 1) быстрые проверки по всем кейсам
    t0 = time.time()
    for i, pair in enumerate(pairs, 1):
        try:
            raw = {s: zf.read(pair[s]) for s in pipeline.SLOTS}
            imgs = {s: pipeline.load(raw[s]) for s in pipeline.SLOTS}
            res = pipeline.fast_check(imgs, pair["imei_name"] if a.name_imei else "", settings)
            results.append(res)
            raws.append(raw)
            rows.append(row_for(pair, res))
            sids.append(record(raw, res, pending=(a.vlm == "auto" and ingest.wants_vlm(res, "auto"))))
        except Exception as ex:  # битое фото: кейс отклоняется, прогон продолжается
            results.append(None)
            raws.append(None)
            sids.append(record(locals().get("raw"), None, err=str(ex)[:200]))
            rows.append(row_for(pair, None, str(ex)[:200]))
        r = rows[-1]
        print(f"[fast {i}/{len(pairs)}] {pair['folder']}: {r['final']} ({r['confidence']}) {r['reason']}", flush=True)
    save()
    print(f"Fast pass done in {time.time() - t0:.0f} s -> {out}")

    # 2) проверка на фото экрана — только там, где без неё был бы Approved
    todo = [i for i, res in enumerate(results)
            if res and res["needs_vlm"] and exam.resolve(res)["final"] == exam.APPROVED]
    if a.vlm == "auto" and todo:
        print(f"Screen-photo check (VLM) for {len(todo)} case(s) that would otherwise be Approved "
              f"(~3 min each on CPU). Ctrl+C keeps the current file.")
        t1 = time.time()
        try:
            for k, i in enumerate(todo, 1):
                imgs = {s: pipeline.load(raws[i][s]) for s in pipeline.SLOTS}
                if sids[i]:
                    ingest.mark_running(sids[i])
                results[i] = pipeline.vlm_check(imgs, results[i], settings, raw=raws[i])
                rows[i] = row_for(pairs[i], results[i])
                if sids[i]:
                    ingest.update(sids[i], results[i])
                save()
                r = rows[i]
                print(f"[vlm {k}/{len(todo)}] {pairs[i]['folder']}: {r['final']} ({r['confidence']}) "
                      f"{r['reason']}  [{time.time() - t1:.0f} s]", flush=True)
        except KeyboardInterrupt:
            print("Interrupted: the result file contains everything finished so far.")
    appr = sum(r["final"] == exam.APPROVED for r in rows)
    low = sum(r["confidence"] == "low" for r in rows)
    print(f"Done in {time.time() - t0:.0f} s: {appr} Approved, {len(rows) - appr} Rejected, "
          f"{low} low-confidence. Result: {out}")


if __name__ == "__main__":
    main()
