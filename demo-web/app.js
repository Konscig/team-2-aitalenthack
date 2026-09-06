const CORRIDORS = {
  TJS: { country: 'Таджикистан', currency: 'TJS', flag: '🇹🇯' },
  UZS: { country: 'Узбекистан', currency: 'UZS', flag: '🇺🇿' },
  KGS: { country: 'Кыргызстан', currency: 'KGS', flag: '🇰🇬' },
  AMD: { country: 'Армения', currency: 'AMD', flag: '🇦🇲' },
  KZT: { country: 'Казахстан', currency: 'KZT', flag: '🇰🇿' },
};

const state = { corridor: 'TJS', range: 365, points: [], signals: [], geometry: null };
const $ = (selector) => document.querySelector(selector);
const canvas = $('#rate-chart');
const ctx = canvas.getContext('2d');
const chartWrap = $('#chart-wrap');
const fmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 });
const money = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });
const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });

function typeClass(type) {
  return type === 'good_now' ? 'good' : type === 'window_closing' ? 'closing' : 'fact';
}

function visibleData() {
  const all = window.DEMO_DATA.corridors[state.corridor];
  const start = state.range === 'all' ? 0 : Math.max(0, all.points.length - Number(state.range));
  const points = all.points.slice(start).map(([date, rate]) => ({ date, rate, ts: Date.parse(date) }));
  const minDate = points[0].date;
  return { points, signals: all.signals.filter((signal) => signal.date >= minDate) };
}

function renderTabs() {
  $('#corridor-tabs').innerHTML = Object.entries(CORRIDORS).map(([code, item]) => `
    <button class="corridor-tab ${code === state.corridor ? 'active' : ''}" data-corridor="${code}" aria-pressed="${code === state.corridor}">
      <strong>${item.flag} ${code} / RUB</strong><span>${item.country}</span>
    </button>`).join('');
}

function resizeCanvas() {
  const rect = chartWrap.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  canvas.style.width = `${rect.width}px`;
  canvas.style.height = `${rect.height}px`;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width: rect.width, height: rect.height };
}

function drawChart() {
  const { points, signals } = visibleData();
  state.points = points; state.signals = signals;
  const { width, height } = resizeCanvas();
  const pad = { left: 22, right: 78, top: 26, bottom: 36 };
  const min = Math.min(...points.map((p) => p.rate));
  const max = Math.max(...points.map((p) => p.rate));
  const spread = Math.max(max - min, max * .002);
  const low = min - spread * .11, high = max + spread * .14;
  const x = (ts) => pad.left + (ts - points[0].ts) / (points.at(-1).ts - points[0].ts) * (width - pad.left - pad.right);
  const y = (rate) => pad.top + (high - rate) / (high - low) * (height - pad.top - pad.bottom);
  state.geometry = { width, height, pad, min: low, max: high, x, y };

  ctx.clearRect(0, 0, width, height);
  ctx.lineWidth = 1;
  ctx.font = '11px Inter, sans-serif';
  ctx.textAlign = 'left';
  for (let i = 0; i <= 5; i += 1) {
    const yy = pad.top + (height - pad.top - pad.bottom) * i / 5;
    ctx.strokeStyle = '#252831'; ctx.setLineDash([3, 5]);
    ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right, yy); ctx.stroke();
    ctx.fillStyle = '#6f7480'; ctx.fillText(fmt.format(high - (high - low) * i / 5), width - pad.right + 10, yy + 4);
  }
  for (let i = 0; i <= 5; i += 1) {
    const index = Math.round((points.length - 1) * i / 5);
    const xx = x(points[index].ts);
    ctx.strokeStyle = '#20232a'; ctx.beginPath(); ctx.moveTo(xx, pad.top); ctx.lineTo(xx, height - pad.bottom); ctx.stroke();
    ctx.fillStyle = '#656a75'; ctx.textAlign = i === 0 ? 'left' : i === 5 ? 'right' : 'center';
    ctx.fillText(new Intl.DateTimeFormat('ru-RU', { month: 'short', year: '2-digit' }).format(points[index].ts), xx, height - 13);
  }
  ctx.setLineDash([]); ctx.textAlign = 'left';
  const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, '#f13c3240'); gradient.addColorStop(1, '#f13c3200');
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(point.ts), y(point.rate)) : ctx.moveTo(x(point.ts), y(point.rate)));
  ctx.lineTo(x(points.at(-1).ts), height - pad.bottom); ctx.lineTo(x(points[0].ts), height - pad.bottom); ctx.closePath();
  ctx.fillStyle = gradient; ctx.fill();
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(point.ts), y(point.rate)) : ctx.moveTo(x(point.ts), y(point.rate)));
  ctx.strokeStyle = '#ff5a51'; ctx.lineWidth = 2; ctx.shadowBlur = 10; ctx.shadowColor = '#f13c3266'; ctx.stroke(); ctx.shadowBlur = 0;

  const last = points.at(-1);
  ctx.setLineDash([4, 4]); ctx.strokeStyle = '#f13c3277'; ctx.beginPath(); ctx.moveTo(pad.left, y(last.rate)); ctx.lineTo(width - pad.right, y(last.rate)); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = '#f13c32'; ctx.fillRect(width - pad.right, y(last.rate) - 10, 66, 20);
  ctx.fillStyle = '#fff'; ctx.font = '700 11px Inter, sans-serif'; ctx.fillText(fmt.format(last.rate), width - pad.right + 7, y(last.rate) + 4);

  renderMarkers();
  const first = points[0].rate;
  const change = (last.rate / first - 1) * 100;
  $('#ticker-rate').textContent = fmt.format(last.rate);
  $('#ticker-change').textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2).replace('.', ',')}% за период`;
  $('#ticker-change').classList.toggle('negative', change > 0);
}

function renderMarkers() {
  const { x, y } = state.geometry;
  $('#signal-layer').innerHTML = state.signals.map((signal, index) => `
    <button class="signal-marker ${typeClass(signal.type)}" style="left:${x(Date.parse(signal.date))}px;top:${y(signal.rate)}px" data-signal="${index}" aria-label="${PUSH_MESSAGES[signal.type].label}, ${dateFmt.format(Date.parse(signal.date))}">✦</button>
  `).join('');
}

function selectCorridor(code) {
  state.corridor = code;
  const item = CORRIDORS[code];
  renderTabs();
  $('#ticker-code').textContent = `${code} / RUB`;
  $('#ticker-country').textContent = item.country;
  updateStats();
  drawChart();
  updateTransfer();
}

function updateStats() {
  const summary = window.DEMO_DATA.corridors[state.corridor].summary;
  $('#stat-total').textContent = summary.total;
  $('#stat-good').textContent = summary.good;
  $('#stat-closing').textContent = summary.closing;
  $('#stat-fact').textContent = summary.fact;
}

function factText(signal) {
  return signal.facts.length ? signal.facts.map((key) => FACT_MESSAGES[key]).join(' ') : 'Курс показывает положительную для отправителя динамику.';
}

function signalReason(signal) {
  if (signal.type === 'good_now') return `Отклонение от минимума окна укладывается в 100 bps. Future regret: ${signal.futureRegretBps ?? 0} bps.`;
  if (signal.type === 'window_closing') return `Отскок от прошлого минимума: ${signal.reboundBps} bps. Будущая медиана хуже на ${signal.futureMedianChangeBps} bps.`;
  return factText(signal);
}

function showSignal(signal) {
  const item = CORRIDORS[state.corridor];
  const copy = PUSH_MESSAGES[signal.type];
  const color = signal.type === 'good_now' ? 'var(--green)' : signal.type === 'window_closing' ? 'var(--amber)' : 'var(--blue)';
  $('#signal-detail').innerHTML = `
    <div class="detail-head"><span class="badge" style="background:${color}">${copy.label}</span><time>${dateFmt.format(Date.parse(signal.date))}</time></div>
    <h2 class="detail-title">Почему появился сигнал</h2>
    <p class="detail-reason">${signalReason(signal)}</p>
    <div class="metric-row">
      <div class="metric"><span>Курс в точке</span><strong>${fmt.format(signal.rate)} ₽/${item.currency}</strong></div>
      <div class="metric"><span>Получатель</span><strong>${money.format(signal.recipientAmount)} ${item.currency}</strong></div>
      <div class="metric"><span>Эффект*</span><strong>${signal.effectUnits >= 0 ? '+' : ''}${money.format(signal.effectUnits)} ${item.currency}</strong></div>
      <div class="metric"><span>Изменение 5д</span><strong>${signal.ret5Pct >= 0 ? '+' : ''}${signal.ret5Pct}%</strong></div>
    </div>
    <p class="detail-note">* Сравнение суммы получения для 22 000 ₽ с медианным курсом следующих 10 дней. Ретроспективная оценка, не обещание.</p>`;
  sendPush(signal);
}

function sendPush(signal) {
  const item = CORRIDORS[state.corridor];
  const copy = getPushCopy(signal.type, { ...item, facts: signal.facts });
  const toast = document.createElement('button');
  toast.className = 'push-toast';
  toast.innerHTML = `<span class="push-app">A</span><span><strong>${copy.title}</strong><span>${copy.body}</span></span><small>сейчас</small>`;
  toast.addEventListener('click', () => { openDrawer(); toast.remove(); });
  $('#push-stack').prepend(toast);
  window.setTimeout(() => toast.remove(), 11000);
}

function nearestPoint(clientX) {
  const rect = chartWrap.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left - state.geometry.pad.left) / (state.geometry.width - state.geometry.pad.left - state.geometry.pad.right)));
  return state.points[Math.round(ratio * (state.points.length - 1))];
}

function moveCrosshair(event) {
  if (!state.geometry) return;
  const rect = chartWrap.getBoundingClientRect();
  const point = nearestPoint(event.clientX);
  const xx = state.geometry.x(point.ts), yy = state.geometry.y(point.rate);
  const crosshair = $('#crosshair'); crosshair.hidden = false;
  crosshair.querySelector('span').style.left = `${xx}px`; crosshair.querySelector('i').style.top = `${yy}px`;
  const tip = $('#chart-tooltip'); tip.hidden = false;
  tip.innerHTML = `<strong>${fmt.format(point.rate)} RUB / ${state.corridor}</strong><span>${dateFmt.format(point.ts)}</span>`;
  tip.style.left = `${Math.min(xx + 12, rect.width - 165)}px`; tip.style.top = `${Math.max(10, yy - 48)}px`;
}

function openDrawer() { $('#transfer-drawer').classList.add('open'); $('#transfer-drawer').setAttribute('aria-hidden', 'false'); updateTransfer(); }
function closeDrawer() { $('#transfer-drawer').classList.remove('open'); $('#transfer-drawer').setAttribute('aria-hidden', 'true'); }
function updateTransfer() {
  const code = $('#transfer-country').value || state.corridor;
  const data = window.DEMO_DATA.corridors[code];
  if (!data) return;
  const amount = Number($('#transfer-amount').value || 0), rate = data.points.at(-1)[1];
  $('#transfer-receives').textContent = `${money.format(amount / rate)} ${code}`;
  $('#transfer-rate-label').textContent = `1 ${code} = ${fmt.format(rate)} ₽ · демо-ориентир`;
}

$('#corridor-tabs').addEventListener('click', (event) => { const button = event.target.closest('[data-corridor]'); if (button) selectCorridor(button.dataset.corridor); });
$('.range-picker').addEventListener('click', (event) => { const button = event.target.closest('[data-range]'); if (!button) return; state.range = button.dataset.range; document.querySelectorAll('[data-range]').forEach((item) => item.classList.toggle('active', item === button)); drawChart(); });
$('#signal-layer').addEventListener('click', (event) => { const button = event.target.closest('[data-signal]'); if (button) showSignal(state.signals[Number(button.dataset.signal)]); });
chartWrap.addEventListener('mousemove', moveCrosshair);
chartWrap.addEventListener('mouseleave', () => { $('#crosshair').hidden = true; $('#chart-tooltip').hidden = true; });
$('#open-transfer').addEventListener('click', openDrawer);
document.querySelectorAll('[data-close-drawer]').forEach((item) => item.addEventListener('click', closeDrawer));
$('#transfer-country').addEventListener('change', updateTransfer); $('#transfer-amount').addEventListener('input', updateTransfer);
$('#transfer-form').addEventListener('submit', (event) => { event.preventDefault(); closeDrawer(); const toast = document.createElement('div'); toast.className = 'push-toast'; toast.innerHTML = '<span class="push-app">✓</span><span><strong>Демо-перевод создан</strong><span>Деньги не списывались и не отправлялись.</span></span><small>сейчас</small>'; $('#push-stack').prepend(toast); setTimeout(() => toast.remove(), 7000); });
window.addEventListener('resize', () => window.requestAnimationFrame(drawChart));

$('#transfer-country').innerHTML = Object.entries(CORRIDORS).map(([code, item]) => `<option value="${code}">${item.flag} ${item.country}</option>`).join('');
$('#transfer-country').value = state.corridor;
selectCorridor(state.corridor);
