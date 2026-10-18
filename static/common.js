// Общие помощники для страниц + переключатель языка RU/EN
const I18N = {
  ru: {
    nav_register: "Регистрация", nav_batch: "Пакетная проверка", nav_review: "Разбор заявок", nav_settings: "Настройки",
    nav_report: "Отчёт по датасету",
    title_register: "Регистрация устройства", imei_label: "IMEI (15 цифр)", scan_btn: "📷 Считать штрихкод камерой",
    imei_hint: "Можно ввести IMEI1 или IMEI2. Сканер заполнит поле номером со штрихкода на этикетке.",
    slot1_title: "1. Фото коробки", slot1_hint: "Под углом: видны верх коробки с названием модели и боковая этикетка со штрихкодами и IMEI.",
    slot2_title: "2. Скан этикетки", slot2_hint: "Крупно: этикетка со штрихкодами IMEI1 и IMEI2 должна полностью помещаться в кадр, цифры — читаться.",
    take_photo: "📸 Сфотографировать", from_gallery: "🖼 Из галереи", submit: "Отправить на проверку",
    imei_digits: "Цифр: {n} из 15", imei_luhn_bad: "Ошибка в номере: не проходит проверку контрольной цифры",
    imei_ok: "✓ Номер корректный", check_imei: "Проверьте IMEI.", add_photos: "Добавьте оба фото.",
    checking: "Проверяем фото, обычно до 10 секунд…", scan_aim: "Наведите рамку на штрихкод IMEI", close: "Закрыть",
    scan_found: "Найден {code}, держите ровно…", no_camera: "Камера недоступна: откройте сайт по HTTPS",
    camera_denied: "Нет доступа к камере: ", replace_imei: "Со штрихкода считан IMEI {code}, а в поле — {cur}. Заменить?",
    submission: "Заявка №{id}", loading: "Загрузка…", new_registration: "← Новая регистрация",
    entered_imei: "Введённый IMEI", camera_read: "Считан камерой", fast_check: "Быстрая проверка", screen_check: "Проверка экрана",
    sec: "с", bg_check: "Фоновая проверка на фото экрана", in_queue: "в очереди", auto_refresh: "Страница обновится сама.",
    reviewer_decision: "Решение проверяющего", recognised_imei: "Распознанные IMEI", barcodes: "Штрихкоды",
    not_read: "не считан", match: "Совпадение", yes: "да", no: "нет", text: "текст", barcode: "штрихкод",
    slot_device: "Фото коробки", slot_scan: "Скан этикетки",
    st_ok: "OK", st_reject: "Отклонено", st_review: "На ручную проверку", approved: "Одобрено", rejected: "Отклонено",
    tab_todo: "Ждут разбора", tab_all: "Все", tab_prelim: "Предварительно", tab_review: "На ручную",
    col_no: "№", col_imei: "IMEI", col_status: "Статус", col_time: "Время", empty: "Пусто", pick_left: "Выберите заявку слева.",
    manual: "вручную", reason_for_reject: "Причина (для отклонения)", comment: "Комментарий", approve: "✓ Одобрить",
    reject: "✕ Отклонить", saved: "Сохранено", already: "Уже решено", seller_scanned: "Камера продавца считала штрихкод",
    batch_title: "Пакетная проверка", batch_hint: "ZIP с парами фото: в каждой папке device_*.jpg и scan_*.jpg, IMEI — в имени файла или папки (например Case_<IMEI>/device_<IMEI>.jpg). Если в архиве есть VALIDATION.xlsx, результаты сравниваются с эталоном.",
    batch_file: "ZIP-архив", batch_vlm: "Проверять фото экрана (VLM): ~3 мин на новую пару, уже проверенные фото — мгновенно из кэша",
    batch_start: "Запустить проверку", batch_progress: "Обработано {done} из {total}", batch_done: "Готово",
    download_xlsx: "⬇ Скачать XLSX", col_folder: "Папка", col_result: "Итог", col_reasons: "Причины",
    col_truth: "Эталон", col_agree: "Совпало", warnings: "Предупреждения", uploading: "Загружаем архив…",
    summary: "Итого", agree_count: "Авто-решений совпало с эталоном: {a} из {n}", false_app: "Ложных одобрений: {n}",
    false_rej: "Ложных отказов: {n}", error: "Ошибка",
    ev_size: "Размер", ev_text_imei: "IMEI из текста (Луна ✓)", ev_imei_lines: "Строки «IMEI»", ev_regions: "Области штрихкодов",
    ev_words: "Слова этикетки", ev_ui: "Интерфейс телефона", ev_lum: "Яркость", ev_time: "Время", ev_vlm: "VLM",
    edge: "край", at_edge: "есть у края", suspicion: "подозрение", screen: "экран", box_top: "верх коробки",
    not_run: "не запускалась", all_ocr: "Все строки OCR", ocr: "OCR",
    set_title: "Настройки", set_vlm: "Фоновая проверка «фото экрана»", set_model: "Модель",
    set_local: "Локальная (Ollama) — без интернета", set_ext: "Внешний API (Claude) — нужно согласование ИБ", set_off: "Выключена",
    set_local_hint: "Локальная модель на CPU отвечает примерно за 1,5 минуты на фото.",
    set_for_rejected: "Проверять и уже отклонённые заявки (точнее причина «фото экрана», но больше очередь)",
    set_require: "Без проверки экрана не одобрять (отправлять на ручную проверку)",
    set_ollama_url: "Адрес Ollama", set_ollama_model: "Модель Ollama", set_threads: "Потоков CPU для Ollama (0 — авто)",
    set_threads_hint: "Меньше потоков — быстрые проверки не тормозят во время фоновой проверки, но сама она идёт дольше.",
    set_ext_title: "Внешний API", set_ext_hint: "По умолчанию выключен: фото содержат GPS, отправку наружу нужно согласовать с ИБ. По коммерческим условиям Anthropic данные API по умолчанию не используются для обучения моделей. Ключ задаётся переменной окружения ANTHROPIC_API_KEY, нужен пакет anthropic.",
    set_ext_allowed: "Отправка фото во внешний API согласована с ИБ", save: "Сохранить",
    state: "Состояние", queue_len: "очередь фоновых проверок", ollama_ok: "Ollama доступна, модель загружена ✓",
    ollama_missing: "модель не найдена — выполните ollama pull",
  },
  en: {
    nav_register: "Register", nav_batch: "Batch check", nav_review: "Review queue", nav_settings: "Settings",
    nav_report: "Dataset report",
    title_register: "Device registration", imei_label: "IMEI (15 digits)", scan_btn: "📷 Scan barcode with camera",
    imei_hint: "You can enter IMEI1 or IMEI2. The scanner fills the field from the label barcode.",
    slot1_title: "1. Box photo", slot1_hint: "At an angle: the box top with the model name and the side label with barcodes and IMEI must be visible.",
    slot2_title: "2. Label scan", slot2_hint: "Close-up: the label with IMEI1 and IMEI2 barcodes must be fully in the frame and the digits readable.",
    take_photo: "📸 Take photo", from_gallery: "🖼 From gallery", submit: "Submit for check",
    imei_digits: "Digits: {n} of 15", imei_luhn_bad: "Invalid number: fails the check digit test",
    imei_ok: "✓ Number is valid", check_imei: "Please check the IMEI.", add_photos: "Please add both photos.",
    checking: "Checking photos, usually under 10 seconds…", scan_aim: "Point the frame at the IMEI barcode", close: "Close",
    scan_found: "Found {code}, hold still…", no_camera: "Camera unavailable: open the site over HTTPS",
    camera_denied: "No camera access: ", replace_imei: "Barcode IMEI is {code}, the field has {cur}. Replace?",
    submission: "Submission #{id}", loading: "Loading…", new_registration: "← New registration",
    entered_imei: "Entered IMEI", camera_read: "Read by camera", fast_check: "Fast check", screen_check: "Screen check",
    sec: "s", bg_check: "Background screen-photo check", in_queue: "in queue", auto_refresh: "The page refreshes automatically.",
    reviewer_decision: "Reviewer decision", recognised_imei: "Recognised IMEI", barcodes: "Barcodes",
    not_read: "not read", match: "Match", yes: "yes", no: "no", text: "text", barcode: "barcode",
    slot_device: "Box photo", slot_scan: "Label scan",
    st_ok: "OK", st_reject: "Rejected", st_review: "Manual review", approved: "Approved", rejected: "Rejected",
    tab_todo: "To review", tab_all: "All", tab_prelim: "Preliminary", tab_review: "Manual review",
    col_no: "#", col_imei: "IMEI", col_status: "Status", col_time: "Time", empty: "Empty", pick_left: "Select a submission on the left.",
    manual: "manual", reason_for_reject: "Reason (for rejection)", comment: "Comment", approve: "✓ Approve",
    reject: "✕ Reject", saved: "Saved", already: "Already decided", seller_scanned: "Seller's camera read barcode",
    batch_title: "Batch check", batch_hint: "ZIP with photo pairs: each folder has device_*.jpg and scan_*.jpg, the IMEI is in the file or folder name (e.g. Case_<IMEI>/device_<IMEI>.jpg). If the archive contains VALIDATION.xlsx, results are compared to the reference.",
    batch_file: "ZIP archive", batch_vlm: "Check for screen photos (VLM): ~3 min per new pair, already checked photos are instant from cache",
    batch_start: "Start check", batch_progress: "Processed {done} of {total}", batch_done: "Done",
    download_xlsx: "⬇ Download XLSX", col_folder: "Folder", col_result: "Result", col_reasons: "Reasons",
    col_truth: "Reference", col_agree: "Match", warnings: "Warnings", uploading: "Uploading archive…",
    summary: "Summary", agree_count: "Auto decisions matching reference: {a} of {n}", false_app: "False approvals: {n}",
    false_rej: "False rejections: {n}", error: "Error",
    ev_size: "Size", ev_text_imei: "IMEI from text (Luhn ✓)", ev_imei_lines: "“IMEI” lines", ev_regions: "Barcode regions",
    ev_words: "Label words", ev_ui: "Phone UI", ev_lum: "Brightness", ev_time: "Time", ev_vlm: "VLM",
    edge: "edge", at_edge: "some at the edge", suspicion: "suspected", screen: "screen", box_top: "box top",
    not_run: "not run", all_ocr: "All OCR lines", ocr: "OCR",
    set_title: "Settings", set_vlm: "Background screen-photo check", set_model: "Model",
    set_local: "Local (Ollama) — offline", set_ext: "External API (Claude) — needs InfoSec approval", set_off: "Disabled",
    set_local_hint: "The local model on CPU takes about 1.5 minutes per photo.",
    set_for_rejected: "Also check already rejected submissions (more precise screen-photo reason, longer queue)",
    set_require: "Do not approve without the screen check (send to manual review)",
    set_ollama_url: "Ollama URL", set_ollama_model: "Ollama model", set_threads: "CPU threads for Ollama (0 = auto)",
    set_threads_hint: "Fewer threads keep the fast check quick while the background check runs, but the background check takes longer.",
    set_ext_title: "External API", set_ext_hint: "Disabled by default: photos contain GPS, sending them out needs InfoSec approval. Under Anthropic's commercial terms API data is not used for model training by default. The key is read from ANTHROPIC_API_KEY; the anthropic package is required.",
    set_ext_allowed: "Sending photos to the external API is approved by InfoSec", save: "Save",
    state: "Status", queue_len: "background check queue", ollama_ok: "Ollama is available, model loaded ✓",
    ollama_missing: "model not found — run ollama pull",
  },
};

const VG = {
  lang: (() => { try { return localStorage.getItem("vg_lang") || "ru"; } catch (_) { return "ru"; } })(),
  t(key, params) {
    let s = (I18N[VG.lang] && I18N[VG.lang][key]) ?? I18N.ru[key] ?? key;
    for (const [k, v] of Object.entries(params || {})) s = s.replaceAll(`{${k}}`, v);
    return s;
  },
  // выбор поля по языку: message / message_en, status_ru / status_en, reasons_ru / reasons_en
  pick(obj, base) {
    if (!obj) return "";
    if (VG.lang === "en") return obj[`${base}_en`] ?? obj[base];
    return obj[`${base}_ru`] ?? obj[base];
  },
  setLang(l) {
    try { localStorage.setItem("vg_lang", l); } catch (_) { /* приватный режим */ }
    location.reload();
  },
  applyI18n(root = document) {
    document.documentElement.lang = VG.lang;
    root.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = VG.t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = VG.t(el.dataset.i18nPh); });
  },
  header(active) {
    const links = [["/", "nav_register"], ["/batch", "nav_batch"], ["/review", "nav_review"], ["/settings", "nav_settings"],
      ["/reports/eval_report.html", "nav_report"]];
    const h = document.querySelector("header");
    h.innerHTML = `<b>VisionGate</b>` + links.map(([href, k]) =>
      `<a href="${href}" class="${href === active ? "active" : ""}">${VG.t(k)}</a>`).join("") +
      `<span class="lang"><button type="button" data-l="ru" class="${VG.lang === "ru" ? "active" : ""}">RU</button>` +
      `<button type="button" data-l="en" class="${VG.lang === "en" ? "active" : ""}">EN</button></span>`;
    h.querySelectorAll(".lang button").forEach(b => b.onclick = () => VG.setLang(b.dataset.l));
  },
  luhn(s) {
    if (!/^\d+$/.test(s)) return false;
    let t = 0;
    [...s].reverse().forEach((ch, i) => { let d = +ch; if (i % 2) { d *= 2; if (d > 9) d -= 9; } t += d; });
    return t % 10 === 0;
  },
  validImei(s) { return s.length === 15 && VG.luhn(s); },
  digits(s) { return (s || "").replace(/\D/g, ""); },
  esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); },
  slotName(slot) { return VG.t(`slot_${slot}`); },
  slotStatus(st) { return VG.t(`st_${st}`); },
  badge(status, text, big) { return `<span class="badge s-${VG.esc(status)}${big ? " big-status" : ""}">${VG.esc(text)}</span>`; },
  async json(url, opts) {
    const r = await fetch(url, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `${VG.t("error")} ${r.status}`);
    return body;
  },
};
