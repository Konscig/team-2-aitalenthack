const app = document.querySelector('#app');
const state = { screen: 'home', corridor: null, method: null, signal: null, transfer: null };
const seenPushes = new Set();
const countries = { TJS:['Таджикистан','🇹🇯'], UZS:['Узбекистан','🇺🇿'], KGS:['Кыргызстан','🇰🇬'], AMD:['Армения','🇦🇲'], KZT:['Казахстан','🇰🇿'] };
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
const countryName = () => countries[state.corridor]?.[0] || 'страна';
function go(screen, extra = {}) { Object.assign(state, extra, { screen }); render(); }
function header(title, back = 'home') { return `<div class="top"><button class="back" type="button" aria-label="Назад" onclick="go('${back}')">‹</button><h1>${title}</h1></div>`; }
async function render() { const pages = { home, countries: countryList, methods, details, signal, settings, result }; app.innerHTML = await pages[state.screen](); }

function home() {
  return `${header('Платежи')}<div class="hero"><span class="demo-label">Web PoC</span><h2>Переводы за рубеж</h2><p>Демо-путь по экранным формам. Все переводы — симуляция.</p><button class="primary" type="button" onclick="go('countries')">Выбрать страну</button></div><button class="card" type="button" onclick="openSignal()"><b>🔔 Открыть демо-пуш</b><span class="sub">Показать status public-reference scenario</span></button><p class="tiny">Для верхнего баннера: POST /api/pushes. Переход из пуша задаёт только страну.</p>`;
}

function showPush(push) {
  if (seenPushes.has(push.id)) return;
  seenPushes.add(push.id);
  const banner = document.createElement('button');
  banner.className = 'push-banner';
  banner.type = 'button';
  banner.innerHTML = `<span class="push-icon">🔔</span><span><b>${escapeHtml(push.title)}</b><small>${escapeHtml(push.body)}</small>${push.model_label ? `<em>${escapeHtml(push.model_label)}</em>` : ''}</span><span class="push-time">сейчас</span>`;
  banner.onclick = () => {
    const url = new URL(push.deep_link, location.origin);
    history.replaceState({}, '', url);
    openSignal();
    banner.remove();
  };
  document.body.append(banner);
  setTimeout(() => banner.remove(), 10000);
}

async function pollPushes() {
  try {
    const pushes = await fetch('/api/pushes/inbox').then(response => response.ok ? response.json() : []);
    pushes.forEach(showPush);
  } catch (_) { /* The banner is optional for an offline demo. */ }
}

async function triggerPush(event) {
  event.preventDefault();
  const body = document.querySelector('#push-text').value.trim();
  const response = await fetch('/api/pushes', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      corridor: document.querySelector('#push-corridor').value,
      status: document.querySelector('#push-status').value,
      model_scenario: document.querySelector('#push-model').value,
      ...(body ? {body} : {}),
    }),
  });
  const result = document.querySelector('#push-result');
  if (!response.ok) { result.textContent = 'Не удалось создать тестовый push.'; return; }
  const payload = await response.json();
  result.textContent = 'Push показан. Нажми на баннер сверху, чтобы открыть перевод.';
  showPush(payload.push);
}

function countryList() {
  return `${header('Переводы за рубеж')}<p>Выберите страну получателя</p>${Object.entries(countries).map(([code,[name,flag]]) => `<button class="choice" type="button" onclick="go('methods',{corridor:'${code}',method:null})"><span class="emoji">${flag}</span><span class="grow"><b>${name}</b><span class="sub">RUB → ${code}</span></span><span>›</span></button>`).join('')}`;
}

function methods() {
  const options = [
    ['phone','По номеру телефона','Мгновенно · до 1 млн ₽','Без комиссии','📱',false],
    ['card','По номеру карты','За 1 день · до 500 000 ₽','Без комиссии','💳',false],
    ['account','По номеру счёта','За 2–5 дней · до 20 млн ₽','Информационный вариант PoC','💼',true],
  ];
  return `${header('Перевод в '+countryName(),'countries')}${options.map(([id,title,speed,fee,icon,disabled]) => `<button class="choice" type="button" ${disabled ? 'disabled aria-label="По счёту — информационный вариант"' : `onclick="go('details',{method:'${id}'})"`}><span class="emoji">${icon}</span><span class="grow"><b>${title}</b><span class="sub">${speed}<br>${fee}</span></span><span class="badge">${disabled ? 'Скоро' : id==='phone' ? 'Быстро' : 'Продолжить'}</span></button>`).join('')}<p class="tiny">Способ по счёту показан как часть исходного экрана, но его форма не входит в PoC.</p>`;
}

function details() {
  const phone = state.method === 'phone';
  const recipientLabel = phone ? 'Номер телефона получателя' : 'Номер карты получателя';
  const max = phone ? 1000000 : 500000;
  return `${header('Перевод в '+countryName(),'methods')}<p>Введите только тестовые данные: реальные реквизиты не используются.</p><form onsubmit="submitTransfer(event)"><label for="recipient">${recipientLabel}</label><input id="recipient" required minlength="3" placeholder="Тестовые данные" autocomplete="off"/><label for="amount">Сумма перевода, ₽</label><input id="amount" type="number" min="1" max="${max}" required placeholder="1000" oninput="updateQuote()"/><div id="quote" class="quote" hidden aria-live="polite"></div><label for="account">Счёт списания</label><select id="account"><option>Демо-счёт •• 1234</option><option>Демо-счёт •• 5678</option></select><p id="form-error" class="error" hidden></p><div class="note">Расчёт и лимит — иллюстрация. Перевод не будет выполнен.</div><button class="primary" type="submit">Отправить тестовый перевод</button></form>`;
}

async function updateQuote() {
  const amount = Number(document.querySelector('#amount').value);
  const quote = document.querySelector('#quote');
  if (!Number.isFinite(amount) || amount <= 0) { quote.hidden = true; return; }
  const response = await fetch(`/api/quotes/${state.corridor}?amount_rub=${amount}`);
  if (!response.ok) { quote.hidden = true; return; }
  const item = await response.json();
  quote.hidden = false;
  const model = state.signal?.model_assessment;
  const modelHint = model?.client_label ? `<div class="model-card ${model.scenario}"><b>${escapeHtml(model.client_label)}</b>${model.forecast_date ? `<span>Окно: ${escapeHtml(model.forecast_date)}</span>` : ''}<small>${escapeHtml(model.disclaimer)}</small></div>` : model?.scenario === 'withhold' ? `<div class="split-help">Если перевод нельзя отложить, можно отправить часть суммы сейчас.</div>` : '';
  quote.innerHTML = `<span>Получит получатель</span><b>${item.recipient_amount.toLocaleString('ru-RU')} ${item.currency}</b><small>Ориентир: 1 ₽ = ${item.rate} ${item.currency} · комиссия ${item.fee_rub} ₽</small><small>${item.rate_label}</small>${modelHint}`;
}

async function submitTransfer(event) {
  event.preventDefault();
  const error = document.querySelector('#form-error');
  const response = await fetch('/api/transfers', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ corridor:state.corridor, method:state.method, recipient:document.querySelector('#recipient').value, amount_rub:Number(document.querySelector('#amount').value), debit_account:document.querySelector('#account').value }) });
  if (!response.ok) { const body = await response.json(); error.hidden = false; error.textContent = body.detail?.[0]?.msg || 'Проверьте тестовые данные.'; return; }
  go('result', { transfer: await response.json() });
}

async function openSignal() {
  const params = new URLSearchParams(location.search);
  const corridor = params.get('corridor') || 'TJS';
  const status = params.get('status') || 'current';
  const modelScenario = params.get('model_scenario') || 'withhold';
  const response = await fetch(`/api/signals/${encodeURIComponent(corridor)}?status=${encodeURIComponent(status)}&model_scenario=${encodeURIComponent(modelScenario)}`);
  if (!response.ok) { go('countries'); return; }
  go('signal', { corridor, method:null, signal:await response.json() });
}

function signal() {
  const item = state.signal;
  const copy = {
    current: { icon:'✓', title:'Сигнал всё ещё актуален', meaning:'Можно рассмотреть перевод, если срок позволяет.', action:'Открыть перевод' },
    changed: { icon:'↻', title:'Пуш устарел', meaning:'Не делаем вывод о текущих условиях по старому пушу.', action:'Перевести без подсказки' },
    unknown: { icon:'?', title:'Не удалось проверить статус', meaning:'Мы не знаем, сохранился ли контекст из пуша.', action:'Перевести без подсказки' },
  }[item.freshness_status];
  const model = item.model_assessment;
  const modelCard = model.client_label ? `<div class="model-card ${model.scenario}"><b>${escapeHtml(model.client_label)}</b>${model.forecast_date ? `<span>Окно: ${escapeHtml(model.forecast_date)}</span>` : ''}<small>${escapeHtml(model.disclaimer)}</small></div>` : '';
  return `${header('Уведомление')}<div class="hero signal ${item.freshness_status}"><span class="demo-label">UI-сценарий, не live-оценка</span><div class="status-heading"><span class="status-icon" aria-hidden="true">${copy.icon}</span><div><span class="status">${escapeHtml(item.freshness_status)}</span><h2>${copy.title}</h2></div></div><p>${escapeHtml(item.message)}</p><div class="meaning"><b>Что это значит</b><span>${copy.meaning}</span></div>${modelCard}<p class="tiny">${escapeHtml(item.source)} · срез: ${escapeHtml(item.source_snapshot_ref)} · дата T: ${escapeHtml(item.observation_date)}</p></div><div class="note">${escapeHtml(item.disclaimer)}</div><button class="primary" type="button" onclick="go('methods',{method:null})">${copy.action}</button><button class="secondary" type="button" onclick="go('countries')">Выбрать другую страну</button><button class="secondary" type="button" onclick="go('home')">Вернуться позже</button><p class="tiny">Срочно нужно перевести? Обычный путь доступен сразу и не оценивает ваше решение.</p>`;
}

async function settings() {
  const prefs = await fetch('/api/preferences').then(response => response.json());
  return `${header('Настройки пушей')}<div class="note">Это display-only настройка демо. Пуши не отправляются, канал и quiet hours не настроены.</div><div class="card switch"><span><b>Демо-сигналы</b><span class="sub">Только сценарии UI</span></span><input id="enabled" type="checkbox" ${prefs.enabled ? 'checked' : ''}/></div><label>Направления</label>${Object.entries(countries).map(([code,[name]]) => `<div class="card switch"><span>${name}</span><input class="corridor" data-code="${code}" type="checkbox" ${prefs.corridors.includes(code) ? 'checked' : ''}/></div>`).join('')}<label for="quiet">Тихие часы</label><input id="quiet" value="${escapeHtml(prefs.quiet_hours)}"/><button class="primary" type="button" onclick="saveSettings()">Сохранить в демо</button>`;
}

async function saveSettings() {
  const corridors = [...document.querySelectorAll('.corridor:checked')].map(item => item.dataset.code);
  await fetch('/api/preferences', { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({enabled:document.querySelector('#enabled').checked, corridors, quiet_hours:document.querySelector('#quiet').value}) });
  alert('Настройки сохранены только в памяти текущего запуска.');
}

function result() {
  const item = state.transfer;
  const quote = item.quote;
  return `<div class="success"><div class="emoji">✓</div><span class="demo-label">Синтетическое продолжение</span><h1>Тестовый перевод отправлен</h1><p>${escapeHtml(item.message)}</p><div class="card"><b>${escapeHtml(item.amount_rub)} ₽</b><span class="sub">в ${escapeHtml(item.country)} · ${escapeHtml(item.method)}</span><hr/><span class="sub">Получит получатель</span><b>${quote.recipient_amount.toLocaleString('ru-RU')} ${escapeHtml(quote.currency)}</b><span class="sub">Демо-ориентир: 1 ₽ = ${escapeHtml(quote.rate)} ${escapeHtml(quote.currency)}</span></div><p class="tiny">Это не банковское подтверждение, деньги не списывались. Расчёт не является курсом исполнения.</p><button class="primary" type="button" onclick="go('home')">К платежам</button></div>`;
}

setInterval(pollPushes, 1500);
pollPushes();
if (new URLSearchParams(location.search).has('corridor')) { openSignal(); } else { render(); }
