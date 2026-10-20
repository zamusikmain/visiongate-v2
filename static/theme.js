// Тема до отрисовки страницы (без мигания): светлая по умолчанию, выбор хранится в localStorage
(function () {
  var t = "light";
  try { t = localStorage.getItem("vg_theme") || "light"; } catch (_) { /* приватный режим */ }
  if (t === "dark") document.documentElement.setAttribute("data-theme", "dark");
})();
