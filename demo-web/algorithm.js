const ALGO_CORRIDORS = {
  TJS: { country: 'Таджикистан', currency: 'TJS', flag: '🇹🇯' },
  UZS: { country: 'Узбекистан', currency: 'UZS', flag: '🇺🇿' },
  KGS: { country: 'Кыргызстан', currency: 'KGS', flag: '🇰🇬' },
  AMD: { country: 'Армения', currency: 'AMD', flag: '🇦🇲' },
  KZT: { country: 'Казахстан', currency: 'KZT', flag: '🇰🇿' },
};

const STAGES = ['line', 'lows', 'good', 'fact', 'closing'];
const STAGE_INFO = {
  line: {
    title: 'Загружаем курс без разметки',
    copy: 'Сначала видим только исторический ряд.',
    rule: 'Строим исторический ряд курса',
    formula: 'rₜ = RUB / 1 unit',
  },
  lows: {
    title: 'Ищем кандидатов в локальных лоях',
    copy: 'Нейтральные точки — ещё не сигналы, а места для проверки.',
    rule: 'Для каждой даты сравниваем курс с локальным окружением',
    formula: 'rₜ = min(rₜ₋₉ … rₜ₊₉)',
  },
  good: {
    title: 'Применяем правило good',
    copy: 'Зелёные точки переезжают на подтверждённые выгодные даты.',
    rule: 'rateₜ ≤ min(rateₜ₋₁₀ … rateₜ₊₁₀) × 1,01',
    formula: 'rₜ ≤ min(rₜ±10) × 1,01',
  },
  fact: {
    title: 'Добавляем положительные market facts',
    copy: 'Синие точки появляются только по данным, известным на дату T.',
    rule: '3 снижения подряд ∨ улучшение ≥1% за неделю ∨ нижние 10% за 30 дней',
    formula: 'D₃ ∨ W₇ ≥ 1% ∨ P₃₀ ≤ 10%',
  },
  closing: {
    title: 'Находим закрывающееся окно',
    copy: 'Все метки заняли финальные позиции — теперь на них можно нажимать.',
    rule: 'good → closing → fact · cooldown 4 дня · максимум 2 push в неделю',
    formula: '100 < rebound ≤ 200 bps ∧ Δmed₊₁₀ ≥ 100 bps',
  },
};

const algoState = {
  corridor: 'TJS',
  stage: 'line',
  points: [],
  signals: [],
  geometry: null,
  timers: [],
};

const aq = (selector) => document.querySelector(selector);
const algoCanvas = aq('#algo-chart');
const algoCtx = algoCanvas.getContext('2d');
const algoWrap = aq('#algo-chart-wrap');
const algoFmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 });
const algoDate = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });

function algoTypeClass(type) {
  return type === 'good_now' ? 'good' : type === 'window_closing' ? 'closing' : 'fact';
}

function renderAlgoTabs() {
  aq('#algo-tabs').innerHTML = Object.entries(ALGO_CORRIDORS).map(([code, item]) => `
    <button class="corridor-tab ${code === algoState.corridor ? 'active' : ''}" data-corridor="${code}" aria-pressed="${code === algoState.corridor}">
      <strong>${item.flag} ${code} / RUB</strong><span>${item.country}</span>
    </button>`).join('');
}

function prepareData() {
  const source = window.DEMO_DATA.corridors[algoState.corridor];
  algoState.points = source.points.map(([date, rate]) => ({ date, rate, ts: Date.parse(date) }));
  algoState.signals = source.signals.map((signal) => ({ ...signal, ts: Date.parse(signal.date) }));
}

function resizeAlgoCanvas() {
  const rect = algoWrap.getBoundingClientRect();
  if (rect.width < 100 || rect.height < 100) return null;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  algoCanvas.width = Math.round(rect.width * ratio);
  algoCanvas.height = Math.round(rect.height * ratio);
  algoCanvas.style.width = `${rect.width}px`;
  algoCanvas.style.height = `${rect.height}px`;
  algoCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width: rect.width, height: rect.height };
}

function drawAlgoChart() {
  const points = algoState.points;
  const size = resizeAlgoCanvas();
  if (!size || !points.length) return false;
  const { width, height } = size;
  const pad = { left: 28, right: 82, top: 30, bottom: 38 };
  const min = Math.min(...points.map((point) => point.rate));
  const max = Math.max(...points.map((point) => point.rate));
  const spread = Math.max(max - min, max * .002);
  const low = min - spread * .12;
  const high = max + spread * .12;
  const x = (ts) => pad.left + (ts - points[0].ts) / (points.at(-1).ts - points[0].ts) * (width - pad.left - pad.right);
  const y = (rate) => pad.top + (high - rate) / (high - low) * (height - pad.top - pad.bottom);
  algoState.geometry = { width, height, pad, x, y };

  algoCtx.clearRect(0, 0, width, height);
  algoCtx.font = '11px Inter, sans-serif';
  const firstDay = new Date(`${points[0].date}T00:00:00Z`);
  const lastDay = new Date(`${points.at(-1).date}T00:00:00Z`);
  const daysToMonday = (8 - firstDay.getUTCDay()) % 7;
  const monday = new Date(firstDay);
  monday.setUTCDate(monday.getUTCDate() + daysToMonday);
  algoCtx.setLineDash([]);
  algoCtx.lineWidth = 1;
  for (const week = new Date(monday); week <= lastDay; week.setUTCDate(week.getUTCDate() + 7)) {
    const xx = x(week.getTime());
    const isMonthStart = week.getUTCDate() <= 7;
    algoCtx.strokeStyle = isMonthStart ? '#2b2e365c' : '#20232a6b';
    algoCtx.beginPath(); algoCtx.moveTo(xx, pad.top); algoCtx.lineTo(xx, height - pad.bottom); algoCtx.stroke();
  }
  for (let index = 0; index <= 5; index += 1) {
    const yy = pad.top + (height - pad.top - pad.bottom) * index / 5;
    algoCtx.strokeStyle = '#252831';
    algoCtx.setLineDash([3, 5]);
    algoCtx.beginPath(); algoCtx.moveTo(pad.left, yy); algoCtx.lineTo(width - pad.right, yy); algoCtx.stroke();
    algoCtx.fillStyle = '#6f7480';
    algoCtx.fillText(algoFmt.format(high - (high - low) * index / 5), width - pad.right + 10, yy + 4);
  }
  for (let index = 0; index <= 5; index += 1) {
    const point = points[Math.round((points.length - 1) * index / 5)];
    const xx = x(point.ts);
    algoCtx.strokeStyle = '#20232a';
    algoCtx.beginPath(); algoCtx.moveTo(xx, pad.top); algoCtx.lineTo(xx, height - pad.bottom); algoCtx.stroke();
    algoCtx.fillStyle = '#656a75';
    algoCtx.textAlign = index === 0 ? 'left' : index === 5 ? 'right' : 'center';
    algoCtx.fillText(new Intl.DateTimeFormat('ru-RU', { month: 'short', year: '2-digit' }).format(point.ts), xx, height - 13);
  }
  algoCtx.setLineDash([]);
  const gradient = algoCtx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, '#f13c3238'); gradient.addColorStop(1, '#f13c3200');
  algoCtx.beginPath();
  points.forEach((point, index) => index ? algoCtx.lineTo(x(point.ts), y(point.rate)) : algoCtx.moveTo(x(point.ts), y(point.rate)));
  algoCtx.lineTo(x(points.at(-1).ts), height - pad.bottom); algoCtx.lineTo(x(points[0].ts), height - pad.bottom); algoCtx.closePath();
  algoCtx.fillStyle = gradient; algoCtx.fill();
  algoCtx.beginPath();
  points.forEach((point, index) => index ? algoCtx.lineTo(x(point.ts), y(point.rate)) : algoCtx.moveTo(x(point.ts), y(point.rate)));
  algoCtx.strokeStyle = '#ff5a51'; algoCtx.lineWidth = 2; algoCtx.shadowBlur = 12; algoCtx.shadowColor = '#f13c3266'; algoCtx.stroke(); algoCtx.shadowBlur = 0;
  positionAlgoMarkers(algoState.stage);
  return true;
}

function localLowFor(signal) {
  const points = algoState.points;
  let center = points.findIndex((point) => point.date >= signal.date);
  center = Math.max(0, center);
  const start = Math.max(0, center - 9);
  const end = Math.min(points.length, center + 10);
  return points.slice(start, end).reduce((lowest, point) => point.rate < lowest.rate ? point : lowest);
}

function createAlgoMarkers() {
  const layer = aq('#algo-marker-layer');
  layer.innerHTML = algoState.signals.map((signal, index) => {
    const low = localLowFor(signal);
    return `<button class="algo-marker candidate" data-index="${index}" data-low-date="${low.date}" data-low-rate="${low.rate}" aria-label="Кандидат сигнала" disabled><span>•</span></button>`;
  }).join('');
  positionAlgoMarkers('line', true);
}

function isRevealed(type, stage) {
  if (type === 'good_now') return ['good', 'fact', 'closing'].includes(stage);
  if (type === 'positive_market_fact') return ['fact', 'closing'].includes(stage);
  return stage === 'closing';
}

function positionAlgoMarkers(stage, immediate = false) {
  if (!algoState.geometry) return;
  const { x, y } = algoState.geometry;
  aq('#algo-marker-layer').querySelectorAll('.algo-marker').forEach((marker) => {
    const signal = algoState.signals[Number(marker.dataset.index)];
    const revealed = isRevealed(signal.type, stage);
    const date = revealed ? signal.date : marker.dataset.lowDate;
    const rate = revealed ? signal.rate : Number(marker.dataset.lowRate);
    marker.className = `algo-marker ${revealed ? algoTypeClass(signal.type) : 'candidate'}${immediate ? ' no-transition' : ''}`;
    marker.style.left = `${x(Date.parse(date))}px`;
    marker.style.top = `${y(rate)}px`;
    marker.style.opacity = stage === 'line' ? '0' : '1';
    marker.disabled = stage !== 'closing';
    marker.setAttribute('aria-label', revealed ? `${PUSH_MESSAGES[signal.type].label}, ${algoDate.format(signal.ts)}` : 'Кандидат в локальном минимуме');
    if (immediate) requestAnimationFrame(() => marker.classList.remove('no-transition'));
  });
}

function setStage(stage) {
  algoState.stage = stage;
  const stageIndex = STAGES.indexOf(stage);
  document.querySelectorAll('.stage').forEach((item, index) => {
    item.classList.toggle('active', index === stageIndex);
    item.classList.toggle('done', index < stageIndex);
  });
  document.querySelectorAll('.stage-strip > i').forEach((item, index) => item.classList.toggle('done', index < stageIndex));
  const info = STAGE_INFO[stage];
  document.querySelectorAll('.stage-formula').forEach((item) => item.remove());
  const activeStage = document.querySelector(`.stage[data-stage="${stage}"]`);
  const formula = document.createElement('code');
  formula.className = 'stage-formula';
  formula.textContent = info.formula;
  activeStage.append(formula);
  aq('#stage-title').textContent = info.title;
  aq('#stage-copy').textContent = info.copy;
  aq('#stage-counter').textContent = `0${stageIndex + 1} / 05`;
  aq('#algorithm-rule').innerHTML = `<span>Текущий шаг</span><b>${info.rule}</b>`;
  positionAlgoMarkers(stage);
}

function startSequence() {
  algoState.timers.forEach(clearTimeout);
  algoState.timers = [];
  setStage('line');
  const schedule = [
    ['lows', 1000],
    ['good', 2400],
    ['fact', 3900],
    ['closing', 5400],
  ];
  schedule.forEach(([stage, delay]) => algoState.timers.push(setTimeout(() => setStage(stage), delay)));
}

function showAlgoHover(marker) {
  const signal = algoState.signals[Number(marker.dataset.index)];
  const item = ALGO_CORRIDORS[algoState.corridor];
  const tip = aq('#algo-hover');
  tip.hidden = false;
  tip.innerHTML = `<strong>${PUSH_MESSAGES[signal.type].label}</strong><span>${algoDate.format(signal.ts)} · ${algoFmt.format(signal.rate)} ₽/${item.currency}</span><code>${signalCalculation(signal)}</code>`;
  const wrapRect = algoWrap.getBoundingClientRect();
  const markerRect = marker.getBoundingClientRect();
  tip.style.left = `${Math.min(markerRect.left - wrapRect.left + 14, wrapRect.width - 210)}px`;
  tip.style.top = `${Math.max(10, markerRect.top - wrapRect.top - 50)}px`;
}

function signalCalculation(signal) {
  if (signal.type === 'good_now') {
    return `regret = ${signal.futureRegretBps ?? 0} bps ≤ 100 bps`;
  }
  if (signal.type === 'window_closing') {
    return `${signal.reboundBps} bps ∈ (100; 200] · Δmed = ${signal.futureMedianChangeBps} bps`;
  }
  const checks = [];
  if (signal.facts.includes('decline_3')) checks.push('D₃ = true');
  if (signal.facts.includes('weekly_gain')) checks.push('W₇ ≥ 1%');
  if (signal.facts.includes('low_percentile')) checks.push('P₃₀ ≤ 10%');
  return checks.join(' ∨ ') || `Δr₅ = ${signal.ret5Pct}%`;
}

function sendAlgoPush(signal) {
  const item = ALGO_CORRIDORS[algoState.corridor];
  const copy = PUSH_MESSAGES[signal.type];
  const facts = signal.facts.length ? signal.facts.map((key) => FACT_MESSAGES[key]).join(' ') : 'Курс показывает положительную динамику.';
  const toast = document.createElement('button');
  toast.className = 'push-toast';
  toast.innerHTML = `<span class="push-app">A</span><span><strong>${copy.title}</strong><span>${copy.body({ ...item, fact: facts })}</span></span><small>сейчас</small>`;
  aq('#push-stack').prepend(toast);
  setTimeout(() => toast.remove(), 10000);
}

function selectAlgoCorridor(code) {
  algoState.timers.forEach(clearTimeout);
  algoState.corridor = code;
  renderAlgoTabs();
  prepareData();
  algoState.geometry = null;
  aq('#algo-marker-layer').innerHTML = '';
  renderSelectedCorridor();
}

function renderSelectedCorridor(attempt = 0) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (!drawAlgoChart()) {
      if (attempt < 5) setTimeout(() => renderSelectedCorridor(attempt + 1), 100);
      return;
    }
    createAlgoMarkers();
    startSequence();
  }));
}

aq('#algo-tabs').addEventListener('click', (event) => {
  const button = event.target.closest('[data-corridor]');
  if (button) selectAlgoCorridor(button.dataset.corridor);
});
aq('#replay').addEventListener('click', startSequence);
aq('#algo-marker-layer').addEventListener('mouseover', (event) => {
  const marker = event.target.closest('.algo-marker:not(:disabled)');
  if (marker) showAlgoHover(marker);
});
aq('#algo-marker-layer').addEventListener('mouseout', () => { aq('#algo-hover').hidden = true; });
aq('#algo-marker-layer').addEventListener('click', (event) => {
  const marker = event.target.closest('.algo-marker:not(:disabled)');
  if (marker) sendAlgoPush(algoState.signals[Number(marker.dataset.index)]);
});
window.addEventListener('resize', () => requestAnimationFrame(drawAlgoChart));
window.addEventListener('load', () => selectAlgoCorridor(algoState.corridor), { once: true });
