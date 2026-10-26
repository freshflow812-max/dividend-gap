const $ = (s) => document.querySelector(s);
const state = { upcoming: [], stats: null, chart: null, sort: {} };

// ---------- форматирование ----------
const nf = (d) => new Intl.NumberFormat("ru-RU", { maximumFractionDigits: d, minimumFractionDigits: d });
const fmtNum = (v, d = 2) => (v == null ? "—" : nf(d).format(v));
const fmtPct = (v, d = 1) => (v == null ? "—" : nf(d).format(v) + "%");
const fmtDate = (s) => (s ? s.split("-").reverse().join(".") : "—");
const fmtValue = (v) => (v == null ? "—" : nf(v < 1 ? 4 : 2).format(v));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const get = (obj, path) => path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
const daysUntil = (iso) => Math.round((new Date(iso) - new Date(new Date().toISOString().slice(0, 10))) / 864e5);

function rateClass(v) {
  if (v == null) return "";
  return v >= 75 ? "good" : v < 40 ? "bad" : "";
}

function lastEventBadge(ev) {
  if (!ev) return "—";
  if (ev.closed) return `<span class="badge good">закрыт за ${ev.days_to_close} дн</span>`;
  return `<span class="badge bad">открыт ${ev.days_open} дн, −${fmtNum(ev.remaining_pct, 1)}%</span>`;
}

// Статическая версия (python -m app.export_static) читает заранее выгруженные JSON вместо API.
const STATIC = !!window.DIVGAP_STATIC;
const staticPath = (path) =>
  path.startsWith("/api/ticker/") ? `data/ticker/${path.slice(12)}.json` : `data/${path.slice(5).split("?")[0]}.json`;

async function api(path, opts) {
  const r = await fetch(STATIC ? staticPath(path) : path, opts);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

// ---------- сортировка таблиц ----------
function setupSort(tableId, render) {
  const ths = document.querySelectorAll(`#${tableId} th[data-key]`);
  ths.forEach((th) =>
    th.addEventListener("click", () => {
      const cur = state.sort[tableId] || {};
      const dir = cur.key === th.dataset.key && cur.dir === "asc" ? "desc" : "asc";
      state.sort[tableId] = { key: th.dataset.key, dir };
      ths.forEach((t) => t.classList.remove("sorted-asc", "sorted-desc"));
      th.classList.add(`sorted-${dir}`);
      render();
    })
  );
}

function sortRows(tableId, rows) {
  const s = state.sort[tableId];
  if (!s) return rows;
  const mul = s.dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = get(a, s.key), y = get(b, s.key);
    if (x == null && y == null) return 0;
    if (x == null) return 1; // пустые всегда внизу
    if (y == null) return -1;
    return (x > y ? 1 : x < y ? -1 : 0) * mul;
  });
}

const matches = (row, q) => !q || row.secid.toLowerCase().includes(q) || (row.name || "").toLowerCase().includes(q);

// ---------- ближайшие дивиденды ----------
async function loadUpcoming() {
  const data = await api("/api/upcoming");
  state.upcoming = data.items;
  $("#last-update").textContent = data.last_update
    ? `данные от ${fmtDate(data.last_update.slice(0, 10))} ${data.last_update.slice(11, 16)}`
    : "данных пока нет — нажмите «Обновить данные»";
  renderUpcoming();
}

function renderUpcoming() {
  const q = $("#up-search").value.trim().toLowerCase();
  const horizon = +$("#up-horizon").value;
  const withForecast = $("#up-forecast").checked;
  const rows = sortRows(
    "up-table",
    state.upcoming.filter(
      (u) => matches(u, q) && (withForecast || !u.is_forecast) && (!horizon || daysUntil(u.registry_date) <= horizon)
    )
  );
  $("#up-table tbody").innerHTML =
    rows
      .map((u) => {
        const s = u.stats;
        const d = daysUntil(u.registry_date);
        return `<tr class="clickable" data-secid="${esc(u.secid)}">
          <td>${fmtDate(u.registry_date)}<span class="sub">${d === 0 ? "сегодня" : `через ${d} дн`}</span></td>
          <td>${fmtDate(u.cum_date_est)}</td>
          <td><b>${esc(u.secid)}</b><span class="sub">${esc(u.name)}</span></td>
          <td class="num">${fmtValue(u.value)}</td>
          <td class="num">${fmtPct(u.yield_pct, 2)}</td>
          <td>${u.is_forecast ? '<span class="badge warn">прогноз</span>' : '<span class="badge good">объявлен</span>'}</td>
          <td class="num">${s.events}</td>
          <td class="num ${rateClass(s.close_rate)}">${fmtPct(s.close_rate, 0)}</td>
          <td class="num ${rateClass(s.closed_within["30"])}">${fmtPct(s.closed_within["30"], 0)}</td>
          <td class="num">${s.median_days ?? "—"}</td>
        </tr>`;
      })
      .join("") || `<tr><td colspan="10" class="muted">Нет отсечек по выбранным фильтрам</td></tr>`;
}

// ---------- статистика ----------
async function loadStats() {
  if (!state.stats) state.stats = await api("/api/stats");
  renderOverall(state.stats.overall);
  renderStats();
}

function cards(items) {
  return items.map(([label, value]) => `<div class="card"><div class="label">${label}</div><div class="value">${value}</div></div>`).join("");
}

function renderOverall(o) {
  $("#overall-cards").innerHTML = cards([
    ["Всего гэпов", o.events],
    ["Закрыто", fmtPct(o.close_rate)],
    ["Закрыто ≤ 7 дн", fmtPct(o.closed_within["7"])],
    ["Закрыто ≤ 30 дн", fmtPct(o.closed_within["30"])],
    ["Закрыто ≤ 90 дн", fmtPct(o.closed_within["90"])],
    ["Закрыто ≤ года", fmtPct(o.closed_within["365"])],
    ["Медиана, дн", o.median_days ?? "—"],
    ["Средний гэп", fmtPct(o.avg_gap_pct, 2)],
  ]);
}

function renderStats() {
  const q = $("#st-search").value.trim().toLowerCase();
  const min = +$("#st-min").value || 0;
  const rows = sortRows("st-table", state.stats.tickers.filter((t) => matches(t, q) && t.events >= min));
  $("#st-table tbody").innerHTML =
    rows
      .map(
        (t) => `<tr class="clickable" data-secid="${esc(t.secid)}">
        <td><b>${esc(t.secid)}</b><span class="sub">${esc(t.name)}</span></td>
        <td>${esc(t.sector || "")}</td>
        <td class="num">${t.events}</td>
        <td class="num ${rateClass(t.close_rate)}">${fmtPct(t.close_rate, 0)}</td>
        ${["7", "30", "90", "365"].map((w) => `<td class="num">${fmtPct(t.closed_within[w], 0)}</td>`).join("")}
        <td class="num">${t.median_days ?? "—"}</td>
        <td class="num">${fmtPct(t.avg_gap_pct, 2)}</td>
        <td class="num">${fmtPct(t.avg_yield_pct, 2)}</td>
        <td>${t.last_event ? fmtDate(t.last_event.ex_date) + " " + lastEventBadge(t.last_event) : "—"}</td>
      </tr>`
      )
      .join("") || `<tr><td colspan="12" class="muted">Нет данных</td></tr>`;
}

// ---------- карточка акции ----------
async function openTicker(secid) {
  showView("ticker");
  history.replaceState(null, "", `#${secid}`);
  $("#tk-title").textContent = secid;
  const r = await api(`/api/ticker/${encodeURIComponent(secid)}`);
  const s = r.summary;
  $("#tk-title").innerHTML = `${esc(r.security.secid)} <span class="muted">${esc(r.security.name)} · ${esc(r.security.sector || "")}</span>`;
  $("#tk-cards").innerHTML = cards([
    ["Гэпов", s.events],
    ["Закрыто", fmtPct(s.close_rate)],
    ["≤ 30 дн", fmtPct(s.closed_within["30"])],
    ["≤ года", fmtPct(s.closed_within["365"])],
    ["Медиана, дн", s.median_days ?? "—"],
    ["Медиана, торг. дн", s.median_trading_days ?? "—"],
    ["Средний гэп", fmtPct(s.avg_gap_pct, 2)],
    ["Средняя доходность", fmtPct(s.avg_yield_pct, 2)],
  ]);
  $("#tk-splits").textContent = r.splits.length
    ? "Учтены сплиты/консолидации: " + r.splits.map((x) => `${fmtDate(x.date)} (×${x.factor >= 1 ? x.factor : "1/" + Math.round(1 / x.factor)})`).join(", ")
    : "";

  const today = new Date().toISOString().slice(0, 10);
  const future = r.dividends.filter((d) => d.registry_date >= today && d.value > 0);
  $("#tk-future tbody").innerHTML =
    future
      .map(
        (d) => `<tr><td>${fmtDate(d.registry_date)}</td><td>${fmtDate(estimateCum(d.registry_date))}</td>
        <td class="num">${fmtValue(d.value)}</td><td>${esc(d.period || "—")}</td>
        <td>${d.is_forecast ? '<span class="badge warn">прогноз</span>' : '<span class="badge good">объявлен ' + fmtDate(d.declared_date) + "</span>"}</td></tr>`
      )
      .join("") || `<tr><td colspan="5" class="muted">Нет объявленных или прогнозных выплат</td></tr>`;

  $("#tk-events tbody").innerHTML =
    r.events
      .map(
        (e) => `<tr><td>${fmtDate(e.registry_date)}</td><td>${fmtDate(e.cum_date)}</td>
        <td class="num">${fmtValue(e.value)}</td><td class="num">${fmtPct(e.div_yield_pct, 2)}</td>
        <td class="num">${fmtPct(e.gap_pct, 2)}</td><td class="num">${fmtValue(e.close_before)}</td>
        <td>${e.closed ? `<span class="badge good">${fmtDate(e.close_date)}</span>` : `<span class="badge bad">нет, −${fmtNum(e.remaining_pct, 1)}%</span>`}</td>
        <td class="num">${e.closed ? e.days_to_close : e.days_open + "+"}</td></tr>`
      )
      .join("") || `<tr><td colspan="8" class="muted">Нет истории</td></tr>`;

  drawChart(r);
}

// Та же логика, что gap.estimate_cum_date: T+1, только будни.
function estimateCum(iso) {
  const d = new Date(iso + "T00:00:00Z");
  while ([0, 6].includes(d.getUTCDay())) d.setUTCDate(d.getUTCDate() - 1);
  do d.setUTCDate(d.getUTCDate() - 1); while ([0, 6].includes(d.getUTCDay()));
  return d.toISOString().slice(0, 10);
}

function drawChart(r) {
  if (state.chart) state.chart.destroy();
  if (typeof Chart === "undefined") return;
  const css = getComputedStyle(document.documentElement);
  const color = (v) => css.getPropertyValue(v).trim();
  const idx = new Map(r.prices.map((p, i) => [p[0], i]));
  const labels = r.prices.map((p) => p[0]);
  const close = r.prices.map((p) => p[1]);
  const before = Array(labels.length).fill(null);
  const closedAt = Array(labels.length).fill(null);
  for (const e of r.events) {
    if (idx.has(e.cum_date)) before[idx.get(e.cum_date)] = e.close_before;
    if (e.closed && idx.has(e.close_date)) closedAt[idx.get(e.close_date)] = r.prices[idx.get(e.close_date)][1];
  }
  state.chart = new Chart($("#tk-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Цена закрытия", data: close, borderColor: color("--accent"), borderWidth: 1.5, pointRadius: 0, tension: 0 },
        { label: "Последний день с дивидендом", data: before, showLine: false, pointRadius: 4, pointBackgroundColor: color("--warn"), borderColor: color("--warn") },
        { label: "Гэп закрыт", data: closedAt, showLine: false, pointRadius: 4, pointStyle: "triangle", pointBackgroundColor: color("--good"), borderColor: color("--good") },
      ],
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: color("--muted") } } },
      scales: {
        x: { ticks: { color: color("--muted"), maxTicksLimit: 10 }, grid: { color: color("--border") } },
        y: { ticks: { color: color("--muted") }, grid: { color: color("--border") } },
      },
    },
  });
}

// ---------- навигация ----------
function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $(`#view-${name}`).classList.remove("hidden");
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
}

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => {
    history.replaceState(null, "", location.pathname);
    showView(t.dataset.view);
    if (t.dataset.view === "stats") loadStats();
  })
);
$("#back-btn").addEventListener("click", () => {
  history.replaceState(null, "", location.pathname);
  showView("upcoming");
});
document.addEventListener("click", (ev) => {
  const tr = ev.target.closest("tr[data-secid]");
  if (tr) openTicker(tr.dataset.secid);
});
["#up-search", "#up-horizon", "#up-forecast"].forEach((s) => $(s).addEventListener("input", renderUpcoming));
["#st-search", "#st-min"].forEach((s) => $(s).addEventListener("input", renderStats));
setupSort("up-table", renderUpcoming);
setupSort("st-table", renderStats);

$("#update-btn").hidden = STATIC;
$("#update-btn").addEventListener("click", async () => {
  const btn = $("#update-btn");
  btn.disabled = true;
  btn.textContent = "Обновляется…";
  await api("/api/update", { method: "POST" });
  const timer = setInterval(async () => {
    const st = await api("/api/update/status");
    if (!st.running) {
      clearInterval(timer);
      btn.disabled = false;
      btn.textContent = "Обновить данные";
      state.stats = null;
      loadUpcoming();
    }
  }, 5000);
});

function route() {
  if (location.hash.length > 1) openTicker(decodeURIComponent(location.hash.slice(1)));
}
window.addEventListener("hashchange", route);

loadUpcoming();
route();
