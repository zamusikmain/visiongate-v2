// Форма регистрации: IMEI, два фото, сканер штрихкода с живой камеры
const files = { device: null, scan: null };
let clientBarcode = "";
const $ = s => document.querySelector(s);

// --- IMEI ---
const imeiInput = $("#imei");
// IMEI необязателен: пустое поле — нормально (номер прочитается с фото); введённый должен быть корректным
function checkImei() {
  const d = VG.digits(imeiInput.value);
  const el = $("#imeiCheck");
  if (!d) { el.textContent = VG.t("imei_empty_ok"); el.className = "check"; return true; }
  if (d.length !== 15) { el.textContent = VG.t("imei_digits", { n: d.length }); el.className = "check bad"; return false; }
  if (!VG.luhn(d)) { el.textContent = VG.t("imei_luhn_bad"); el.className = "check bad"; return false; }
  el.textContent = VG.t("imei_ok"); el.className = "check ok"; return true;
}
imeiInput.addEventListener("input", checkImei);
checkImei();

// --- фото: живая камера на странице или файл из галереи ---
function setPhoto(slot, f) {
  const card = document.querySelector(`[data-slot="${slot}"]`);
  files[slot] = f;
  const img = card.querySelector(".slot-preview");
  img.src = URL.createObjectURL(f);
  img.style.display = "block";
  card.querySelector(".check").textContent = `✓ ${f.name || "photo"} — ${(f.size / 1048576).toFixed(1)} MB`;
  card.querySelector(".check").className = "check ok";
}
document.querySelectorAll("[data-slot]").forEach(card => {
  const slot = card.dataset.slot;
  card.querySelector("[data-gallery]").addEventListener("change", e => {
    if (e.target.files[0]) setPhoto(slot, e.target.files[0]);
    e.target.value = "";  // можно выбрать тот же файл повторно
  });
  card.querySelector("[data-cam]").addEventListener("click", async () => {
    const f = await VGCamera.open(slot);
    if (f) setPhoto(slot, f);
  });
});
// из окна камеры (нет доступа / нет камеры) — сразу к выбору из галереи
VGCamera.onGallery = slot => document.querySelector(`[data-slot="${slot}"] [data-gallery]`).click();

// --- отправка ---
$("#form").addEventListener("submit", async e => {
  e.preventDefault();
  const st = $("#status");
  if (!checkImei()) { st.innerHTML = `<span class="err">${VG.t("check_imei")}</span>`; imeiInput.focus(); return; }
  if (!files.device || !files.scan) { st.innerHTML = `<span class="err">${VG.t("add_photos")}</span>`; return; }
  const fd = new FormData();
  fd.append("imei", VG.digits(imeiInput.value));
  fd.append("device", files.device);
  fd.append("scan", files.scan);
  fd.append("client_barcode", clientBarcode);
  $("#submit").disabled = true;
  st.innerHTML = `<span class="spinner"></span> ${VG.t("checking")}`;
  try {
    const r = await VG.json("/api/submissions", { method: "POST", body: fd });
    location.href = `/s/${r.id}`;
  } catch (err) {
    st.innerHTML = `<span class="err">${VG.esc(err.message)}</span>`;
    $("#submit").disabled = false;
  }
});

// --- сканер штрихкода: живое видео в полном разрешении, до водяного знака и сжатия ---
let stream = null, timer = null, lastSeen = "", zxingReady = null;

function prepareZxing() {
  if (!zxingReady && window.ZXingWASM) {
    zxingReady = ZXingWASM.prepareZXingModule({
      overrides: { locateFile: (p, prefix) => p.endsWith(".wasm") ? "/static/vendor/zxing-wasm/zxing_reader.wasm" : prefix + p },
      fireImmediately: true,
    });
  }
  return zxingReady;
}

async function detect(canvas) {
  // нативный BarcodeDetector (Android Chrome) быстрее; иначе — zxing-wasm (iOS Safari, десктоп)
  if ("BarcodeDetector" in window) {
    try {
      const det = new BarcodeDetector({ formats: ["code_128"] });
      return (await det.detect(canvas)).map(b => b.rawValue);
    } catch (_) { /* формат не поддержан — переходим на zxing */ }
  }
  await prepareZxing();
  const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height);
  const res = await ZXingWASM.readBarcodes(data, { formats: ["Code128"], tryHarder: true, maxNumberOfSymbols: 4 });
  return res.filter(r => r.isValid).map(r => r.text);
}

async function startScan() {
  if (!navigator.mediaDevices?.getUserMedia) { alert(VG.t("no_camera")); return; }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false,
    });
  } catch (err) { alert(VG.t("camera_denied") + err.message); return; }
  const video = $("#video");
  video.srcObject = stream;
  await video.play();
  $("#scanner").style.display = "flex";
  $("#scanMsg").textContent = VG.t("scan_aim");
  lastSeen = "";
  const canvas = document.createElement("canvas");
  const tick = async () => {
    if (!stream) return;
    const vw = video.videoWidth, vh = video.videoHeight;
    if (vw) {
      // центральная полоса кадра (как рамка на экране) в исходном разрешении камеры
      const y = Math.round(vh * 0.3), h = Math.round(vh * 0.4);
      canvas.width = vw; canvas.height = h;
      canvas.getContext("2d").drawImage(video, 0, y, vw, h, 0, 0, vw, h);
      try {
        const imeis = (await detect(canvas)).filter(t => /^\d{15}$/.test(t) && VG.luhn(t));
        if (imeis.length) {
          // принимаем номер только если он считан два кадра подряд
          if (imeis.includes(lastSeen)) { acceptScan(lastSeen); return; }
          lastSeen = imeis[0];
          $("#scanMsg").textContent = VG.t("scan_found", { code: lastSeen });
        }
      } catch (_) { /* кадр не распознан */ }
    }
    timer = setTimeout(tick, 200);
  };
  tick();
}

function stopScan() {
  clearTimeout(timer);
  stream?.getTracks().forEach(t => t.stop());
  stream = null;
  $("#scanner").style.display = "none";
}

function acceptScan(code) {
  stopScan();
  const cur = VG.digits(imeiInput.value);
  if (cur && cur !== code && !confirm(VG.t("replace_imei", { code, cur }))) return;
  imeiInput.value = code;
  clientBarcode = code;
  checkImei();
}

$("#scanBtn").addEventListener("click", startScan);
$("#scanClose").addEventListener("click", stopScan);
