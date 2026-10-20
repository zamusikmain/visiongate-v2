"""Import a folder or ZIP of cases into the dashboard database (one command to fill the dashboard).

  .venv\\Scripts\\python.exe tools\\import_dataset.py <folder-or-zip> [--vlm auto|all|off] [--threads 0]

Each case (a folder with device_*.jpg + scan_*.jpg, labels not needed) goes through the same pipeline as the
website (fast checks, then the screen-photo check by the local VLM) and is stored as a submission with
source = "import". Cases waiting for the screen check are visible in "Processing queue" while it runs.
--vlm auto (default): screen check only for cases that would otherwise be Approved; all: every non-rejected
case; off: fast checks only (those cases stay "Needs review", not checked for a screen photo).
"""
import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from visiongate import batch, ingest, pipeline  # noqa: E402
from visiongate.config import load_settings  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def read_input(src: Path) -> bytes:
    if src.is_dir():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for p in sorted(src.rglob("*")):
                if p.is_file() and p.suffix.lower() in IMG_EXT:
                    z.write(p, p.relative_to(src).as_posix())
        return buf.getvalue()
    if src.suffix.lower() == ".zip":
        return src.read_bytes()
    sys.exit("Input must be a folder or a .zip file")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--vlm", choices=["auto", "all", "off"], default="auto")
    ap.add_argument("--threads", type=int, default=0, help="CPU threads for Ollama (0 = all)")
    ap.add_argument("--name-imei", action="store_true", help="compare photos with the IMEI from folder/file names")
    a = ap.parse_args()
    data = read_input(Path(a.input).resolve())
    pairs, _truth, warnings = batch.parse_zip(data)
    for w in warnings:
        print("WARNING:", w)
    zf = zipfile.ZipFile(io.BytesIO(data))
    settings = dict(load_settings())
    settings["ollama_num_thread"] = a.threads
    if a.vlm == "off":
        settings["vlm_provider"] = "off"
    tag = "import-" + time.strftime("%Y%m%d-%H%M%S")
    print(f"{len(pairs)} cases -> dashboard DB (batch id {tag})")
    t0 = time.time()
    todo = []
    for i, pair in enumerate(pairs, 1):
        raw = None
        try:
            raw = {s: zf.read(pair[s]) for s in pipeline.SLOTS}
            imgs = {s: pipeline.load(raw[s]) for s in pipeline.SLOTS}
            res = pipeline.fast_check(imgs, pair["imei_name"] if a.name_imei else "", settings)
            pending = ingest.wants_vlm(res, a.vlm)
            sid = ingest.save(raw, res, "import", tag, vlm_pending=pending)
            if pending:
                todo.append((sid, imgs, raw, res))
            print(f"[fast {i}/{len(pairs)}] #{sid} {pair['folder']}: {res['final']['status']}", flush=True)
        except Exception as ex:
            sid = ingest.save(raw or {}, None, "import", tag, error=str(ex)[:200])
            print(f"[fast {i}/{len(pairs)}] #{sid} {pair['folder']}: ERROR {ex}", flush=True)
    for k, (sid, imgs, raw, res) in enumerate(todo, 1):
        ingest.mark_running(sid)
        res = pipeline.vlm_check(imgs, res, settings, raw=raw)
        ingest.update(sid, res)
        print(f"[vlm {k}/{len(todo)}] #{sid}: {res['final']['status']}  [{time.time() - t0:.0f} s]", flush=True)
    print(f"Done in {time.time() - t0:.0f} s. Open the dashboard: / (Overview) or /submissions?source=import")


if __name__ == "__main__":
    main()
