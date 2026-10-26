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

// ---------- пояснения к заголовкам ----------
const PERIOD_NOTE =
  "Считается по всем прошлым отсечкам этой акции, для которых есть котировки (обычно с 2008–2011 года по сегодня). Точный период указан под значением или в колонке «Период».";
const HELP = {
  registry: ["Реестр", "Дата закрытия реестра акционеров. Дивиденд получат те, кто владеет акцией на конец этого дня (с учётом расчётов по сделкам)."],
  cum: ["Купить до ≈", "Последний день, когда можно купить акцию и получить дивиденд. Сейчас расчёты идут в режиме T+1, поэтому это рабочий день перед датой реестра. Оценка: праздники и нерабочие дни биржи не учитываются, проверяйте у брокера."],
  cum_past: ["Последний день с дивидендом", "Последний торговый день, когда покупка ещё давала право на дивиденд. На следующий день акция торгуется уже без дивиденда, и цена обычно падает — это и есть гэп. Режим расчётов учтён: до 02.09.2013 — T+0, до 31.07.2023 — T+2, после — T+1."],
  value: ["Дивиденд, ₽", "Выплата на одну акцию до вычета НДФЛ. Суммы скорректированы на сплиты, поэтому старые выплаты сопоставимы с текущей ценой."],
  yield: ["Доходность", "Дивиденд, делённый на последнюю цену закрытия. Это доходность одной выплаты, а не годовая и до вычета налога."],
  status: ["Статус", "«Объявлен» — выплату рекомендовал совет директоров или утвердило собрание акционеров. «Прогноз» — оценка аналитиков dohod.ru, компания ещё ничего не объявляла; сумма и дата могут измениться или выплаты не будет вовсе."],
  div_period: ["Период", "За какой отчётный год выплачивается дивиденд, по данным dohod.ru."],
  events: ["Гэпов", "Сколько прошлых отсечек этой акции попало в статистику: все выплаты, по которым есть котировки до и после даты реестра."],
  close_rate: ["Закрыто", "Доля гэпов, которые к сегодняшнему дню закрылись хотя бы раз: цена закрытия вернулась к уровню последнего дня с дивидендом. Срок не ограничен — гэп, закрывшийся через три года, тоже считается закрытым."],
  within: ["Закрыто ≤ N дн", "Доля гэпов, закрывшихся не позже чем через N календарных дней после дня гэпа. Свежие отсечки, после которых ещё не прошло N дней и гэп не закрыт, не учитываются, чтобы не занижать долю."],
  median_days: ["Медиана, дн", "Типичный срок закрытия гэпа в календарных днях. Половина закрытых гэпов закрылась быстрее, половина — медленнее. Считается только по закрытым гэпам. В отличие от среднего, медиана не искажается редкими случаями, когда гэп закрывался годами. 0 — гэп закрылся в тот же день."],
  median_trading_days: ["Медиана, торг. дн", "То же, что медиана в днях, но в торговых днях: выходные и праздники не считаются."],
  avg_gap: ["Средний гэп", "Среднее падение цены в день гэпа: (закрытие последнего дня с дивидендом − цена открытия следующего дня) ÷ закрытие последнего дня с дивидендом. Обычно гэп чуть меньше дивиденда: рынок учитывает налог, а цена ещё и движется вместе с рынком. " + PERIOD_NOTE],
  avg_yield: ["Средняя доходность", "Средняя доходность одной выплаты к цене закрытия последнего дня с дивидендом, по тем же отсечкам, что и средний гэп. Это не годовая доходность: у акций с выплатами раз в квартал годовая выше. " + PERIOD_NOTE],
  period: ["Период", "Годы первой и последней отсечки, попавших в статистику. По ним считаются все средние и доли в строке."],
  last_gap: ["Последний гэп", "Дата последнего гэпа и его судьба: закрылся за столько-то дней или ещё открыт. Для открытого показано, на сколько процентов цене нужно вырасти до закрытия."],
  ev_yield: ["Доходность выплаты", "Дивиденд ÷ цена закрытия последнего дня с дивидендом."],
  ev_gap: ["Гэп", "Падение цены на открытии следующего дня относительно закрытия последнего дня с дивидендом. Отрицательное значение — цена открылась выше, рынок отыграл гэп сразу."],
  price_before: ["Цена до", "Цена закрытия последнего дня с дивидендом. Гэп закрыт, когда цена закрытия возвращается к этому уровню. Цены скорректированы на сплиты."],
  ev_closed: ["Закрыт", "Дата, когда цена закрытия впервые вернулась к уровню «Цена до». «Нет» — гэп ещё открыт; рядом показано, сколько процентов осталось до закрытия."],
  ev_days: ["Дней", "Календарных дней от дня гэпа до закрытия. Для открытого гэпа — сколько дней прошло на сегодня (со знаком «+»)."],
  pf_price: ["Цена", "Последняя цена закрытия. За текущий день — цена на момент выгрузки данных (бесплатные данные Мосбиржи идут с задержкой 15 минут). Для индексов — значение индекса в пунктах."],
  pf_day: ["День", "Изменение к закрытию предыдущего торгового дня."],
  pf_week: ["Неделя", "Изменение к закрытию 7 календарных дней назад. Если в тот день торгов не было — к ближайшему торговому дню до него."],
  pf_month: ["Месяц", "Изменение к закрытию месяц назад (или ближайшему торговому дню до этой даты)."],
  pf_ytd: ["С начала года", "Изменение к закрытию последнего торгового дня прошлого года."],
  pf_year: ["Год", "Изменение к закрытию год назад (или ближайшему торговому дню до этой даты)."],
  pf_custom: ["Период", "Изменение от закрытия последнего торгового дня перед началом периода до закрытия последнего торгового дня периода. Даты задаются полями «Период с … по …»."],
  pf_divs: ["С дивидендами", "Добавляет к росту цены дивиденды, по которым гэп пришёлся на выбранный период: (цена в конце + сумма дивидендов) ÷ цена в начале − 1. Дивиденды не реинвестируются, налог не вычитается. Индекс IMOEX считается без дивидендов, для сравнения с ними смотрите MCFTR — индекс полной доходности, где дивиденды уже учтены."],
  total_events: ["Всего гэпов", "Число отсечек по всем акциям, попавших в статистику."],
};

const helpBtn = (key) =>
  `<button type="button" class="help-btn" data-help-key="${key}" aria-label="Что это: ${esc(HELP[key][0])}">?</button>`;

function decorateHelp(root = document) {
  root.querySelectorAll("[data-help]").forEach((el) => {
    if (el.querySelector(".help-btn") || !HELP[el.dataset.help]) return;
    el.insertAdjacentHTML("beforeend", " " + helpBtn(el.dataset.help));
  });
}

let helpOpenFor = null;
function showHelp(btn) {
  const pop = $("#help-pop");
  if (helpOpenFor === btn && !pop.hidden) return hideHelp();
  const [title, text] = HELP[btn.dataset.helpKey];
  pop.innerHTML = `<b>${esc(title)}</b><p>${esc(text)}</p>`;
  pop.hidden = false;
  helpOpenFor = btn;
  placeHelp();
}
// Держим окно рядом с кнопкой: при прокрутке переставляем, а не закрываем.
function placeHelp() {
  const pop = $("#help-pop");
  if (!helpOpenFor || pop.hidden) return;
  const r = helpOpenFor.getBoundingClientRect();
  if (r.bottom < 0 || r.top > window.innerHeight) return hideHelp();
  const w = pop.offsetWidth;
  const left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
  const below = r.bottom + 8 + pop.offsetHeight < window.innerHeight;
  pop.style.left = `${left}px`;
  pop.style.top = `${below ? r.bottom + 8 : Math.max(8, r.top - pop.offsetHeight - 8)}px`;
}
function hideHelp() {
  $("#help-pop").hidden = true;
  helpOpenFor = null;
}
document.addEventListener(
  "click",
  (ev) => {
    const btn = ev.target.closest(".help-btn");
    if (btn) {
      ev.stopPropagation(); // не сортировать таблицу и не открывать карточку
      ev.preventDefault();
      showHelp(btn);
    } else if (!ev.target.closest("#help-pop")) hideHelp();
  },
  true
);
document.addEventListener("keydown", (ev) => ev.key === "Escape" && hideHelp());
window.addEventListener("scroll", placeHelp, true);
window.addEventListener("resize", placeHelp);

const yearRange = (s) => (s.first_ex_date ? `${s.first_ex_date.slice(0, 4)}–${s.last_ex_date.slice(0, 4)}` : "—");

// Статическая версия (python -m app.export_static) читает заранее выгруженные JSON вместо API.
const STATIC = !!window.DIVGAP_STATIC;
const staticPath = (path) =>
  path.startsWith("/api/ticker/") ? `data/ticker/${path.slice(12)}.json` : `data/${path.slice(5).split("?")[0]}.json`;

async function api(path, opts) {
  // Однофайловая версия: все данные встроены в страницу.
  if (window.DIVGAP_DATA) {
    const data = window.DIVGAP_DATA[staticPath(path)];
    if (!data) throw new Error(`нет данных: ${path}`);
    return data;
  }
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
    ? `данные от ${fmtDate(data.last_update.slice(0, 10))} ${data.last_update.slice(11, 16)}${data.last_update.includes("+03:00") ? " МСК" : ""}`
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

// items: [подпись, значение, ключ пояснения?, подстрочник?]
function cards(items) {
  return items
    .map(
      ([label, value, help, sub]) =>
        `<div class="card"><div class="label">${label}${help ? " " + helpBtn(help) : ""}</div>` +
        `<div class="value">${value}</div>${sub ? `<div class="label">${sub}</div>` : ""}</div>`
    )
    .join("");
}

function renderOverall(o) {
  $("#overall-cards").innerHTML = cards([
    ["Всего гэпов", o.events, "total_events", yearRange(o)],
    ["Закрыто", fmtPct(o.close_rate), "close_rate"],
    ["Закрыто ≤ 7 дн", fmtPct(o.closed_within["7"]), "within"],
    ["Закрыто ≤ 30 дн", fmtPct(o.closed_within["30"]), "within"],
    ["Закрыто ≤ 90 дн", fmtPct(o.closed_within["90"]), "within"],
    ["Закрыто ≤ года", fmtPct(o.closed_within["365"]), "within"],
    ["Медиана, дн", o.median_days ?? "—", "median_days"],
    ["Средний гэп", fmtPct(o.avg_gap_pct, 2), "avg_gap", `за ${yearRange(o)}`],
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
        <td>${yearRange(t)}</td>
        <td class="num">${fmtPct(t.avg_gap_pct, 2)}</td>
        <td class="num">${fmtPct(t.avg_yield_pct, 2)}</td>
        <td>${t.last_event ? fmtDate(t.last_event.ex_date) + " " + lastEventBadge(t.last_event) : "—"}</td>
      </tr>`
      )
      .join("") || `<tr><td colspan="13" class="muted">Нет данных</td></tr>`;
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
    ["Гэпов", s.events, "events", yearRange(s)],
    ["Закрыто", fmtPct(s.close_rate), "close_rate"],
    ["≤ 30 дн", fmtPct(s.closed_within["30"]), "within"],
    ["≤ года", fmtPct(s.closed_within["365"]), "within"],
    ["Медиана, дн", s.median_days ?? "—", "median_days"],
    ["Медиана, торг. дн", s.median_trading_days ?? "—", "median_trading_days"],
    ["Средний гэп", fmtPct(s.avg_gap_pct, 2), "avg_gap", `за ${yearRange(s)}`],
    ["Средняя доходность", fmtPct(s.avg_yield_pct, 2), "avg_yield", `за ${yearRange(s)}`],
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

async function drawChart(r) {
  if (state.chart) state.chart.destroy();
  state.chart = null;
  if (typeof Chart === "undefined") return;
  const series = (await getCloses())[r.security.secid];
  r.prices = series ? series.dates.map((d, i) => [d, series.closes[i]]) : [];
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


// ---------- цены закрытия (общие для вкладки «Доходность» и графиков) ----------
let closesPromise = null;
function getCloses() {
  if (!closesPromise) {
    closesPromise = api("/api/closes").then((raw) => {
      const out = {};
      for (const [secid, s] of Object.entries(raw)) {
        const dates = [];
        let t = s.t0 ? Date.parse(s.t0 + "T00:00:00Z") : 0;
        for (const dt of s.dt) {
          t += dt * 864e5;
          dates.push(new Date(t).toISOString().slice(0, 10));
        }
        out[secid] = { ...s, secid, dates, closes: s.c };
      }
      return out;
    });
    closesPromise.catch(() => (closesPromise = null));
  }
  return closesPromise;
}

// Индекс последней даты <= iso (или < iso при strict), -1 если такой нет.
function idxOnOrBefore(dates, iso, strict = false) {
  let lo = 0, hi = dates.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (strict ? dates[mid] < iso : dates[mid] <= iso) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return ans;
}

function shiftIso(iso, { days = 0, months = 0, years = 0 }) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCFullYear(d.getUTCFullYear() + years, d.getUTCMonth() + months, d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

// Доходность ряда между индексами base и end (в процентах), опционально с дивидендами.
function periodReturn(s, base, end, withDivs) {
  if (base < 0 || end < 0 || base >= end) return null;
  let value = s.closes[end];
  if (withDivs) {
    const from = s.dates[base], to = s.dates[end];
    for (const [ex, v] of s.divs) if (ex > from && ex <= to) value += v;
  }
  return (value / s.closes[base] - 1) * 100;
}

function perfRow(s, asOf, from, to, withDivs) {
  const end = idxOnOrBefore(s.dates, asOf);
  if (end < 0) return null;
  const at = (iso) => idxOnOrBefore(s.dates, iso);
  const yearStart = `${asOf.slice(0, 4)}-01-01`;
  const cEnd = idxOnOrBefore(s.dates, to);
  return {
    secid: s.secid,
    name: s.name,
    sector: s.sector,
    is_index: s.is_index,
    last_date: s.dates[end],
    price: s.closes[end],
    day: periodReturn(s, end - 1, end, withDivs),
    week: periodReturn(s, at(shiftIso(asOf, { days: -7 })), end, withDivs),
    month: periodReturn(s, at(shiftIso(asOf, { months: -1 })), end, withDivs),
    ytd: periodReturn(s, idxOnOrBefore(s.dates, yearStart, true), end, withDivs),
    year: periodReturn(s, at(shiftIso(asOf, { years: -1 })), end, withDivs),
    custom: from && to && from <= to ? periodReturn(s, idxOnOrBefore(s.dates, from, true), cEnd, withDivs) : null,
  };
}

let perfData = null;
async function loadPerf() {
  if (!perfData) {
    perfData = await getCloses();
    const all = Object.values(perfData);
    const asOf = all.reduce((m, s) => (s.dates.length && s.dates.at(-1) > m ? s.dates.at(-1) : m), "");
    state.perfAsOf = asOf;
    if (!$("#pf-to").value) $("#pf-to").value = asOf;
    if (!$("#pf-from").value) $("#pf-from").value = shiftIso(asOf, { months: -3 });
    const sectors = [...new Set(all.filter((s) => !s.is_index).map((s) => s.sector).filter(Boolean))].sort();
    $("#pf-sector").insertAdjacentHTML("beforeend", sectors.map((x) => `<option>${esc(x)}</option>`).join(""));
  }
  renderPerf();
}

const pctCell = (v) =>
  `<td class="num ${v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : ""}">${v == null ? "—" : (v > 0 ? "+" : "") + fmtNum(v, 2) + "%"}</td>`;

function perfRowHtml(r) {
  // Отстающая дата: бумага не торговалась или индекс ещё не рассчитан за последний день.
  let lag = "";
  if (r.last_date < shiftIso(state.perfAsOf, { days: -7 })) lag = ` · торги до ${fmtDate(r.last_date)}`;
  else if (r.last_date !== state.perfAsOf) lag = ` · на ${fmtDate(r.last_date)}`;
  const link = r.is_index ? "" : ` class="clickable" data-secid="${esc(r.secid)}"`;
  return `<tr${link}>
    <td><b>${esc(r.secid)}</b><span class="sub">${esc(r.name)}${lag}</span></td>
    <td class="num">${r.is_index ? fmtNum(r.price, 2) : fmtValue(r.price)}</td>
    ${["day", "week", "month", "ytd", "year", "custom"].map((k) => pctCell(r[k])).join("")}
  </tr>`;
}

function renderPerf() {
  if (!perfData) return;
  const q = $("#pf-search").value.trim().toLowerCase();
  const sector = $("#pf-sector").value;
  const withDivs = $("#pf-divs").checked;
  const from = $("#pf-from").value, to = $("#pf-to").value;
  const asOf = state.perfAsOf;
  const rows = Object.values(perfData).map((s) => perfRow(s, asOf, from, to, withDivs)).filter(Boolean);

  $("#pf-index").innerHTML = rows.filter((r) => r.is_index).map(perfRowHtml).join("");
  const stocks = sortRows("pf-table", rows.filter((r) => !r.is_index && matches(r, q) && (!sector || r.sector === sector)));
  $("#pf-body").innerHTML =
    stocks.map(perfRowHtml).join("") || `<tr><td colspan="8" class="muted">Нет акций по выбранным фильтрам</td></tr>`;

  $("#pf-custom-th").firstChild.textContent = from && to ? `${fmtDate(from)} – ${fmtDate(to)} ` : "Период ";
  $("#pf-note").textContent =
    `Цены на ${fmtDate(asOf)}. ` +
    (withDivs ? "Доходность с учётом дивидендов (без реинвестирования и налога). " : "Изменение цены без учёта дивидендов. ") +
    `Акций: ${stocks.length}.`;
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
    if (t.dataset.view === "perf") loadPerf();
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
decorateHelp();
setupSort("up-table", renderUpcoming);
setupSort("st-table", renderStats);
setupSort("pf-table", renderPerf);
["#pf-search", "#pf-sector", "#pf-divs", "#pf-from", "#pf-to"].forEach((sel) => $(sel).addEventListener("input", renderPerf));

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

const VIEWS = { upcoming: null, stats: loadStats, perf: loadPerf };
function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (!h) return;
  if (h in VIEWS) {
    showView(h);
    VIEWS[h]?.();
  } else openTicker(h);
}
window.addEventListener("hashchange", route);

loadUpcoming();
route();
