const CORRIDORS = {
  TJS: { country: 'Таджикистан', currency: 'TJS', flag: '🇹🇯' },
  UZS: { country: 'Узбекистан', currency: 'UZS', flag: '🇺🇿' },
  KGS: { country: 'Кыргызстан', currency: 'KGS', flag: '🇰🇬' },
  AMD: { country: 'Армения', currency: 'AMD', flag: '🇦🇲' },
  KZT: { country: 'Казахстан', currency: 'KZT', flag: '🇰🇿' },
};

const state = {
  corridor: 'TJS', range: 365, mode: 'history', selectedDate: null,
  points: [], signals: [], geometry: null, replayStartedAt: 0, replayFrame: 0, replayPushSent: false,
};
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

function visibleHistory() {
  const all = window.DEMO_DATA.corridors[state.corridor];
  const start = state.range === 'all' ? 0 : Math.max(0, all.points.length - Number(state.range));
  const points = all.points.slice(start).map(([date, rate]) => ({ date, rate, ts: Date.parse(date) }));
  return { points, signals: all.signals.filter((signal) => signal.date >= points[0].date) };
}

function predictionSource() { return window.REPLAY_DATA.corridors[state.corridor]; }
function selectedReplay() { return state.selectedDate ? predictionSource().replays[state.selectedDate] : null; }

function renderTabs() {
  $('#corridor-tabs').innerHTML = Object.entries(CORRIDORS).map(([code, item]) => `
    <button class="corridor-tab ${code === state.corridor ? 'active' : ''}" data-corridor="${code}" aria-pressed="${code === state.corridor}">
      <strong>${item.flag} ${code} / RUB</strong><span>${item.country}</span>
    </button>`).join('');
}

function resizeCanvas() {
  const rect = chartWrap.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio);
  canvas.style.width = `${rect.width}px`; canvas.style.height = `${rect.height}px`;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width: rect.width, height: rect.height };
}

function chartGeometry(points, width, height, extraRates = []) {
  const pad = { left: 22, right: 78, top: 26, bottom: 36 };
  const rates = points.map((point) => point.rate).concat(extraRates);
  const min = Math.min(...rates), max = Math.max(...rates);
  const spread = Math.max(max - min, Math.abs(max) * .002, .000001);
  const low = min - spread * .12, high = max + spread * .14;
  const firstTs = points[0].ts, lastTs = points.at(-1).ts;
  return {
    width, height, pad, min: low, max: high,
    x: (ts) => pad.left + (ts - firstTs) / Math.max(1, lastTs - firstTs) * (width - pad.left - pad.right),
    y: (rate) => pad.top + (high - rate) / (high - low) * (height - pad.top - pad.bottom),
  };
}

function drawGrid(points, geometry) {
  const { width, height, pad, min: low, max: high, x } = geometry;
  ctx.clearRect(0, 0, width, height); ctx.lineWidth = 1; ctx.font = '11px Inter, sans-serif';
  for (let i = 0; i <= 5; i += 1) {
    const yy = pad.top + (height - pad.top - pad.bottom) * i / 5;
    ctx.strokeStyle = '#252831'; ctx.setLineDash([3, 5]); ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right, yy); ctx.stroke();
    ctx.fillStyle = '#6f7480'; ctx.textAlign = 'left'; ctx.fillText(fmt.format(high - (high - low) * i / 5), width - pad.right + 10, yy + 4);
  }
  const first = new Date(points[0].ts), last = new Date(points.at(-1).ts);
  const monday = new Date(first); monday.setUTCDate(monday.getUTCDate() + ((8 - monday.getUTCDay()) % 7));
  ctx.setLineDash([]);
  for (const week = new Date(monday); week <= last; week.setUTCDate(week.getUTCDate() + 7)) {
    const xx = x(week.getTime()); ctx.strokeStyle = week.getUTCDate() <= 7 ? '#2b2e3677' : '#20232a70';
    ctx.beginPath(); ctx.moveTo(xx, pad.top); ctx.lineTo(xx, height - pad.bottom); ctx.stroke();
  }
  for (let i = 0; i <= 5; i += 1) {
    const point = points[Math.round((points.length - 1) * i / 5)], xx = x(point.ts);
    ctx.fillStyle = '#656a75'; ctx.textAlign = i === 0 ? 'left' : i === 5 ? 'right' : 'center';
    ctx.fillText(new Intl.DateTimeFormat('ru-RU', { month: 'short', year: '2-digit' }).format(point.ts), xx, height - 13);
  }
  ctx.setLineDash([]); ctx.textAlign = 'left';
}

function drawLine(points, geometry, color, width = 2, dashed = false, progress = 1) {
  if (!points.length || progress <= 0) return;
  const scaled = Math.min(1, progress) * (points.length - 1), complete = Math.floor(scaled), fraction = scaled - complete;
  const visible = points.slice(0, complete + 1);
  if (complete < points.length - 1 && fraction > 0) {
    const a = points[complete], b = points[complete + 1];
    visible.push({ ts: a.ts + (b.ts - a.ts) * fraction, rate: a.rate + (b.rate - a.rate) * fraction });
  }
  ctx.beginPath(); visible.forEach((point, index) => index ? ctx.lineTo(geometry.x(point.ts), geometry.y(point.rate)) : ctx.moveTo(geometry.x(point.ts), geometry.y(point.rate)));
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.setLineDash(dashed ? [7, 5] : []); ctx.shadowBlur = dashed ? 12 : 8; ctx.shadowColor = `${color}55`; ctx.stroke(); ctx.shadowBlur = 0; ctx.setLineDash([]);
}

function drawLastPrice(point, geometry, color) {
  const { width, pad, y } = geometry;
  ctx.setLineDash([4, 4]); ctx.strokeStyle = `${color}77`; ctx.beginPath(); ctx.moveTo(pad.left, y(point.rate)); ctx.lineTo(width - pad.right, y(point.rate)); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = color; ctx.fillRect(width - pad.right, y(point.rate) - 10, 66, 20);
  ctx.fillStyle = '#fff'; ctx.font = '700 11px Inter, sans-serif'; ctx.fillText(fmt.format(point.rate), width - pad.right + 7, y(point.rate) + 4);
}

function drawHistoryChart() {
  const { points, signals } = visibleHistory(); state.points = points; state.signals = signals;
  const { width, height } = resizeCanvas(), geometry = chartGeometry(points, width, height); state.geometry = geometry;
  drawGrid(points, geometry); drawLine(points, geometry, '#ff5a51'); drawLastPrice(points.at(-1), geometry, '#f13c32'); renderMarkers();
  const change = (points.at(-1).rate / points[0].rate - 1) * 100;
  $('#ticker-rate').textContent = fmt.format(points.at(-1).rate);
  $('#ticker-change').textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2).replace('.', ',')}% за период`;
  $('#ticker-change').classList.toggle('negative', change > 0);
}

function drawPredictionChart(now = performance.now()) {
  if (state.mode !== 'prediction') return;
  const source = predictionSource();
  const points = source.year.map(([date, rate]) => ({ date, rate, ts: Date.parse(date) }));
  const replay = selectedReplay();
  const predicted = replay ? replay.predicted.map(([date, rate]) => ({ date, rate, ts: Date.parse(date) })) : [];
  const { width, height } = resizeCanvas();
  const geometry = chartGeometry(points, width, height, predicted.map((point) => point.rate));
  state.geometry = geometry; state.points = points;
  drawGrid(points, geometry); drawLine(points, geometry, '#ff5a51', 1.8); drawLastPrice(points.at(-1), geometry, '#f13c32');

  if (!replay) {
    state.signals = []; renderMarkers(true); updatePredictionPrompt(); return;
  }

  const elapsed = now - state.replayStartedAt;
  const selectedTs = Date.parse(replay.date), endTs = predicted.at(-1).ts;
  const selectedX = geometry.x(selectedTs), endX = geometry.x(endTs);
  ctx.fillStyle = '#a98cff0e'; ctx.fillRect(selectedX, geometry.pad.top, Math.max(3, endX - selectedX), height - geometry.pad.top - geometry.pad.bottom);
  ctx.strokeStyle = '#d9dce499'; ctx.setLineDash([4, 5]); ctx.beginPath(); ctx.moveTo(selectedX, geometry.pad.top); ctx.lineTo(selectedX, height - geometry.pad.bottom); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = '#e7e8ec'; ctx.font = '700 11px Inter, sans-serif'; ctx.fillText('ВЫБРАННЫЙ ДЕНЬ', selectedX + 8, geometry.pad.top + 15);
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(selectedX, geometry.y(predicted[0].rate), 5, 0, Math.PI * 2); ctx.fill();

  drawLine(predicted, geometry, '#a98cff', 3, true, (elapsed - 300) / 1000);
  const predictedVisible = elapsed >= 1450, goldenVisible = elapsed >= 2250, decisionVisible = elapsed >= 3050;
  state.signals = [
    ...(predictedVisible ? replay.predictedSignals : []),
    ...(goldenVisible ? replay.goldenSignals : []),
    ...(decisionVisible && replay.todaySignal ? [replay.todaySignal] : []),
  ];
  renderMarkers(true); updatePredictionDetail(replay, elapsed);
  $('#ticker-rate').textContent = fmt.format(predicted[0].rate);
  $('#ticker-change').textContent = `TimesFM H5: ${replay.comparison.meanChangeH5Bps >= 0 ? '+' : ''}${replay.comparison.meanChangeH5Bps.toFixed(1).replace('.', ',')} bps`;
  $('#ticker-change').classList.toggle('negative', replay.comparison.meanChangeH5Bps > 0);

  if (decisionVisible && replay.push.sent && !state.replayPushSent) {
    state.replayPushSent = true; sendPush(replay.todaySignal);
  }
  if (elapsed < 3500) state.replayFrame = requestAnimationFrame(drawPredictionChart);
}

function renderMarkers(replayMode = false) {
  const { x, y } = state.geometry;
  $('#signal-layer').innerHTML = state.signals.map((signal, index) => {
    const series = replayMode ? ` ${signal.series || ''}` : '';
    const title = signal.series === 'predicted' ? 'Сигнал TimesFM' : PUSH_MESSAGES[signal.type].label;
    return `<button class="signal-marker ${typeClass(signal.type)}${series}" style="left:${x(Date.parse(signal.date))}px;top:${y(signal.rate)}px" data-signal="${index}" aria-label="${title}, ${dateFmt.format(Date.parse(signal.date))}">${signal.series === 'predicted' ? '◇' : '✦'}</button>`;
  }).join('');
}

function updatePredictionPrompt() {
  $('#ticker-rate').textContent = fmt.format(state.points.at(-1).rate); $('#ticker-change').textContent = 'выберите день на графике'; $('#ticker-change').classList.remove('negative');
  $('#signal-detail').innerHTML = '<div class="empty-detail"><span class="radar-icon">⌖</span><h2>Выберите день</h2><p>Нажмите на любую точку годового графика. От неё TimesFM построит прогноз поверх фактического курса.</p></div>';
  $('#stat-total').textContent = '—'; $('#stat-good').textContent = '—'; $('#stat-closing').textContent = '—'; $('#stat-fact').textContent = '—';
}

function updatePredictionDetail(replay, elapsed) {
  const c = replay.comparison;
  let stage = 'Строим TimesFM-прогноз от выбранного дня';
  if (elapsed >= 1450) stage = 'Расставляем predicted-сигналы';
  if (elapsed >= 2250) stage = 'Показываем golden-сигналы по факту';
  if (elapsed >= 3050) stage = replay.push.sent ? 'Push отправлен' : 'Push не отправлен';
  const verdict = elapsed < 3050
    ? '<div class="push-verdict pending"><b>Push-политика</b><span>Проверяем сигнал в выбранной точке…</span></div>'
    : `<div class="push-verdict ${replay.push.sent ? 'sent' : 'suppressed'}"><b>${replay.push.sent ? '✓ Отправлен' : '× Не отправлен'}</b><span>${replay.push.explanation}</span></div>`;
  $('#signal-detail').innerHTML = `
    <div class="detail-head"><span class="badge replay-badge">TIMESFM</span><time>${dateFmt.format(Date.parse(replay.date))}</time></div>
    <h2 class="detail-title">${stage}</h2><p class="detail-reason">Пунктир — прогноз, красная линия — то, что произошло на самом деле.</p>
    ${verdict}
    <div class="metric-row">
      <div class="metric"><span>Среднее H1…H5</span><strong>${c.meanChangeH5Bps >= 0 ? '+' : ''}${c.meanChangeH5Bps.toFixed(1)} bps</strong></div>
      <div class="metric"><span>Дней хуже</span><strong>${c.worseDaysH5} из 5</strong></div>
      <div class="metric"><span>Predicted</span><strong>${c.predictedCount} сигн.</strong></div>
      <div class="metric"><span>Golden</span><strong>${c.goldenCount} сигн.</strong></div>
    </div>`;
  const predicted = replay.predictedSignals;
  $('#stat-total').textContent = predicted.length;
  $('#stat-good').textContent = predicted.filter((signal) => signal.type === 'good_now').length;
  $('#stat-closing').textContent = predicted.filter((signal) => signal.type === 'window_closing').length;
  $('#stat-fact').textContent = predicted.filter((signal) => signal.type === 'positive_market_fact').length;
}

function selectPredictionDate(clientX) {
  const rect = chartWrap.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left - state.geometry.pad.left) / (state.geometry.width - state.geometry.pad.left - state.geometry.pad.right)));
  const targetTs = state.points[0].ts + ratio * (state.points.at(-1).ts - state.points[0].ts);
  const available = Object.keys(predictionSource().replays);
  state.selectedDate = available.reduce((best, date) => Math.abs(Date.parse(date) - targetTs) < Math.abs(Date.parse(best) - targetTs) ? date : best, available[0]);
  $('#push-stack').innerHTML = '';
  cancelAnimationFrame(state.replayFrame); state.replayPushSent = false; state.replayStartedAt = performance.now();
  $('#mode-hint span').textContent = `${dateFmt.format(Date.parse(state.selectedDate))} · строим прогноз`;
  drawPredictionChart(state.replayStartedAt);
}

function setMode(mode) {
  state.mode = mode; state.selectedDate = null; state.replayPushSent = false; cancelAnimationFrame(state.replayFrame);
  $('#history-mode').classList.toggle('active', mode === 'history'); $('#prediction-mode').classList.toggle('active', mode === 'prediction');
  $('#history-mode').setAttribute('aria-pressed', mode === 'history'); $('#prediction-mode').setAttribute('aria-pressed', mode === 'prediction');
  document.body.classList.toggle('prediction-mode', mode === 'prediction');
  if (mode === 'prediction') {
    $('#mode-hint span').textContent = 'Нажмите на день, чтобы построить прогноз';
    $('#chart-legend').innerHTML = '<span><i class="line-key golden"></i> Фактический курс</span><span><i class="line-key predicted"></i> TimesFM-прогноз</span><span><i class="dot candidate"></i> predicted</span><span><i class="dot good"></i> golden</span><small>Сначала выберите день на графике</small>';
    $('.logic-card').innerHTML = '<div class="section-label">ЛОГИКА РЕЖИМА</div><p>Вы выбираете дату T. Модель видит только прошлое, а затем мы накладываем её прогноз и сигналы на уже известный фактический ряд.</p>';
    drawPredictionChart();
  } else {
    $('#mode-hint span').textContent = 'История сигналов за год';
    $('#chart-legend').innerHTML = '<span><i class="dot good"></i> Выгодный момент</span><span><i class="dot closing"></i> Окно закрывается</span><span><i class="dot fact"></i> Позитивный факт</span><small>Нажмите на любую метку, чтобы отправить push</small>';
    $('.logic-card').innerHTML = '<div class="section-label">ПОЧЕМУ ЭТО НЕ ПРОГНОЗ</div><p>Метки <b>good</b> и <b>closing</b> — ретроспективная разметка для проверки идеи. В продуктовом контуре модель использует только данные, доступные на дату T.</p>';
    resetSignalDetail(); updateStats(); drawHistoryChart();
  }
}

function resetSignalDetail() {
  $('#signal-detail').innerHTML = '<div class="empty-detail"><span class="radar-icon">⌁</span><h2>Выберите сигнал</h2><p>Нажмите на метку над графиком — здесь появится разбор и сразу прилетит тестовый push.</p></div>';
}

function selectCorridor(code) {
  state.corridor = code; renderTabs();
  $('#ticker-code').textContent = `${code} / RUB`; $('#ticker-country').textContent = CORRIDORS[code].country;
  $('#transfer-country').value = code; updateTransfer();
  if (state.mode === 'prediction') setMode('prediction'); else { updateStats(); drawHistoryChart(); }
}

function updateStats() {
  const summary = window.DEMO_DATA.corridors[state.corridor].summary;
  $('#stat-total').textContent = summary.total; $('#stat-good').textContent = summary.good; $('#stat-closing').textContent = summary.closing; $('#stat-fact').textContent = summary.fact;
}

function signalReason(signal) {
  if (signal.timesfm) return `TimesFM: среднее H1…H5 = ${signal.timesfm.meanChangeH5Bps.toFixed(1)} bps; ухудшение — ${signal.timesfm.worseDaysH5} дней из 5.`;
  if (signal.series === 'predicted') return 'Кандидат, выставленный time-series моделью по данным, доступным на дату T.';
  if (signal.type === 'good_now') return `Отклонение от минимума окна укладывается в 100 bps. Future regret: ${signal.futureRegretBps ?? 0} bps.`;
  if (signal.type === 'window_closing') return `Отскок от прошлого минимума: ${signal.reboundBps ?? '—'} bps. Будущая медиана хуже на ${signal.futureMedianChangeBps ?? '—'} bps.`;
  const facts = signal.facts || []; return facts.length ? facts.map((key) => FACT_MESSAGES[key]).join(' ') : 'Зафиксирован положительный рыночный факт.';
}

function showSignal(signal) {
  const item = CORRIDORS[state.corridor], copy = PUSH_MESSAGES[signal.type];
  const color = signal.type === 'good_now' ? 'var(--green)' : signal.type === 'window_closing' ? 'var(--amber)' : 'var(--blue)';
  $('#signal-detail').innerHTML = `<div class="detail-head"><span class="badge" style="background:${color}">${copy.label}</span><time>${dateFmt.format(Date.parse(signal.date))}</time></div><h2 class="detail-title">Почему появился сигнал</h2><p class="detail-reason">${signalReason(signal)}</p><div class="metric-row"><div class="metric"><span>Курс в точке</span><strong>${fmt.format(signal.rate)} ₽/${item.currency}</strong></div><div class="metric"><span>Получатель</span><strong>${money.format(signal.recipientAmount ?? 22000 / signal.rate)} ${item.currency}</strong></div><div class="metric"><span>Эффект*</span><strong>${(signal.effectUnits ?? 0) >= 0 ? '+' : ''}${money.format(signal.effectUnits ?? 0)} ${item.currency}</strong></div><div class="metric"><span>Изменение 5д</span><strong>${(signal.ret5Pct ?? 0) >= 0 ? '+' : ''}${signal.ret5Pct ?? 0}%</strong></div></div>`;
  sendPush(signal);
}

function sendPush(signal) {
  const corridor = state.corridor, copy = getPushCopy(signal.type, { ...CORRIDORS[corridor], facts: signal.facts || [] });
  const toast = document.createElement('button'); toast.className = 'push-toast';
  toast.innerHTML = `<span class="push-app">A</span><span><strong>${copy.title}</strong><span>${copy.body}</span></span><small>сейчас</small>`;
  toast.addEventListener('click', () => { openDrawer(corridor); toast.remove(); }); $('#push-stack').prepend(toast); setTimeout(() => toast.remove(), 11000);
}

function nearestPoint(clientX) {
  const rect = chartWrap.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left - state.geometry.pad.left) / (state.geometry.width - state.geometry.pad.left - state.geometry.pad.right)));
  return state.points[Math.round(ratio * (state.points.length - 1))];
}
function moveCrosshair(event) {
  if (!state.geometry || !state.points.length) return;
  const rect = chartWrap.getBoundingClientRect(), point = nearestPoint(event.clientX), xx = state.geometry.x(point.ts), yy = state.geometry.y(point.rate);
  const crosshair = $('#crosshair'); crosshair.hidden = false; crosshair.querySelector('span').style.left = `${xx}px`; crosshair.querySelector('i').style.top = `${yy}px`;
  const tip = $('#chart-tooltip'); tip.hidden = false; tip.innerHTML = `<strong>${fmt.format(point.rate)} RUB / ${state.corridor}</strong><span>${dateFmt.format(point.ts)}</span>`;
  tip.style.left = `${Math.min(xx + 12, rect.width - 165)}px`; tip.style.top = `${Math.max(10, yy - 48)}px`;
}

function openDrawer(code = state.corridor) { $('#transfer-country').value = CORRIDORS[code] ? code : state.corridor; $('#transfer-drawer').classList.add('open'); $('#transfer-drawer').setAttribute('aria-hidden', 'false'); updateTransfer(); }
function closeDrawer() { $('#transfer-drawer').classList.remove('open'); $('#transfer-drawer').setAttribute('aria-hidden', 'true'); }
function updateTransfer() {
  const code = $('#transfer-country').value || state.corridor, data = window.DEMO_DATA.corridors[code]; if (!data) return;
  const amount = Number($('#transfer-amount').value || 0), rate = data.points.at(-1)[1];
  $('#transfer-receives').textContent = `${money.format(amount / rate)} ${code}`; $('#transfer-rate-label').textContent = `1 ${code} = ${fmt.format(rate)} ₽ · демо-ориентир`;
}

$('#corridor-tabs').addEventListener('click', (event) => { const button = event.target.closest('[data-corridor]'); if (button) selectCorridor(button.dataset.corridor); });
$('.range-picker').addEventListener('click', (event) => { const button = event.target.closest('[data-range]'); if (!button || state.mode !== 'history') return; state.range = button.dataset.range; document.querySelectorAll('[data-range]').forEach((item) => item.classList.toggle('active', item === button)); drawHistoryChart(); });
$('#history-mode').addEventListener('click', () => setMode('history')); $('#prediction-mode').addEventListener('click', () => setMode('prediction'));
$('#signal-layer').addEventListener('click', (event) => { const button = event.target.closest('[data-signal]'); if (button) { event.stopPropagation(); showSignal(state.signals[Number(button.dataset.signal)]); } });
chartWrap.addEventListener('click', (event) => { if (state.mode === 'prediction' && !event.target.closest('[data-signal]')) selectPredictionDate(event.clientX); });
chartWrap.addEventListener('mousemove', moveCrosshair); chartWrap.addEventListener('mouseleave', () => { $('#crosshair').hidden = true; $('#chart-tooltip').hidden = true; });
$('#open-transfer').addEventListener('click', () => openDrawer()); document.querySelectorAll('[data-close-drawer]').forEach((item) => item.addEventListener('click', closeDrawer));
$('#transfer-country').addEventListener('change', updateTransfer); $('#transfer-amount').addEventListener('input', updateTransfer);
$('#transfer-form').addEventListener('submit', (event) => { event.preventDefault(); closeDrawer(); const toast = document.createElement('div'); toast.className = 'push-toast'; toast.innerHTML = '<span class="push-app">✓</span><span><strong>Демо-перевод создан</strong><span>Деньги не списывались и не отправлялись.</span></span><small>сейчас</small>'; $('#push-stack').prepend(toast); setTimeout(() => toast.remove(), 7000); });
window.addEventListener('resize', () => requestAnimationFrame(() => state.mode === 'history' ? drawHistoryChart() : drawPredictionChart()));

$('#transfer-country').innerHTML = Object.entries(CORRIDORS).map(([code, item]) => `<option value="${code}">${item.flag} ${item.country}</option>`).join('');
$('#transfer-country').value = state.corridor; renderTabs(); selectCorridor(state.corridor);
if (new URLSearchParams(location.search).get('mode') === 'prediction') setMode('prediction');
