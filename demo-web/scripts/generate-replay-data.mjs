import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const demoDir = dirname(dirname(fileURLToPath(import.meta.url)));
const repoDir = dirname(demoDir);
const corridorCodes = ['AMD', 'KGS', 'KZT', 'TJS', 'UZS'];

async function readCsv(path) {
  const text = (await readFile(path, 'utf8')).replace(/^\uFEFF/, '').trim();
  const [headerLine, ...lines] = text.split(/\r?\n/);
  const headers = headerLine.split(',');
  return lines.map((line) => {
    const values = line.split(',');
    return Object.fromEntries(headers.map((header, index) => [header, values[index]]));
  });
}

const [labelRows, candidateRows, policyRows] = await Promise.all([
  readCsv(join(repoDir, 'reports/final_push_labels_long.csv')),
  readCsv(join(repoDir, 'reports/three_type_timesfm_candidates.csv')),
  readCsv(join(demoDir, 'data/timesfm_policy.csv')),
]);

const bool = (value) => value === 'True' || value === 'true' || value === '1';
const candidateByKey = new Map(candidateRows.map((row) => [`${row.corridor}|${row.date}`, row]));
const policyByKey = new Map(policyRows.map((row) => [`${row.corridor}|${row.date}`, row]));
const labelsByKey = new Map();
const ratesByCorridor = new Map();

for (const row of labelRows) {
  const key = `${row.corridor}|${row.date}`;
  const labels = labelsByKey.get(key) || [];
  if (row.label === '1') labels.push(row.type);
  labelsByKey.set(key, labels);
  if (!ratesByCorridor.has(row.corridor)) ratesByCorridor.set(row.corridor, new Map());
  ratesByCorridor.get(row.corridor).set(row.date, Number(row.rate));
}

const signalType = {
  good_day: 'good_now',
  window_closing: 'window_closing',
  positive_market_fact: 'positive_market_fact',
  'Good day': 'good_now',
  Closing: 'window_closing',
  Fact: 'positive_market_fact',
};

function candidateType(row) {
  if (!row) return null;
  if (bool(row.good_day_candidate)) return 'good_now';
  if (bool(row.window_closing_candidate)) return 'window_closing';
  if (bool(row.positive_market_fact_candidate)) return 'positive_market_fact';
  return null;
}

function interpolateTimesFm(meanBps, worseDays) {
  const countPositive = Math.max(0, Math.min(5, worseDays));
  if (countPositive === 0) return [-1.35, -1.15, -1, -.85, -.65].map((weight) => Math.abs(meanBps) * weight);
  if (countPositive === 5) return [.45, .7, .95, 1.25, 1.65].map((weight) => meanBps * weight);
  const countNegative = 5 - countPositive;
  const small = Math.max(Math.abs(meanBps) * .2, 1);
  const negative = meanBps >= 0 ? -small : (meanBps * 5 - countPositive * small) / countNegative;
  const positive = meanBps >= 0 ? (meanBps * 5 + countNegative * small) / countPositive : small;
  const spread = (value, count) => Array.from({ length: count }, (_, index) => value * (1 + (index - (count - 1) / 2) * .16));
  return spread(negative, countNegative).concat(spread(positive, countPositive));
}

function metrics(rate, futureRate) {
  const recipientAmount = 22000 / rate;
  return {
    recipientAmount: Math.round(recipientAmount),
    effectUnits: Math.round(recipientAmount - 22000 / futureRate),
    ret5Pct: Number(((futureRate / rate - 1) * 100).toFixed(2)),
    facts: [],
  };
}

function pushExplanation(policy, type) {
  if (bool(policy.final_push)) {
    if (type === 'good_now') return 'Сработал good day, и коммуникационные ограничения пропустили сигнал.';
    if (type === 'window_closing') return 'TimesFM увидел закрывающееся окно, и cooldown не заблокировал сообщение.';
    return 'Сработал наблюдаемый market fact, и сигнал прошёл коммуникационную политику.';
  }
  if (policy.final_push_reason === 'COOLDOWN') return 'Кандидат был, но push подавлен: ещё действует cooldown после предыдущего сообщения.';
  return 'На выбранную дату ни одно правило-кандидат не сработало.';
}

const corridors = {};
for (const code of corridorCodes) {
  const corridor = `${code}_RUB`;
  const rates = ratesByCorridor.get(corridor);
  const allDates = [...rates.keys()].sort();
  const lastDate = new Date(`${allDates.at(-1)}T00:00:00Z`);
  const yearStart = new Date(lastDate); yearStart.setUTCFullYear(yearStart.getUTCFullYear() - 1);
  const yearDates = allDates.filter((date) => Date.parse(date) >= yearStart.getTime());
  const replays = {};

  for (const date of yearDates) {
    const index = allDates.indexOf(date);
    const futureDates = allDates.slice(index + 1, index + 6);
    const candidate = candidateByKey.get(`${corridor}|${date}`);
    const policy = policyByKey.get(`${corridor}|${date}`);
    if (!candidate || !policy || futureDates.length < 5) continue;

    const rate = Number(candidate.rate_t);
    const meanChangeH5Bps = Number(candidate.mean_change_h5_bps);
    const worseDaysH5 = Number(candidate.n_worse_days_h5);
    const changes = interpolateTimesFm(meanChangeH5Bps, worseDaysH5);
    const predicted = [[date, rate], ...futureDates.map((futureDate, horizon) => [futureDate, rate * (1 + changes[horizon] / 10000)])];
    const golden = [[date, rate], ...futureDates.map((futureDate) => [futureDate, rates.get(futureDate)])];
    const predictedEnd = predicted.at(-1)[1];
    const goldenEnd = golden.at(-1)[1];

    const predictedSignals = [date, ...futureDates].flatMap((signalDate, horizon) => {
      const labels = labelsByKey.get(`${corridor}|${signalDate}`) || [];
      if (!labels.includes('Кандидат')) return [];
      const type = candidateType(candidateByKey.get(`${corridor}|${signalDate}`));
      if (!type) return [];
      const signalRate = predicted[horizon][1];
      return [{ date: signalDate, rate: signalRate, type, series: 'predicted', ...metrics(signalRate, predictedEnd) }];
    });

    const goldenSignals = [date, ...futureDates].flatMap((signalDate, horizon) => {
      const labels = labelsByKey.get(`${corridor}|${signalDate}`) || [];
      return labels.filter((label) => signalType[label]).map((label) => {
        const signalRate = golden[horizon][1];
        return { date: signalDate, rate: signalRate, type: signalType[label], series: 'golden', ...metrics(signalRate, goldenEnd) };
      });
    });

    const sent = bool(policy.final_push);
    const pushType = signalType[policy.final_push_type] || candidateType(candidate);
    const todaySignal = sent ? {
      date, rate, type: pushType, series: 'today', ...metrics(rate, goldenEnd),
      timesfm: { meanChangeH5Bps, worseDaysH5, reason: policy.final_push_reason },
    } : null;
    const mae = predicted.slice(1).reduce((sum, point, horizon) => sum + Math.abs(point[1] - golden[horizon + 1][1]), 0) / 5;

    replays[date] = {
      date, predicted, golden, predictedSignals, goldenSignals, todaySignal,
      push: {
        sent,
        type: pushType,
        reasonCode: policy.final_push_reason,
        explanation: pushExplanation(policy, pushType),
      },
      comparison: {
        mae, meanChangeH5Bps, worseDaysH5, predictedEnd, goldenEnd,
        predictedCount: predictedSignals.length,
        goldenCount: goldenSignals.length,
      },
    };
  }

  corridors[code] = {
    source: 'TimesFM · final_push_labels_long.csv',
    year: yearDates.map((date) => [date, rates.get(date)]),
    replays,
  };
}

await writeFile(join(demoDir, 'replay-data.js'), `window.REPLAY_DATA = ${JSON.stringify({ model: 'TimesFM', corridors })};\n`);
