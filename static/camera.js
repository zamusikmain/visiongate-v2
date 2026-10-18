// Живая камера на странице: превью, шаблон-подсказка, «Снять» / «Переснять», переключение камер.
// Шаблон (SVG) лежит поверх видео и в снимок не попадает: кадр берётся из видеопотока / ImageCapture.
const VGCamera = (() => {
  // Уголки-ориентиры (как в сканерах документов). Пропорции фиксированы viewBox + meet, поэтому
  // в горизонтальном и вертикальном кадре рамка одинаковой формы; отступ от краёв кадра ~12% (fitOverlay).
  const corners = (w, h, a) =>
    `<g class="ov-corner"><path d="M0 ${a} V0 H${a}"/><path d="M${w - a} 0 H${w} V${a}"/>` +
    `<path d="M${w} ${h - a} V${h} H${w - a}"/><path d="M${a} ${h} H0 V${h - a}"/></g>`;
  const OVERLAYS = {
    // Фото коробки: рамка 4:3, сверху подпись про верх коробки, внизу узкая зона под этикетку
    device: `
      <svg viewBox="-2 -2 164 124" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        ${corners(160, 120, 18)}
        <text x="80" y="16" class="ov-caption" font-size="6.5" data-k="ov_device_top"></text>
        <rect x="10" y="92" width="140" height="18" rx="2" class="ov-zone"/>
        <text x="80" y="103.5" class="ov-caption" font-size="6" data-k="ov_device_label"></text>
      </svg>`,
    // Скан этикетки: рамка 2:1, этикетка с блоком IMEI1/IMEI2 должна целиком поместиться внутри
    scan: `
      <svg viewBox="-2 -2 164 84" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        ${corners(160, 80, 16)}
        <text x="80" y="43" class="ov-caption" font-size="5.6" data-k="ov_scan"></text>
      </svg>`,
  };

  let stream = null, facing = "environment", deviceIds = [], resolveFn = null, slot = null, shot = null;
  const $ = s => document.querySelector(s);

  function build() {
    if ($("#cam")) return;
    const el = document.createElement("div");
    el.id = "cam";
    el.innerHTML = `
      <div class="cam-stage">
        <video id="camVideo" playsinline muted autoplay></video>
        <img id="camShot" alt="">
        <div id="camOverlay"></div>
        <div id="camMsg" class="cam-msg"></div>
      </div>
      <div class="cam-bar">
        <button type="button" id="camClose">${VG.t("close")}</button>
        <button type="button" id="camSwitch" title="${VG.t("cam_switch")}" hidden>🔄 ${VG.t("cam_switch")}</button>
        <button type="button" id="camGallery" hidden>${VG.t("from_gallery")}</button>
        <button type="button" id="camRetake" hidden>${VG.t("cam_retake")}</button>
        <button type="button" id="camUse" class="cam-primary" hidden>${VG.t("cam_use")}</button>
        <button type="button" id="camShoot" class="cam-shutter" aria-label="${VG.t("cam_shoot")}"></button>
      </div>`;
    document.body.appendChild(el);
    $("#camClose").onclick = () => finish(null);
    $("#camShoot").onclick = capture;
    $("#camRetake").onclick = retake;
    $("#camUse").onclick = () => finish(shot);
    $("#camSwitch").onclick = switchCamera;
    $("#camGallery").onclick = () => { const s = slot; finish(null); VGCamera.onGallery && VGCamera.onGallery(s); };
  }

  function setMode(m) {  // live | shot | error
    $("#camVideo").style.display = m === "live" ? "" : "none";
    $("#camShot").style.display = m === "shot" ? "" : "none";
    $("#camOverlay").style.display = m === "live" ? "" : "none";
    $("#camShoot").hidden = m !== "live";
    $("#camRetake").hidden = m !== "shot";
    $("#camUse").hidden = m !== "shot";
    $("#camGallery").hidden = m !== "error";
    $("#camSwitch").hidden = m !== "live" || deviceIds.length < 2;
  }

  function errorText(err) {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) return VG.t("cam_need_https");
    const n = err && err.name;
    if (n === "NotAllowedError" || n === "SecurityError") return VG.t("cam_denied");
    if (n === "NotFoundError" || n === "OverconstrainedError") return VG.t("cam_none");
    if (n === "NotReadableError") return VG.t("cam_busy");
    return VG.t("cam_error") + (err && err.message ? `: ${err.message}` : "");
  }

  function showError(err) {
    setMode("error");
    $("#camMsg").textContent = errorText(err);
    $("#camMsg").style.display = "flex";
  }

  // шаблон — точно поверх видимой части кадра (видео вписано с полями, object-fit: contain)
  function fitOverlay() {
    const v = $("#camVideo"), ov = $("#camOverlay"), stage = v.parentElement;
    if (!v.videoWidth) return;
    const cw = stage.clientWidth, ch = stage.clientHeight;
    const k = Math.min(cw / v.videoWidth, ch / v.videoHeight);
    const w = v.videoWidth * k, h = v.videoHeight * k;
    Object.assign(ov.style, { left: `${(cw - w) / 2}px`, top: `${(ch - h) / 2}px`, width: `${w}px`, height: `${h}px`,
      padding: `${h * 0.12}px ${w * 0.12}px` });  // отступ ~12% от каждой стороны кадра
  }
  window.addEventListener("resize", fitOverlay);

  async function startStream(constraint) {
    stop();
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: Object.assign({ width: { ideal: 3840 }, height: { ideal: 2160 } }, constraint),
    });
    const v = $("#camVideo");
    v.onloadedmetadata = v.onresize = fitOverlay;
    v.srcObject = stream;
    await v.play().catch(() => {});
    fitOverlay();
    const s = stream.getVideoTracks()[0].getSettings();
    if (s.facingMode) facing = s.facingMode;
    // кнопка переключения — только если камер больше одной (метки доступны после разрешения)
    try {
      deviceIds = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "videoinput").map(d => d.deviceId);
    } catch (_) { deviceIds = []; }
    $("#camSwitch").hidden = deviceIds.length < 2;
  }

  async function switchCamera() {
    const track = stream && stream.getVideoTracks()[0];
    const s = track ? track.getSettings() : {};
    try {
      if (s.facingMode) {
        // телефон: передняя ↔ задняя
        await startStream({ facingMode: { exact: facing === "user" ? "environment" : "user" } });
      } else {
        // ноутбук: камеры без facingMode — по кругу по deviceId
        const i = deviceIds.indexOf(s.deviceId);
        await startStream({ deviceId: { exact: deviceIds[(i + 1) % deviceIds.length] } });
      }
    } catch (err) {
      try { await startStream({ facingMode: { ideal: facing } }); } catch (e) { showError(e); }
    }
  }

  async function grab() {
    const track = stream.getVideoTracks()[0];
    // ImageCapture (Chrome/Android) даёт полное разрешение сенсора; иначе — кадр видео
    if (window.ImageCapture) {
      try {
        const blob = await new ImageCapture(track).takePhoto();
        if (blob && blob.size) return blob;
      } catch (_) { /* не поддерживается этой камерой */ }
    }
    const v = $("#camVideo");
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    return await new Promise(res => c.toBlob(res, "image/jpeg", 0.92));
  }

  async function capture() {
    if (!stream) return;
    $("#camShoot").disabled = true;
    try {
      const blob = await grab();
      shot = new File([blob], `${slot}_${Date.now()}.jpg`, { type: blob.type || "image/jpeg" });
      $("#camShot").src = URL.createObjectURL(shot);
      setMode("shot");
    } catch (err) { showError(err); }
    $("#camShoot").disabled = false;
  }

  function retake() { shot = null; setMode("live"); }

  function stop() {
    stream && stream.getTracks().forEach(t => t.stop());
    stream = null;
  }

  function finish(file) {
    stop();
    $("#cam").style.display = "none";
    document.body.style.overflow = "";
    const r = resolveFn; resolveFn = null;
    r && r(file);
  }

  return {
    onGallery: null,
    /** Открывает камеру для слота device|scan. Возвращает File или null (закрыли / ошибка). */
    async open(forSlot) {
      build();
      slot = forSlot; shot = null;
      $("#camOverlay").innerHTML = OVERLAYS[forSlot] || "";
      $("#camOverlay").querySelectorAll("[data-k]").forEach(t => { t.textContent = VG.t(t.dataset.k); });
      $("#camMsg").style.display = "none";
      $("#cam").style.display = "flex";
      document.body.style.overflow = "hidden";
      setMode("live");
      const done = new Promise(res => { resolveFn = res; });
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) { showError(null); return done; }
      try {
        // по умолчанию — задняя камера (на ноутбуке ideal просто возьмёт единственную)
        await startStream({ facingMode: { ideal: "environment" } });
      } catch (err) { showError(err); }
      return done;
    },
  };
})();
