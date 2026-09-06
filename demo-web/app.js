const CORRIDORS = {
  TJS: { country: 'Таджикистан', currency: 'TJS', flag: '🇹🇯' },
  UZS: { country: 'Узбекистан', currency: 'UZS', flag: '🇺🇿' },
  KGS: { country: 'Кыргызстан', currency: 'KGS', flag: '🇰🇬' },
  AMD: { country: 'Армения', currency: 'AMD', flag: '🇦🇲' },
  KZT: { country: 'Казахстан', currency: 'KZT', flag: '🇰🇿' },
};

const state = {
  corridor: 'TJS', range: 365, mode: 'history', points: [], signals: [], geometry: null,
  replayStartedAt: 0, replayFrame: 0, replayPushSent: false,
};
const $ = (selector) => document.querySelector(selector);
const canvas = $('#rate-chart');
const ctx = canvas.getContext('2d');
const chartWrap = $('#chart-wrap');
const fmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 });
const money = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });
const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
const shortDateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' });

function typeClass(type) {
  return type === 'good_now' ? 'good' : type === 'window_closing' ? 'closing' : 'fact';
}

function visibleData() {
  const all = window.DEMO_DATA.corridors[state.corridor];
  const start = state.range === 'all' ? 0 : Math.max(0, all.points.length - Number(state.range));
  const points = all.points.slice(start).map(([date, rate]) => ({ date, rate, ts: Date.parse(date) }));
  return { points, signals: all.signals.filter((signal) => signal.date >= points[0].date) };
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

function chartGeometry(points, width, height, extraRates = []) {
  const pad = { left: 22, right: 78, top: 26, bottom: 36 };
  const rates = points.map((point) => point.rate).concat(extraRates);
  const min = Math.min(...rates), max = Math.max(...rates);
  const spread = Math.max(max - min, Math.abs(max) * .002, .000001);
  const low = min - spread * .18, high = max + spread * .2;
  const firstTs = points[0].ts, lastTs = points.at(-1).ts;
  const x = (ts) => pad.left + (ts - firstTs) / Math.max(1, lastTs - firstTs) * (width - pad.left - pad.right);
  const y = (rate) => pad.top + (high - rate) / (high - low) * (height - pad.top - pad.bottom);
  return { width, height, pad, min: low, max: high, x, y };
}

function drawGrid(points, geometry, replay = false) {
  const { width, height, pad, min: low, max: high, x } = geometry;
  ctx.clearRect(0, 0, width, height);
  ctx.lineWidth = 1;
  ctx.font = '11px Inter, sans-serif';
  for (let i = 0; i <= 5; i += 1) {
    const yy = pad.top + (height - pad.top - pad.bottom) * i / 5;
    ctx.strokeStyle = '#252831'; ctx.setLineDash([3, 5]);
    ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right, yy); ctx.stroke();
    ctx.fillStyle = '#6f7480'; ctx.textAlign = 'left';
    ctx.fillText(fmt.format(high - (high - low) * i / 5), width - pad.right + 10, yy + 4);
  }
  const ticks = replay ? points : Array.from({ length: 6 }, (_, i) => points[Math.round((points.length - 1) * i / 5)]);
  ticks.forEach((point, index) => {
    const xx = x(point.ts);
    ctx.strokeStyle = '#20232a'; ctx.setLineDash([]); ctx.beginPath(); ctx.moveTo(xx, pad.top); ctx.lineTo(xx, height - pad.bottom); ctx.stroke();
    ctx.fillStyle = '#656a75'; ctx.textAlign = index === 0 ? 'left' : index === ticks.length - 1 ? 'right' : 'center';
    const label = replay ? shortDateFmt.format(point.ts) : new Intl.DateTimeFormat('ru-RU', { month: 'short', year: '2-digit' }).format(point.ts);
    ctx.fillText(label, xx, height - 13);
  });
  ctx.setLineDash([]); ctx.textAlign = 'left';
}

function drawHistoryChart() {
  const { points, signals } = visibleData();
  state.points = points; state.signals = signals;
  const { width, height } = resizeCanvas();
  const geometry = chartGeometry(points, width, height);
  state.geometry = geometry;
  drawGrid(points, geometry);
  const { x, y, pad } = geometry;
  const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, '#f13c3240'); gradient.addColorStop(1, '#f13c3200');
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(point.ts), y(point.rate)) : ctx.moveTo(x(point.ts), y(point.rate)));
  ctx.lineTo(x(points.at(-1).ts), height - pad.bottom); ctx.lineTo(x(points[0].ts), height - pad.bottom); ctx.closePath();
  ctx.fillStyle = gradient; ctx.fill();
  ctx.beginPath(); points.forEach((point, index) => index ? ctx.lineTo(x(point.ts), y(point.rate)) : ctx.moveTo(x(point.ts), y(point.rate)));
  ctx.strokeStyle = '#ff5a51'; ctx.lineWidth = 2; ctx.shadowBlur = 10; ctx.shadowColor = '#f13c3266'; ctx.stroke(); ctx.shadowBlur = 0;
  drawLastPrice(points.at(-1), geometry, '#f13c32');
  renderMarkers();
  const first = points[0].rate, last = points.at(-1);
  const change = (last.rate / first - 1) * 100;
  $('#ticker-rate').textContent = fmt.format(last.rate);
  $('#ticker-change').textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2).replace('.', ',')}% за период`;
  $('#ticker-change').classList.toggle('negative', change > 0);
}

function drawLastPrice(point, geometry, color) {
  const { width, pad, y } = geometry;
  ctx.setLineDash([4, 4]); ctx.strokeStyle = `${color}77`; ctx.beginPath(); ctx.moveTo(pad.left, y(point.rate)); ctx.lineTo(width - pad.right, y(point.rate)); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = color; ctx.fillRect(width - pad.right, y(point.rate) - 10, 66, 20);
  ctx.fillStyle = '#fff'; ctx.font = '700 11px Inter, sans-serif'; ctx.fillText(fmt.format(point.rate), width - pad.right + 7, y(point.rate) + 4);
}

function drawProgressLine(points, progress, geometry, color, dashed = false) {
  if (progress <= 0) return;
  const scaled = Math.min(1, progress) * (points.length - 1);
  const completed = Math.floor(scaled);
  const fraction = scaled - completed;
  const visible = points.slice(0, completed + 1);
  if (completed < points.length - 1 && fraction > 0) {
    const a = points[completed], b = points[completed + 1];
    visible.push({ ts: a.ts + (b.ts - a.ts) * fraction, rate: a.rate + (b.rate - a.rate) * fraction });
  }
  ctx.beginPath(); visible.forEach((point, index) => index ? ctx.lineTo(geometry.x(point.ts), geometry.y(point.rate)) : ctx.moveTo(geometry.x(point.ts), geometry.y(point.rate)));
  ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.setLineDash(dashed ? [7, 5] : []); ctx.shadowBlur = 12; ctx.shadowColor = `${color}66`; ctx.stroke(); ctx.shadowBlur = 0; ctx.setLineDash([]);
}

function replayData() { return window.REPLAY_DATA.corridors[state.corridor]; }

function drawReplay(now = performance.now()) {
  if (state.mode !== 'prediction') return;
  const replay = replayData();
  const elapsed = now - state.replayStartedAt;
  const predicted = replay.predicted.map(([date, rate]) => ({ date, rate, ts: Date.parse(date) }));
  const golden = replay.golden.map(([date, rate]) => ({ date, rate, ts: Date.parse(date) }));
  const { width, height } = resizeCanvas();
  const geometry = chartGeometry(predicted, width, height, golden.map((point) => point.rate));
  state.geometry = geometry;
  state.points = golden;
  drawGrid(predicted, geometry, true);

  const todayAlpha = Math.max(0, Math.min(1, (elapsed - 120) / 320));
  if (todayAlpha > 0) {
    const today = predicted[0], xx = geometry.x(today.ts), yy = geometry.y(today.rate);
    ctx.globalAlpha = todayAlpha;
    ctx.setLineDash([4, 5]); ctx.strokeStyle = '#d9dce488'; ctx.beginPath(); ctx.moveTo(xx, geometry.pad.top); ctx.lineTo(xx, height - geometry.pad.bottom); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(xx, yy, 5, 0, Math.PI * 2); ctx.fill();
    ctx.font = '700 11px Inter, sans-serif'; ctx.fillStyle = '#d9dce4'; ctx.fillText('СЕГОДНЯ', xx + 10, geometry.pad.top + 15);
    ctx.globalAlpha = 1;
  }

  const predictedProgress = (elapsed - 520) / 1250;
  const goldenProgress = (elapsed - 2350) / 1150;
  drawProgressLine(predicted, predictedProgress, geometry, '#a98cff', true);
  drawProgressLine(golden, goldenProgress, geometry, '#ff5a51');
  if (goldenProgress >= 1) drawLastPrice(golden.at(-1), geometry, '#f13c32');

  const predictedVisible = elapsed >= 1850;
  const goldenVisible = elapsed >= 3600;
  const todayVisible = elapsed >= 4150;
  state.signals = [
    ...(predictedVisible ? replay.predictedSignals : []),
    ...(goldenVisible ? replay.goldenSignals : []),
    ...(todayVisible ? [replay.todaySignal] : []),
  ];
  renderMarkers(true);
  updateReplaySummary(elapsed);

  $('#ticker-rate').textContent = fmt.format(replay.todaySignal.rate);
  $('#ticker-change').textContent = `TimesFM H5: ${replay.comparison.meanChangeH5Bps >= 0 ? '+' : ''}${replay.comparison.meanChangeH5Bps.toFixed(1).replace('.', ',')} bps`;
  $('#ticker-change').classList.toggle('negative', replay.comparison.meanChangeH5Bps > 0);

  if (todayVisible && !state.replayPushSent) {
    state.replayPushSent = true;
    sendPush(replay.todaySignal);
  }
  if (elapsed < 4600) state.replayFrame = requestAnimationFrame(drawReplay);
}

function renderMarkers(replayMode = false) {
  const { x, y } = state.geometry;
  $('#signal-layer').innerHTML = state.signals.map((signal, index) => {
    const series = replayMode ? ` ${signal.series || ''}` : '';
    const title = signal.series === 'predicted' ? 'Прогнозный сигнал' : PUSH_MESSAGES[signal.type].label;
    return `<button class="signal-marker ${typeClass(signal.type)}${series}" style="left:${x(Date.parse(signal.date))}px;top:${y(signal.rate)}px" data-signal="${index}" aria-label="${title}, ${dateFmt.format(Date.parse(signal.date))}">${signal.series === 'predicted' ? '◇' : '✦'}</button>`;
  }).join('');
}

function updateReplaySummary(elapsed) {
  const replay = replayData(), c = replay.comparison;
  let stage = 'Фиксируем точку T и входные данные';
  if (elapsed >= 520) stage = 'TimesFM строит прогноз на H1…H5';
  if (elapsed >= 1850) stage = 'Расставляем сигналы на прогнозе';
  if (elapsed >= 2350) stage = 'Открываем golden-факт для сравнения';
  if (elapsed >= 3600) stage = 'Сравниваем predicted и golden сигналы';
  if (elapsed >= 4150) stage = 'Применяем push-политику в точке «сегодня»';
  $('#signal-detail').innerHTML = `
    <div class="detail-head"><span class="badge replay-badge">TIMESFM</span><time>${dateFmt.format(Date.parse(replay.today))}</time></div>
    <h2 class="detail-title">${stage}</h2>
    <p class="detail-reason">Прогноз строится без заглядывания вперёд. Golden появляется позже и нужен только для проверки.</p>
    <div class="metric-row">
      <div class="metric"><span>Среднее H1…H5</span><strong>${c.meanChangeH5Bps >= 0 ? '+' : ''}${c.meanChangeH5Bps.toFixed(1)} bps</strong></div>
      <div class="metric"><span>Дней хуже</span><strong>${c.worseDaysH5} из 5</strong></div>
      <div class="metric"><span>Сигналов predicted</span><strong>${c.predictedCount}</strong></div>
      <div class="metric"><span>Сигналов golden</span><strong>${c.goldenCount}</strong></div>
    </div>
    <p class="detail-note">Пунктир — интерполяция сохранённых агрегатов TimesFM H5. Красная линия — фактический golden-ряд. MAE: ${fmt.format(c.mae)}.</p>`;
}

function setMode(mode) {
  state.mode = mode;
  cancelAnimationFrame(state.replayFrame);
  state.replayFrame = 0;
  state.replayPushSent = false;
  $('#history-mode').classList.toggle('active', mode === 'history');
  $('#prediction-mode').classList.toggle('active', mode === 'prediction');
  $('#history-mode').setAttribute('aria-pressed', mode === 'history');
  $('#prediction-mode').setAttribute('aria-pressed', mode === 'prediction');
  document.body.classList.toggle('prediction-mode', mode === 'prediction');
  if (mode === 'prediction') {
    $('#chart-legend').innerHTML = '<span><i class="line-key predicted"></i> TimesFM прогноз</span><span><i class="line-key golden"></i> Golden факт</span><span><i class="dot candidate"></i> predicted сигнал</span><span><i class="dot good"></i> golden / push</span><small>Метки остаются кликабельными</small>';
    $('.logic-card').innerHTML = '<div class="section-label">ЧТО СРАВНИВАЕМ</div><p><b>Predicted</b> использует данные только до T. <b>Golden</b> открывается после прогноза и показывает, где сигналы должны были стоять по факту.</p>';
    updateStats();
    state.replayStartedAt = performance.now();
    drawReplay(state.replayStartedAt);
  } else {
    $('#chart-legend').innerHTML = '<span><i class="dot good"></i> Выгодный момент</span><span><i class="dot closing"></i> Окно закрывается</span><span><i class="dot fact"></i> Позитивный факт</span><small>Нажмите на любую метку, чтобы отправить push</small>';
    $('.logic-card').innerHTML = '<div class="section-label">ПОЧЕМУ ЭТО НЕ ПРОГНОЗ</div><p>Метки <b>good</b> и <b>closing</b> — ретроспективная разметка для проверки идеи. В продуктовом контуре модель использует только данные, доступные на дату T.</p>';
    resetSignalDetail();
    updateStats();
    drawHistoryChart();
  }
}

function resetSignalDetail() {
  $('#signal-detail').innerHTML = '<div class="empty-detail"><span class="radar-icon">⌁</span><h2>Выберите сигнал</h2><p>Нажмите на метку над графиком — здесь появится разбор и сразу прилетит тестовый push.</p></div>';
}

function selectCorridor(code) {
  state.corridor = code;
  const item = CORRIDORS[code];
  renderTabs();
  $('#ticker-code').textContent = `${code} / RUB`;
  $('#ticker-country').textContent = item.country;
  $('#transfer-country').value = code;
  updateTransfer();
  if (state.mode === 'prediction') setMode('prediction');
  else { updateStats(); drawHistoryChart(); }
}

function updateStats() {
  if (state.mode === 'prediction') {
    const replay = replayData();
    const all = [replay.todaySignal, ...replay.predictedSignals];
    $('#stat-total').textContent = all.length;
    $('#stat-good').textContent = all.filter((signal) => signal.type === 'good_now').length;
    $('#stat-closing').textContent = all.filter((signal) => signal.type === 'window_closing').length;
    $('#stat-fact').textContent = all.filter((signal) => signal.type === 'positive_market_fact').length;
    return;
  }
  const summary = window.DEMO_DATA.corridors[state.corridor].summary;
  $('#stat-total').textContent = summary.total;
  $('#stat-good').textContent = summary.good;
  $('#stat-closing').textContent = summary.closing;
  $('#stat-fact').textContent = summary.fact;
}

function factText(signal) {
  const facts = signal.facts || [];
  return facts.length ? facts.map((key) => FACT_MESSAGES[key]).join(' ') : 'Курс показывает положительную для отправителя динамику.';
}

function signalReason(signal) {
  if (signal.timesfm) return `TimesFM: среднее изменение H1…H5 = ${signal.timesfm.meanChangeH5Bps.toFixed(1)} bps; дней с ухудшением — ${signal.timesfm.worseDaysH5} из 5.`;
  if (signal.type === 'good_now') return `Отклонение от минимума окна укладывается в 100 bps. Future regret: ${signal.futureRegretBps ?? 0} bps.`;
  if (signal.type === 'window_closing') return `Отскок от прошлого минимума: ${signal.reboundBps ?? '—'} bps. Будущая медиана хуже на ${signal.futureMedianChangeBps ?? '—'} bps.`;
  return factText(signal);
}

function showSignal(signal) {
  const item = CORRIDORS[state.corridor], copy = PUSH_MESSAGES[signal.type];
  const color = signal.type === 'good_now' ? 'var(--green)' : signal.type === 'window_closing' ? 'var(--amber)' : 'var(--blue)';
  $('#signal-detail').innerHTML = `
    <div class="detail-head"><span class="badge" style="background:${color}">${copy.label}</span><time>${dateFmt.format(Date.parse(signal.date))}</time></div>
    <h2 class="detail-title">Почему появился сигнал</h2><p class="detail-reason">${signalReason(signal)}</p>
    <div class="metric-row">
      <div class="metric"><span>Курс в точке</span><strong>${fmt.format(signal.rate)} ₽/${item.currency}</strong></div>
      <div class="metric"><span>Получатель</span><strong>${money.format(signal.recipientAmount ?? 22000 / signal.rate)} ${item.currency}</strong></div>
      <div class="metric"><span>Эффект*</span><strong>${(signal.effectUnits ?? 0) >= 0 ? '+' : ''}${money.format(signal.effectUnits ?? 0)} ${item.currency}</strong></div>
      <div class="metric"><span>Изменение 5д</span><strong>${(signal.ret5Pct ?? 0) >= 0 ? '+' : ''}${signal.ret5Pct ?? 0}%</strong></div>
    </div><p class="detail-note">* Ретроспективная оценка для 22 000 ₽, не обещание.</p>`;
  sendPush(signal);
}

function sendPush(signal) {
  const corridor = state.corridor, item = CORRIDORS[corridor];
  const copy = getPushCopy(signal.type, { ...item, facts: signal.facts || [] });
  const toast = document.createElement('button');
  toast.className = 'push-toast';
  toast.innerHTML = `<span class="push-app">A</span><span><strong>${copy.title}</strong><span>${copy.body}</span></span><small>сейчас</small>`;
  toast.addEventListener('click', () => { openDrawer(corridor); toast.remove(); });
  $('#push-stack').prepend(toast);
  window.setTimeout(() => toast.remove(), 11000);
}

function nearestPoint(clientX) {
  const rect = chartWrap.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left - state.geometry.pad.left) / (state.geometry.width - state.geometry.pad.left - state.geometry.pad.right)));
  return state.points[Math.round(ratio * (state.points.length - 1))];
}

function moveCrosshair(event) {
  if (!state.geometry || !state.points.length) return;
  const rect = chartWrap.getBoundingClientRect(), point = nearestPoint(event.clientX);
  const xx = state.geometry.x(point.ts), yy = state.geometry.y(point.rate);
  const crosshair = $('#crosshair'); crosshair.hidden = false;
  crosshair.querySelector('span').style.left = `${xx}px`; crosshair.querySelector('i').style.top = `${yy}px`;
  const tip = $('#chart-tooltip'); tip.hidden = false;
  tip.innerHTML = `<strong>${fmt.format(point.rate)} RUB / ${state.corridor}</strong><span>${dateFmt.format(point.ts)}</span>`;
  tip.style.left = `${Math.min(xx + 12, rect.width - 165)}px`; tip.style.top = `${Math.max(10, yy - 48)}px`;
}

function openDrawer(code = state.corridor) {
  const selected = CORRIDORS[code] ? code : state.corridor;
  $('#transfer-country').value = selected;
  $('#transfer-drawer').classList.add('open');
  $('#transfer-drawer').setAttribute('aria-hidden', 'false');
  updateTransfer();
}
function closeDrawer() { $('#transfer-drawer').classList.remove('open'); $('#transfer-drawer').setAttribute('aria-hidden', 'true'); }
function updateTransfer() {
  const code = $('#transfer-country').value || state.corridor, data = window.DEMO_DATA.corridors[code];
  if (!data) return;
  const amount = Number($('#transfer-amount').value || 0), rate = data.points.at(-1)[1];
  $('#transfer-receives').textContent = `${money.format(amount / rate)} ${code}`;
  $('#transfer-rate-label').textContent = `1 ${code} = ${fmt.format(rate)} ₽ · демо-ориентир`;
}

$('#corridor-tabs').addEventListener('click', (event) => { const button = event.target.closest('[data-corridor]'); if (button) selectCorridor(button.dataset.corridor); });
$('.range-picker').addEventListener('click', (event) => { const button = event.target.closest('[data-range]'); if (!button || state.mode !== 'history') return; state.range = button.dataset.range; document.querySelectorAll('[data-range]').forEach((item) => item.classList.toggle('active', item === button)); drawHistoryChart(); });
$('#history-mode').addEventListener('click', () => setMode('history'));
$('#prediction-mode').addEventListener('click', () => setMode('prediction'));
$('#signal-layer').addEventListener('click', (event) => { const button = event.target.closest('[data-signal]'); if (button) showSignal(state.signals[Number(button.dataset.signal)]); });
chartWrap.addEventListener('mousemove', moveCrosshair);
chartWrap.addEventListener('mouseleave', () => { $('#crosshair').hidden = true; $('#chart-tooltip').hidden = true; });
$('#open-transfer').addEventListener('click', () => openDrawer());
document.querySelectorAll('[data-close-drawer]').forEach((item) => item.addEventListener('click', closeDrawer));
$('#transfer-country').addEventListener('change', updateTransfer); $('#transfer-amount').addEventListener('input', updateTransfer);
$('#transfer-form').addEventListener('submit', (event) => { event.preventDefault(); closeDrawer(); const toast = document.createElement('div'); toast.className = 'push-toast'; toast.innerHTML = '<span class="push-app">✓</span><span><strong>Демо-перевод создан</strong><span>Деньги не списывались и не отправлялись.</span></span><small>сейчас</small>'; $('#push-stack').prepend(toast); setTimeout(() => toast.remove(), 7000); });
window.addEventListener('resize', () => window.requestAnimationFrame(() => state.mode === 'history' ? drawHistoryChart() : drawReplay()));

$('#transfer-country').innerHTML = Object.entries(CORRIDORS).map(([code, item]) => `<option value="${code}">${item.flag} ${item.country}</option>`).join('');
$('#transfer-country').value = state.corridor;
selectCorridor(state.corridor);
