# VisionGate v2 — проверка фото коробок при регистрации устройства

**[Русский](#русский)** · **[English](#english)**

---

# Русский

MVP для Windows-ноутбука без видеокарты, работает без интернета. Продавец вводит IMEI (необязательно) и загружает
или снимает камерой телефона два фото: **фото коробки** и **скан этикетки**. Система за несколько секунд читает IMEI
со штрихкодов и текста, сверяет номера между фото и с введённым, а в фоне проверяет, не сфотографирован ли экран
другого устройства. Есть пакетная проверка с выгрузкой в XLSX и админ-панель со статистикой.

## 1. Возможности

- Форма регистрации с живой камерой, шаблоном-подсказкой поверх видео и считыванием штрихкода IMEI в браузере.
- Быстрая фаза (синхронно, несколько секунд): проверка Луна, штрихкоды, OCR, IMEI из текста, сверка номеров.
- Фоновая фаза: локальная vision-модель в Ollama проверяет, не является ли фото снимком экрана.
- Режим без введённого IMEI: номер читается с фото и сверяется между фото.
- Пакетная проверка ZIP → таблица → XLSX; CLI для пакетного прогона.
- Админ-панель: обзор, все заявки (поиск, фильтры, экспорт), очередь обработки, причины отказов, точность модели.
- Разбор заявок с ручным решением, настройки модели.
- RU/EN, светлая/тёмная тема, графики на чистом SVG/JS (без CDN).
- HTTPS с самоподписанным сертификатом для камеры телефона в локальной сети; режим временной ссылки через
  Cloudflare Tunnel с паролем.
- Внешний API для vision-модели — выключен по умолчанию.

## 2. Стек технологий

| Слой | Технологии |
| --- | --- |
| Backend | Python 3.11+ (рекомендуется 3.13), FastAPI, Uvicorn, python-multipart |
| CV и OCR | OpenCV 5 (headless), Pillow, NumPy, RapidOCR (PP-OCRv3 на ONNX Runtime, CPU), zxing-cpp |
| Vision-модель | Qwen2.5-VL 3B (`qwen2.5vl:3b`) в Ollama (Docker); опционально внешний API |
| Экспорт | openpyxl |
| HTTPS | cryptography (самоподписанный сертификат в `storage/certs`) |
| Frontend | Статические HTML + чистый JavaScript + CSS; zxing-wasm для считывания штрихкода в браузере |
| База данных | SQLite (`storage/visiongate.db`) |
| Инфраструктура | Docker Compose (только Ollama), PowerShell-скрипты `run.ps1`, `tunnel.ps1`, Cloudflare Quick Tunnel |

## 3. Как устроено

```
Телефон продавца ──HTTPS (LAN)──► FastAPI (Python)
  форма, камера,                    │
  считывание IMEI (zxing-wasm)      ├─ Быстрая фаза (синхронно)
                                    │    • проверка Луна введённого IMEI
                                    │    • штрихкоды: zxing-cpp
                                    │    • OCR: RapidOCR (ONNX, CPU)
                                    │    • поиск и сверка IMEI
                                    │    → решение или «на ручную проверку»
                                    │
                                    ├─ Фоновая фаза (очередь)
                                    │    • vision-модель в Ollama: «фото экрана?»
                                    │
                                    └─ SQLite: заявки, признаки, ответы модели, ручные решения
```

Статусы: одобрено, отклонено (с причиной), на ручную проверку, предварительно одобрено (идёт фоновая проверка).
Принцип: отклоняем только при явных признаках, при сомнении — ручная проверка.

## 4. Структура проекта

```text
visiongate/
  __main__.py      запуск сервера (HTTPS :8443 или --http :8000)
  web.py           FastAPI: страницы и API
  pipeline.py      быстрая фаза
  decision.py      правила решений
  imei.py          поиск IMEI, Луна, сверка
  ocr.py, barcode.py, imaging.py   OCR, штрихкоды, изображения
  vlm.py, worker.py   vision-модель и очередь фоновой проверки
  batch.py, exam.py, ingest.py, evidence.py, validation.py   пакетная проверка, экспорт, импорт
  dashboard.py     статистика для админ-панели
  db.py, certs.py, config.py   БД, сертификат, настройки
static/            HTML-страницы, JS, CSS, vendor/zxing-wasm
tools/             eval.py, exam.py, import_dataset.py, probe_screen.py, serve_public.py
run.ps1, tunnel.ps1, docker-compose.yml, requirements.txt
storage/           БД, загрузки, настройки, сертификаты, кэш модели (не в Git)
```

## 5. Страницы и API

| Страница | URL |
|---|---|
| Обзор | `/` |
| Новая заявка | `/new` |
| Результат | `/s/<id>` |
| Пакетная проверка | `/batch` |
| Все заявки | `/submissions` |
| Очередь | `/queue` |
| Причины отказов | `/reasons` |
| Точность модели | `/accuracy` |
| Разбор | `/review` |
| Настройки | `/settings` |

| Метод и путь | Назначение |
| --- | --- |
| `POST /api/submissions` | Создать заявку (фото + необязательный IMEI) |
| `GET /api/submissions`, `GET /api/submissions/{id}` | Список и одна заявка |
| `GET /api/submissions/{id}/photo/{slot}` | Фото заявки |
| `POST /api/submissions/{id}/review` | Ручное решение |
| `POST /api/batches`, `GET /api/batches/{job}`, `GET /api/batches/{job}/xlsx` | Пакетная проверка |
| `GET /api/stats/overview`, `GET /api/stats/reasons` | Статистика |
| `GET /api/list`, `GET /api/list/export.xlsx` | Список и экспорт |
| `GET /api/queue`, `GET /api/accuracy` | Очередь и точность |
| `GET/POST /api/settings`, `GET /api/health` | Настройки и здоровье |

## 6. Настройки

Хранятся в `storage/settings.json`, меняются на `/settings`: провайдер vision-модели (`ollama` / внешний / выкл.),
адрес и модель Ollama, размер картинки и тайм-аут, число потоков CPU для Ollama, разрешение внешнего API.
Переменная `VG_STORAGE` переопределяет папку `storage`.

## 7. Запуск

Нужны Python 3.11+ и (для фоновой проверки) Docker Desktop.

```powershell
.\run.ps1
```

Скрипт создаст `.venv`, поставит зависимости, поднимет Ollama в Docker, при первом запуске скачает модель (~3 ГБ) и
запустит сайт на `https://<IP-ноутбука>:8443`. Если запуск скриптов запрещён:
`powershell -ExecutionPolicy Bypass -File .\run.ps1`. Ключи: `-Http`, `-Port N`, `-NoDocker`.

Вручную:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d
docker exec vg-ollama ollama pull qwen2.5vl:3b
.\.venv\Scripts\python.exe -m visiongate            # HTTPS :8443
```

С телефона: телефон и ноутбук в одной сети, открыть `https://<IP-ноутбука>:8443`, подтвердить самоподписанный
сертификат. Временная ссылка в интернет: `powershell -ExecutionPolicy Bypass -File .\tunnel.ps1` (нужен
`cloudflared`; сайт защищён паролем, трафик идёт через Cloudflare).

## 8. Ограничения MVP

- Нет авторизации: рассчитан на доверенную локальную сеть (кроме режима туннеля с паролем).
- Один процесс: быстрые проверки и vision-модель идут по очереди, фоновая проверка медленная на CPU.
- Бесплатный хостинг (512 МБ RAM) не подходит: нужно минимум 4 vCPU и 8 ГБ RAM, для быстрой проверки экрана — GPU.
- Проверено на небольшом наборе кейсов; камера на телефонах отдельно не проверялась.

---

# English

An MVP for a Windows laptop without a GPU that works offline. A seller enters an IMEI (optional) and uploads or takes
with a phone camera two photos: the **box photo** and the **label scan**. Within seconds the system reads the IMEI from
barcodes and text, matches the numbers between the photos and with the entered one, and checks in the background
whether the photo shows another device's screen. There is batch checking with XLSX export and an admin panel with
statistics.

## 1. Features

- Registration form with a live camera, a guide overlay on the video and in-browser IMEI barcode reading.
- Fast phase (synchronous, a few seconds): Luhn check, barcodes, OCR, IMEI from text, number matching.
- Background phase: a local vision model in Ollama checks whether the photo is a picture of a screen.
- No-IMEI mode: the number is read from the photos and matched between them.
- Batch check ZIP → table → XLSX; a CLI for batch runs.
- Admin panel: overview, all submissions (search, filters, export), processing queue, rejection reasons, model
  accuracy.
- Submission review with manual decisions, model settings.
- RU/EN, light/dark theme, charts in plain SVG/JS (no CDN).
- HTTPS with a self-signed certificate for the phone camera on the LAN; a password-protected temporary link via
  Cloudflare Tunnel.
- External API for the vision model — off by default.

## 2. Tech stack

| Layer | Technologies |
| --- | --- |
| Backend | Python 3.11+ (3.13 recommended), FastAPI, Uvicorn, python-multipart |
| CV and OCR | OpenCV 5 (headless), Pillow, NumPy, RapidOCR (PP-OCRv3 on ONNX Runtime, CPU), zxing-cpp |
| Vision model | Qwen2.5-VL 3B (`qwen2.5vl:3b`) in Ollama (Docker); optional external API |
| Export | openpyxl |
| HTTPS | cryptography (self-signed certificate in `storage/certs`) |
| Frontend | Static HTML + plain JavaScript + CSS; zxing-wasm for in-browser barcode reading |
| Database | SQLite (`storage/visiongate.db`) |
| Infrastructure | Docker Compose (Ollama only), PowerShell scripts `run.ps1`, `tunnel.ps1`, Cloudflare Quick Tunnel |

## 3. How it works

```
Seller's phone ──HTTPS (LAN)──► FastAPI (Python)
  form, camera,                    │
  IMEI reading (zxing-wasm)        ├─ Fast phase (synchronous)
                                   │    • Luhn check of the entered IMEI
                                   │    • barcodes: zxing-cpp
                                   │    • OCR: RapidOCR (ONNX, CPU)
                                   │    • IMEI search and matching
                                   │    → decision or "manual review"
                                   │
                                   ├─ Background phase (queue)
                                   │    • vision model in Ollama: "photo of a screen?"
                                   │
                                   └─ SQLite: submissions, features, model answers, manual decisions
```

Statuses: approved, rejected (with a reason), manual review, preliminarily approved (background check running).
Principle: reject only on clear signs; when in doubt, manual review.

## 4. Project structure

```text
visiongate/
  __main__.py      server start (HTTPS :8443 or --http :8000)
  web.py           FastAPI: pages and API
  pipeline.py      fast phase
  decision.py      decision rules
  imei.py          IMEI search, Luhn, matching
  ocr.py, barcode.py, imaging.py   OCR, barcodes, images
  vlm.py, worker.py   vision model and background queue
  batch.py, exam.py, ingest.py, evidence.py, validation.py   batch checks, export, import
  dashboard.py     admin panel statistics
  db.py, certs.py, config.py   database, certificate, settings
static/            HTML pages, JS, CSS, vendor/zxing-wasm
tools/             eval.py, exam.py, import_dataset.py, probe_screen.py, serve_public.py
run.ps1, tunnel.ps1, docker-compose.yml, requirements.txt
storage/           database, uploads, settings, certificates, model cache (not in Git)
```

## 5. Pages and API

| Page | URL |
|---|---|
| Overview | `/` |
| New submission | `/new` |
| Result | `/s/<id>` |
| Batch check | `/batch` |
| All submissions | `/submissions` |
| Queue | `/queue` |
| Rejection reasons | `/reasons` |
| Model accuracy | `/accuracy` |
| Review | `/review` |
| Settings | `/settings` |

| Method and path | Purpose |
| --- | --- |
| `POST /api/submissions` | Create a submission (photos + optional IMEI) |
| `GET /api/submissions`, `GET /api/submissions/{id}` | List and one submission |
| `GET /api/submissions/{id}/photo/{slot}` | Submission photo |
| `POST /api/submissions/{id}/review` | Manual decision |
| `POST /api/batches`, `GET /api/batches/{job}`, `GET /api/batches/{job}/xlsx` | Batch check |
| `GET /api/stats/overview`, `GET /api/stats/reasons` | Statistics |
| `GET /api/list`, `GET /api/list/export.xlsx` | List and export |
| `GET /api/queue`, `GET /api/accuracy` | Queue and accuracy |
| `GET/POST /api/settings`, `GET /api/health` | Settings and health |

## 6. Settings

Stored in `storage/settings.json`, changed on `/settings`: vision model provider (`ollama` / external / off), Ollama
address and model, image size and timeout, CPU threads for Ollama, external API permission. The `VG_STORAGE` variable
overrides the `storage` folder.

## 7. Running

Requires Python 3.11+ and (for the background check) Docker Desktop.

```powershell
.\run.ps1
```

The script creates `.venv`, installs dependencies, starts Ollama in Docker, downloads the model on first run (~3 GB)
and starts the site at `https://<laptop-IP>:8443`. If script execution is blocked:
`powershell -ExecutionPolicy Bypass -File .\run.ps1`. Flags: `-Http`, `-Port N`, `-NoDocker`.

Manually:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d
docker exec vg-ollama ollama pull qwen2.5vl:3b
.\.venv\Scripts\python.exe -m visiongate            # HTTPS :8443
```

From a phone: same network, open `https://<laptop-IP>:8443`, accept the self-signed certificate. Temporary internet
link: `powershell -ExecutionPolicy Bypass -File .\tunnel.ps1` (needs `cloudflared`; the site is password-protected,
traffic goes through Cloudflare).

## 8. MVP limitations

- No authentication: designed for a trusted LAN (except the password-protected tunnel mode).
- One process: fast checks and the vision model run in turn; the background check is slow on CPU.
- Free hosting (512 MB RAM) does not fit: at least 4 vCPU and 8 GB RAM, a GPU for a fast screen check.
- Tested on a small set of cases; the camera was not separately tested on phones.
