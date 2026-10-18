"""Замер варианта C: быстрые детекторы «фото экрана» для быстрой фазы (бюджет 1–3 с на фото).

Отдельное окружение (torch не входит в зависимости приложения):
  python -m venv .venv-probe
  .venv-probe\\Scripts\\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  .venv-probe\\Scripts\\python -m pip install open_clip_torch pillow openpyxl
  .venv-probe\\Scripts\\python tools\\probe_screen.py [--ollama moondream]

Без подгонки под датасет: классы и подсказки зафиксированы заранее, решение — argmax (без порога),
кадр целиком вписывается в квадрат (рамка телефона по краям не обрезается). Эталон «экран» —
кейсы с причиной «photo of photo from other device» из VALIDATION.xlsx.
"""
import argparse
import base64
import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SCREEN_PROMPTS = [
    "a photo of a smartphone screen showing a picture",
    "a photo taken of a phone display with a messenger app",
    "a photo of a computer monitor screen showing a photo",
    "a picture of a picture displayed on a mobile phone",
]
BOX_PROMPTS = [
    "a photo of a cardboard smartphone box",
    "a photo of a white sticker with barcodes on a product box",
    "a close-up photo of a product label with barcodes",
    "a photo of a hand holding a phone box in a shop",
]


def cases():
    import openpyxl
    ws = openpyxl.load_workbook(ROOT / "data/Test/Description/VALIDATION.xlsx", data_only=True).active
    screen = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[1] and len(str(row[1])) == 15:
            screen[str(row[1])] = {"device": "photo of photo" in str(row[4]).lower(),
                                   "scan": "photo of photo" in str(row[5]).lower()}
    out = []
    for p in sorted((ROOT / "data/Test").glob("*_cases/*/*.jpg")):
        slot = "device" if p.name.startswith("device") else "scan"
        out.append((p, slot, screen[p.stem.split("_")[1]][slot]))
    return out


def letterbox(img: Image.Image, side: int) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((side, side))
    canvas = Image.new("RGB", (side, side), (0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas


def run_clip(items):
    import open_clip
    import torch
    torch.set_num_threads(4)
    t = time.time()
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    tok = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    with torch.no_grad():
        txt = model.encode_text(tok(SCREEN_PROMPTS + BOX_PROMPTS))
        txt = txt / txt.norm(dim=-1, keepdim=True)
    load_s = time.time() - t
    res = []
    for p, slot, truth in items:
        t = time.time()
        x = preprocess(letterbox(Image.open(p), 224)).unsqueeze(0)
        with torch.no_grad():
            im = model.encode_image(x)
            im = im / im.norm(dim=-1, keepdim=True)
            sims = (100 * im @ txt.T).softmax(dim=-1)[0]
        p_screen = float(sims[:len(SCREEN_PROMPTS)].sum())
        res.append({"file": p.name, "slot": slot, "truth": truth, "pred": p_screen > 0.5,
                    "p_screen": round(p_screen, 3), "seconds": round(time.time() - t, 2)})
    return res, load_s


def run_ollama(items, model):
    prompt = ("Ignore the watermark text. Is this a photo of the screen of another phone or monitor "
              "(not a real box photographed directly)? Answer only yes or no.")
    res = []
    for p, slot, truth in items:
        buf = io.BytesIO()
        letterbox(Image.open(p), 768).save(buf, "JPEG", quality=90)
        body = json.dumps({"model": model, "prompt": prompt, "images": [base64.b64encode(buf.getvalue()).decode()],
                           "stream": False, "options": {"temperature": 0, "num_predict": 5}}).encode()
        t = time.time()
        r = json.loads(urllib.request.urlopen(urllib.request.Request(
            "http://localhost:11434/api/generate", body, {"Content-Type": "application/json"}), timeout=900).read())
        ans = r["response"].strip().lower()
        res.append({"file": p.name, "slot": slot, "truth": truth, "pred": ans.startswith("yes"), "answer": ans[:20],
                    "seconds": round(time.time() - t, 1)})
        print(res[-1], flush=True)
    return res


def summary(name, res, extra=""):
    tp = sum(r["pred"] and r["truth"] for r in res)
    fp = sum(r["pred"] and not r["truth"] for r in res)
    fn = sum(not r["pred"] and r["truth"] for r in res)
    tn = sum(not r["pred"] and not r["truth"] for r in res)
    times = sorted(r["seconds"] for r in res)
    print(f"\n{name}: найдено экранов {tp}/{tp + fn}, ложных срабатываний {fp}/{fp + tn}, "
          f"время на фото: медиана {times[len(times) // 2]} с, макс {times[-1]} с {extra}")
    return {"name": name, "tp": tp, "fn": fn, "fp": fp, "tn": tn, "median_s": times[len(times) // 2], "max_s": times[-1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ollama", default="", help="модель Ollama для сравнения, например moondream")
    ap.add_argument("--limit", type=int, default=0, help="для медленных моделей: только N фото")
    a = ap.parse_args()
    items = cases()
    out = {}
    res, load_s = run_clip(items)
    for r in res:
        print(r)
    out["clip"] = {"summary": summary("CLIP ViT-B-32 (zero-shot, argmax)", res, f"(загрузка модели {load_s:.1f} с)"),
                   "rows": res}
    if a.ollama:
        sub = items[:a.limit] if a.limit else items
        if a.limit:  # берём поровну экранов и не-экранов, чтобы оценить и время, и ответы
            scr = [i for i in items if i[2]][: a.limit // 2]
            sub = scr + [i for i in items if not i[2]][: a.limit - len(scr)]
        r2 = run_ollama(sub, a.ollama)
        out[a.ollama] = {"summary": summary(a.ollama, r2), "rows": r2}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/probe_screen.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
