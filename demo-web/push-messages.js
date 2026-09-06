window.PUSH_MESSAGES = {
  good_now: {
    label: 'Выгодный момент',
    title: 'Курс в фокусе',
    body: ({ currency }) => `Курс ${currency} близок к локальному минимуму.`,
    reason: 'Курс не дальше 1% от минимума в окне ±10 календарных дней.',
  },
  window_closing: {
    label: 'Окно закрывается',
    title: 'Условия меняются',
    body: ({ country }) => `Курс для перевода в ${country} начал расти.`,
    reason: 'Курс на 1–2% выше минимума прошлых 10 дней, а медиана следующих 10 дней хуже минимум на 1%.',
  },
  positive_market_fact: {
    label: 'Позитивный факт',
    title: ({ facts }) => factPushVariant(facts).title,
    body: ({ country, facts }) => factPushVariant(facts).body({ country }),
    reason: 'Только наблюдаемый факт на дату сигнала — без использования будущего.',
  },
};

window.FACT_PUSH_MESSAGES = {
  decline_3: {
    title: 'Курс снижается',
    body: ({ country }) => `Курс для перевода в ${country} снижался три обновления подряд.`,
  },
  weekly_gain: {
    title: 'Курс улучшился за неделю',
    body: ({ country }) => `За неделю курс для перевода в ${country} улучшился минимум на 1%.`,
  },
  low_percentile: {
    title: 'Редкий уровень курса',
    body: ({ country }) => `Курс для перевода в ${country} выгоднее 90% значений за 30 дней.`,
  },
  'decline_3+weekly_gain': {
    title: 'Курс продолжает снижаться',
    body: ({ country }) => `Курс для перевода в ${country}: три снижения подряд и улучшение минимум на 1% за неделю.`,
  },
  'decline_3+low_percentile': {
    title: 'Курс в нижнем диапазоне',
    body: ({ country }) => `Курс для перевода в ${country} снижался три обновления подряд и достиг редкого уровня за 30 дней.`,
  },
  'weekly_gain+low_percentile': {
    title: 'Неделя заметного улучшения',
    body: ({ country }) => `Курс для перевода в ${country} улучшился за неделю и выгоднее 90% значений за 30 дней.`,
  },
  'decline_3+weekly_gain+low_percentile': {
    title: 'Сразу три сигнала по курсу',
    body: ({ country }) => `Курс для перевода в ${country}: снижение подряд, улучшение за неделю и редкий уровень за 30 дней.`,
  },
};

function factPushVariant(facts = []) {
  const order = ['decline_3', 'weekly_gain', 'low_percentile'];
  const key = order.filter((fact) => facts.includes(fact)).join('+');
  return FACT_PUSH_MESSAGES[key] || {
    title: 'Курс изменился',
    body: ({ country }) => `Курс для перевода в ${country} заметно изменился.`,
  };
}

window.getPushCopy = function getPushCopy(type, context) {
  const copy = PUSH_MESSAGES[type];
  return {
    title: typeof copy.title === 'function' ? copy.title(context) : copy.title,
    body: copy.body(context),
  };
};

window.FACT_MESSAGES = {
  decline_3: 'Курс снижался три обновления подряд.',
  weekly_gain: 'За неделю курс улучшился минимум на 1%.',
  low_percentile: 'Курс выгоднее не менее 90% значений за прошлые 30 дней.',
};
