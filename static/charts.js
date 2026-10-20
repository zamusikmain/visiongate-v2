// Графики на чистом SVG (без библиотек и CDN). Цвета — CSS-переменные темы (через style, не атрибуты)
const VGChart = {
  // Столбики по дням: две серии рядом (поступило / обработано)
  daily(el, data, colors = ["var(--c-received)", "var(--c-processed)"]) {
    const W = 720, H = 220, pl = 30, pr = 8, pt = 10, pb = 26;
    const max = Math.max(1, ...data.flatMap(d => [d.received, d.processed]));
    const step = Math.max(1, Math.ceil(max / 4));
    const top = step * 4;
    const cw = (W - pl - pr) / data.length, bw = Math.max(3, Math.min(14, cw / 2 - 3));
    const y = v => pt + (H - pt - pb) * (1 - v / top);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    for (let i = 0; i <= 4; i++) {
      const v = step * i, yy = y(v);
      s += `<line x1="${pl}" x2="${W - pr}" y1="${yy}" y2="${yy}" style="stroke:var(--chart-grid)"/><text x="${pl - 6}" y="${yy + 4}" text-anchor="end">${v}</text>`;
    }
    data.forEach((d, i) => {
      const cx = pl + cw * i + cw / 2;
      [[d.received, colors[0], -bw - 1], [d.processed, colors[1], 1]].forEach(([v, c, off]) => {
        if (v > 0) s += `<rect x="${cx + off}" y="${y(v)}" width="${bw}" height="${y(0) - y(v)}" rx="2" style="fill:${c}"><title>${d.day}: ${v}</title></rect>`;
      });
      const every = Math.ceil(data.length / 10);
      if (i % every === 0 || i === data.length - 1)
        s += `<text x="${cx}" y="${H - 8}" text-anchor="middle">${d.day.slice(8, 10)}.${d.day.slice(5, 7)}</text>`;
    });
    el.innerHTML = s + "</svg>";
  },
  // Маленький график-линия для динамики причины
  spark(values, color = "var(--c-processed)") {
    const W = 140, H = 30, max = Math.max(1, ...values);
    const pts = values.map((v, i) => `${(i / Math.max(1, values.length - 1)) * (W - 2) + 1},${H - 2 - (v / max) * (H - 6)}`).join(" ");
    return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><polyline points="${pts}" fill="none" style="stroke:${color}" stroke-width="1.6"/>` +
      values.map((v, i) => v ? `<circle cx="${(i / Math.max(1, values.length - 1)) * (W - 2) + 1}" cy="${H - 2 - (v / max) * (H - 6)}" r="1.8" style="fill:${color}"/>` : "").join("") + "</svg>";
  },
  // Горизонтальные столбики: [{label, value, href, color}]
  hbars(items, total) {
    const max = Math.max(1, ...items.map(i => i.value));
    return `<div class="bars">${items.map(i => {
      const tag = i.href ? "a" : "div";
      return `<${tag} class="bar-row" ${i.href ? `href="${i.href}"` : ""}><span>${VG.esc(i.label)}</span>` +
        `<span class="bar-track"><div style="width:${(100 * i.value / (total || max)).toFixed(1)}%;background:${i.color || "var(--accent)"}"></div></span>` +
        `<span class="num">${i.suffix ? i.value + i.suffix : i.value}</span></${tag}>`;
    }).join("")}</div>`;
  },
};
const BUCKET_COLOR = { approved: "var(--c-approved)", rejected: "var(--c-rejected)", review: "var(--c-review)",
  processing: "var(--c-processing)" };
