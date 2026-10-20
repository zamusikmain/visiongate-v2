// Общие помощники для страниц + переключатель языка RU/EN
const I18N = {
  ru: {
    nav_overview: "Обзор", nav_new: "Новая заявка", nav_all: "Все заявки", nav_queue: "Очередь обработки",
    nav_reasons: "Причины отказов",
    b_approved: "Approved", b_rejected: "Rejected", b_review: "Needs review", b_processing: "В обработке",
    r_INVALID_IMEI: "Неверный IMEI (Луна)", r_PHOTO_OF_SCREEN: "Фото экрана", r_IMEI_MISMATCH: "IMEI не совпадает",
    r_NO_SERIAL: "Нет наклейки с IMEI", r_CROPPED: "Наклейка обрезана", r_BLURRY_DARK_UNREADABLE: "Размыто / темно / нечитаемо",
    r_DUPLICATE: "Одно фото в обоих слотах",
    ov_title: "Обзор", ov_sub: "Сводка по проверкам фото коробок", k_total: "Всего заявок", k_processing_sub: "идёт проверка экрана",
    ch_daily: "Заявки по дням", ch_received: "Поступило", ch_processed: "Обработано", ch_summary: "Итоги",
    ch_reasons: "Топ причин отказа", ch_metrics: "Средние метрики", m_fast: "быстрая проверка, с", m_vlm: "проверка экрана, с",
    m_high: "решений с high confidence", ch_recent: "Последние заявки", all_link: "Все заявки →",
    col_id: "ID", col_model: "Модель", col_date: "Дата", col_conf: "Уверенность", col_source: "Режим",
    empty_title: "Пока нет данных", empty_hint: "Отправьте заявку или загрузите пакет — статистика появится здесь.",
    empty_reasons: "Отказов пока нет", src_single: "Одиночная", src_batch: "Пакет", src_exam: "exam.py", src_import: "Импорт",
    f_search: "Поиск по ID или IMEI", f_status: "Статус", f_reason: "Причина", f_source: "Режим", f_from: "С даты", f_to: "По дату",
    any: "Все", reset: "Сбросить", export_xlsx: "⬇ Экспорт в XLSX", found_n: "Найдено: {n}", prev: "← Назад", next: "Вперёд →",
    card_title: "Заявка №{id}", errors: "Найденные ошибки", timings: "Тайминги", vlm_state: "Проверка экрана",
    open_review: "Открыть в разборе", open_in_list: "Открыть в списке заявок", close_x: "Закрыть",
    q_title: "Очередь обработки", q_sub: "Заявки с незавершённой фоновой проверкой на фото экрана. Обновление каждые 5 с.",
    q_empty: "Очередь пуста", q_empty_hint: "Все заявки обработаны.", q_running: "проверяется", q_waiting: "в очереди",
    q_pos: "Позиция", q_wait: "Ожидание", rs_title: "Причины отказов", rs_sub: "Разбивка по типам ошибок; клик — список заявок с этой причиной.",
    rs_share: "Доля от отклонённых", rs_trend: "Динамика", per_day: "по дням", days_n: "{n} дн.", minutes_short: "мин",
    sc_passed: "пройдена", sc_not_run: "не выполнялась", sc_suspected: "подозрение на экран", sc_failed: "ошибка проверки",
    sc_ui_detected: "интерфейс телефона найден", conf_high: "high", conf_low: "low",
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
    st_ok: "OK", st_reject: "Отклонено", st_review: "На ручную проверку", st_unchecked: "Не проверено на фото экрана", st_pending: "Проверяется на фото экрана", approved: "Одобрено", rejected: "Отклонено",
    tab_todo: "Ждут разбора", tab_all: "Все", tab_prelim: "Предварительно", tab_review: "На ручную",
    col_no: "№", col_imei: "IMEI", col_status: "Статус", col_time: "Время", empty: "Пусто", pick_left: "Выберите заявку слева.",
    manual: "вручную", reason_for_reject: "Причина (для отклонения)", comment: "Комментарий", approve: "✓ Одобрить",
    reject: "✕ Отклонить", saved: "Сохранено", already: "Уже решено", seller_scanned: "Камера продавца считала штрихкод",
    batch_title: "Пакетная проверка", batch_hint: "ZIP с парами фото: в каждой папке один файл device*.jpg (фото коробки) и один scan*.jpg (скан этикетки); если пар в папке несколько — окончания имён должны совпадать (device_1.jpg ↔ scan_1.jpg). IMEI в именах не нужен: он читается с фото. Если в архиве есть VALIDATION.xlsx, результаты сравниваются с эталоном.",
    batch_file: "ZIP-архив", batch_vlm: "Проверять фото экрана (VLM): ~3 мин на новую пару, уже проверенные фото — мгновенно из кэша",
    batch_start: "Запустить проверку", batch_progress: "Обработано {done} из {total}", batch_done: "Готово",
    download_xlsx: "⬇ Скачать XLSX (подробный)", download_validation: "⬇ XLSX в формате VALIDATION (Approved/Rejected)", col_folder: "Папка", col_result: "Итог", col_reasons: "Причины",
    col_truth: "Эталон", col_agree: "Совпало", warnings: "Предупреждения", uploading: "Загружаем архив…",
    summary: "Итого", agree_count: "Авто-решений совпало с эталоном: {a} из {n}", false_app: "Ложных одобрений: {n}",
    false_rej: "Ложных отказов: {n}", error: "Ошибка",
    ev_size: "Размер", ev_text_imei: "IMEI из текста (Луна ✓)", ev_imei_lines: "Строки «IMEI»", ev_regions: "Области штрихкодов",
    ev_words: "Слова этикетки", ev_ui: "Интерфейс телефона", ev_lum: "Яркость", ev_time: "Время", ev_vlm: "VLM",
    edge: "край", at_edge: "есть у края", suspicion: "подозрение", screen: "экран", box_top: "верх коробки",
    not_run: "не запускалась", all_ocr: "Все строки OCR", ocr: "OCR",
    ev_top: "Надпись «Galaxy» (верх коробки)", hint_only: "подсказка, в решении не участвует",
    imei_label_opt: "IMEI (необязательно)", imei_hint_opt: "Можно не вводить: система прочитает IMEI со штрихкода и текста на фото и проверит, что на обоих фото один и тот же номер. Если ввести (IMEI1 или IMEI2) — дополнительно сверит с ним.",
    imei_empty_ok: "Поле пустое — IMEI будет прочитан с фото", cam_switch: "Сменить камеру", cam_retake: "Переснять",
    cam_use: "Использовать фото", cam_shoot: "Снять",
    cam_need_https: "Камера недоступна: браузер разрешает её только по HTTPS (или на localhost). Откройте сайт по https:// или выберите фото из галереи.",
    cam_denied: "Доступ к камере запрещён. Разрешите камеру в настройках браузера для этого сайта или выберите фото из галереи.",
    cam_none: "Камера не найдена. Подключите камеру или выберите фото из галереи.",
    cam_busy: "Камера занята другим приложением. Закройте его или выберите фото из галереи.",
    cam_error: "Не удалось включить камеру", ov_device_top: "Верх коробки с названием модели",
    ov_device_label: "Этикетка со штрихкодами", ov_scan: "Этикетка с IMEI1/IMEI2 целиком в рамке",
    imei_from_photo: "IMEI (прочитан с фото)", imei_not_found: "не найден на фото", use_name_imei: "Сверять с IMEI из имени файла или папки (если есть)",
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
    nav_overview: "Overview", nav_new: "New submission", nav_all: "All submissions", nav_queue: "Processing queue",
    nav_reasons: "Rejection reasons",
    b_approved: "Approved", b_rejected: "Rejected", b_review: "Needs review", b_processing: "Processing",
    r_INVALID_IMEI: "Invalid IMEI (Luhn)", r_PHOTO_OF_SCREEN: "Screen photo", r_IMEI_MISMATCH: "IMEI mismatch",
    r_NO_SERIAL: "No IMEI label", r_CROPPED: "Label cropped", r_BLURRY_DARK_UNREADABLE: "Blurry / dark / unreadable",
    r_DUPLICATE: "Same photo in both slots",
    ov_title: "Overview", ov_sub: "Box photo verification summary", k_total: "Total submissions", k_processing_sub: "screen check running",
    ch_daily: "Submissions per day", ch_received: "Received", ch_processed: "Processed", ch_summary: "Summary",
    ch_reasons: "Top rejection reasons", ch_metrics: "Average metrics", m_fast: "fast check, s", m_vlm: "screen check, s",
    m_high: "high-confidence decisions", ch_recent: "Latest submissions", all_link: "All submissions →",
    col_id: "ID", col_model: "Model", col_date: "Date", col_conf: "Confidence", col_source: "Mode",
    empty_title: "No data yet", empty_hint: "Submit a check or upload a batch — statistics will appear here.",
    empty_reasons: "No rejections yet", src_single: "Single", src_batch: "Batch", src_exam: "exam.py", src_import: "Import",
    f_search: "Search by ID or IMEI", f_status: "Status", f_reason: "Reason", f_source: "Mode", f_from: "From", f_to: "To",
    any: "All", reset: "Reset", export_xlsx: "⬇ Export to XLSX", found_n: "Found: {n}", prev: "← Prev", next: "Next →",
    card_title: "Submission #{id}", errors: "Errors found", timings: "Timings", vlm_state: "Screen check",
    open_review: "Open in review", open_in_list: "Open in submissions list", close_x: "Close",
    q_title: "Processing queue", q_sub: "Submissions with an unfinished background screen-photo check. Refreshes every 5 s.",
    q_empty: "Queue is empty", q_empty_hint: "All submissions are processed.", q_running: "checking", q_waiting: "waiting",
    q_pos: "Position", q_wait: "Waiting", rs_title: "Rejection reasons", rs_sub: "Breakdown by error type; click to list submissions with this reason.",
    rs_share: "Share of rejected", rs_trend: "Trend", per_day: "per day", days_n: "{n} days", minutes_short: "min",
    sc_passed: "passed", sc_not_run: "not run", sc_suspected: "screen suspected", sc_failed: "check failed",
    sc_ui_detected: "phone UI detected", conf_high: "high", conf_low: "low",
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
    st_ok: "OK", st_reject: "Rejected", st_review: "Manual review", st_unchecked: "Not checked for screen photo", st_pending: "Screen-photo check in progress", approved: "Approved", rejected: "Rejected",
    tab_todo: "To review", tab_all: "All", tab_prelim: "Preliminary", tab_review: "Manual review",
    col_no: "#", col_imei: "IMEI", col_status: "Status", col_time: "Time", empty: "Empty", pick_left: "Select a submission on the left.",
    manual: "manual", reason_for_reject: "Reason (for rejection)", comment: "Comment", approve: "✓ Approve",
    reject: "✕ Reject", saved: "Saved", already: "Already decided", seller_scanned: "Seller's camera read barcode",
    batch_title: "Batch check", batch_hint: "ZIP with photo pairs: each folder has one device*.jpg (box photo) and one scan*.jpg (label scan); with several pairs in a folder the name endings must match (device_1.jpg ↔ scan_1.jpg). No IMEI is needed in the names: it is read from the photos. If the archive contains VALIDATION.xlsx, results are compared to the reference.",
    batch_file: "ZIP archive", batch_vlm: "Check for screen photos (VLM): ~3 min per new pair, already checked photos are instant from cache",
    batch_start: "Start check", batch_progress: "Processed {done} of {total}", batch_done: "Done",
    download_xlsx: "⬇ Download XLSX (detailed)", download_validation: "⬇ XLSX in VALIDATION format (Approved/Rejected)", col_folder: "Folder", col_result: "Result", col_reasons: "Reasons",
    col_truth: "Reference", col_agree: "Match", warnings: "Warnings", uploading: "Uploading archive…",
    summary: "Summary", agree_count: "Auto decisions matching reference: {a} of {n}", false_app: "False approvals: {n}",
    false_rej: "False rejections: {n}", error: "Error",
    ev_size: "Size", ev_text_imei: "IMEI from text (Luhn ✓)", ev_imei_lines: "“IMEI” lines", ev_regions: "Barcode regions",
    ev_words: "Label words", ev_ui: "Phone UI", ev_lum: "Brightness", ev_time: "Time", ev_vlm: "VLM",
    edge: "edge", at_edge: "some at the edge", suspicion: "suspected", screen: "screen", box_top: "box top",
    not_run: "not run", all_ocr: "All OCR lines", ocr: "OCR",
    ev_top: "“Galaxy” text (box top)", hint_only: "hint only, not used in the decision",
    imei_label_opt: "IMEI (optional)", imei_hint_opt: "You can leave it empty: the system reads the IMEI from the barcode and text in the photos and checks that both photos show the same number. If you enter it (IMEI1 or IMEI2), it is also compared.",
    imei_empty_ok: "Empty — the IMEI will be read from the photos", cam_switch: "Switch camera", cam_retake: "Retake",
    cam_use: "Use photo", cam_shoot: "Take photo",
    cam_need_https: "Camera unavailable: browsers allow it only over HTTPS (or on localhost). Open the site via https:// or pick a photo from the gallery.",
    cam_denied: "Camera access is blocked. Allow the camera for this site in the browser settings or pick a photo from the gallery.",
    cam_none: "No camera found. Connect a camera or pick a photo from the gallery.",
    cam_busy: "The camera is used by another app. Close it or pick a photo from the gallery.",
    cam_error: "Could not start the camera", ov_device_top: "Box top with the model name",
    ov_device_label: "Label with barcodes", ov_scan: "Whole IMEI1/IMEI2 label inside the frame",
    imei_from_photo: "IMEI (read from photo)", imei_not_found: "not found in the photos", use_name_imei: "Compare with the IMEI in the file or folder name (if any)",
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
  // Единый макет: левое меню (на телефоне — сворачиваемое), бренд, RU/EN
  header(active) {
    const ic = {
      overview: '<path d="M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z"/>',
      new: '<path d="M12 5v14M5 12h14"/><rect x="3" y="3" width="18" height="18" rx="3"/>',
      batch: '<path d="M4 7h16M4 12h16M4 17h10"/>',
      list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
      queue: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
      reasons: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    };
    const nav = [["/", "overview", "nav_overview"], ["/new", "new", "nav_new"], ["/batch", "batch", "nav_batch"],
      ["/submissions", "list", "nav_all"], ["/queue", "queue", "nav_queue"], ["/reasons", "reasons", "nav_reasons"]];
    const sub = [["/review", "nav_review"], ["/settings", "nav_settings"], ["/reports/eval_report.html", "nav_report"]];
    const h = document.querySelector("header");
    h.innerHTML =
      `<a class="brand" href="/"><span class="logo">V</span><span><b>VisionGate</b><small>Photo verification</small></span></a>` +
      `<button type="button" class="burger" aria-label="menu">☰</button>` +
      `<nav>${nav.map(([href, i, k]) => `<a href="${href}" class="${href === active ? "active" : ""}">` +
        `<svg viewBox="0 0 24 24">${ic[i]}</svg>${VG.t(k)}${i === "queue" ? '<span class="count" id="navQueue" hidden></span>' : ""}</a>`).join("")}</nav>` +
      `<div class="sub">${sub.map(([href, k]) => `<a href="${href}" class="${href === active ? "active" : ""}">${VG.t(k)}</a>`).join("")}` +
      `<span class="lang"><button type="button" data-l="ru" class="${VG.lang === "ru" ? "active" : ""}">RU</button>` +
      `<button type="button" data-l="en" class="${VG.lang === "en" ? "active" : ""}">EN</button></span></div>`;
    h.querySelectorAll(".lang button").forEach(b => b.onclick = () => VG.setLang(b.dataset.l));
    h.querySelector(".burger").onclick = () => h.classList.toggle("open");
    // счётчик очереди фоновой проверки в меню
    fetch("/api/queue").then(r => r.json()).then(q => {
      const el = document.getElementById("navQueue");
      if (el && q.rows && q.rows.length) { el.textContent = q.rows.length; el.hidden = false; }
    }).catch(() => {});
  },
  maskImei(v) { return !v || v.length < 8 ? (v || "") : v.slice(0, 2) + "x".repeat(v.length - 6) + v.slice(-4); },
  reasonLabel(code) { return VG.t(`r_${code}`) === `r_${code}` ? code : VG.t(`r_${code}`); },
  bucketLabel(b) { return VG.t(`b_${b}`); },
  fmtDate(ts) { return (ts || "").replace("T", " ").slice(0, 16); },
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
  // «OK» показываем только если слот прошёл проверку на фото экрана
  slotView(d, pending) {
    if (d && d.status === "ok" && (d.screen_check || "passed") !== "passed") return pending ? "pending" : "unchecked";
    return d ? d.status : "";
  },
  badge(status, text, big) { return `<span class="badge s-${VG.esc(status)}${big ? " big-status" : ""}">${VG.esc(text)}</span>`; },
  async json(url, opts) {
    const r = await fetch(url, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `${VG.t("error")} ${r.status}`);
    return body;
  },
};
