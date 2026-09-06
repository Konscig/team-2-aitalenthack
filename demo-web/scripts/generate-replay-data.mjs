import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const demoDir = dirname(dirname(fileURLToPath(import.meta.url)));
const repoDir = dirname(demoDir);
const TODAY = '2026-06-10';
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
  readCsv(join(repoDir, 'reports/three_type_timesfm_suppression_log.csv')),
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

// Only TimesFM's mean H1...H5 change and count of worse days are persisted.
// Reconstruct display points while preserving those two saved aggregates.
function interpolateTimesFm(meanBps, worseDays) {
  const countPositive = Math.max(0, Math.min(5, worseDays));
  if (countPositive === 0) return [-1.35, -1.15, -1, -.85, -.65].map((weight) => Math.abs(meanBps) * weight);
  if (countPositive === 5) return [.45, .7, .95, 1.25, 1.65].map((weight) => meanBps * weight);

  const countNegative = 5 - countPositive;
  const small = Math.max(Math.abs(meanBps) * .2, 1);
  let negative;
  let positive;
  if (meanBps >= 0) {
    negative = -small;
    positive = (meanBps * 5 + countNegative * small) / countPositive;
  } else {
    positive = small;
    negative = (meanBps * 5 - countPositive * small) / countNegative;
  }
  const spread = (value, count) => Array.from({ length: count }, (_, index) => (
    value * (1 + (index - (count - 1) / 2) * .16)
  ));
  return spread(negative, countNegative).concat(spread(positive, countPositive));
}

function signalMetrics(rate, futureRate) {
  const amount = 22000;
  const recipientAmount = amount / rate;
  const futureAmount = amount / futureRate;
  return {
    recipientAmount: Math.round(recipientAmount),
    effectUnits: Math.round(recipientAmount - futureAmount),
    ret5Pct: Number(((futureRate / rate - 1) * 100).toFixed(2)),
    facts: [],
  };
}

const corridors = {};
for (const code of corridorCodes) {
  const corridor = `${code}_RUB`;
  const rates = ratesByCorridor.get(corridor);
  const todayCandidate = candidateByKey.get(`${corridor}|${TODAY}`);
  const todayPolicy = policyByKey.get(`${corridor}|${TODAY}`);
  if (!rates || !todayCandidate || !todayPolicy) throw new Error(`TimesFM replay is incomplete for ${corridor}`);

  const allDates = [...rates.keys()].sort();
  const historyDates = allDates.filter((date) => date <= TODAY).slice(-42);
  const futureDates = allDates.filter((date) => date > TODAY).slice(0, 5);
  const todayRate = Number(todayCandidate.rate_t);
  const meanChangeH5Bps = Number(todayCandidate.mean_change_h5_bps);
  const worseDaysH5 = Number(todayCandidate.n_worse_days_h5);
  const changes = interpolateTimesFm(meanChangeH5Bps, worseDaysH5);
  const predicted = [[TODAY, todayRate], ...futureDates.map((date, index) => [date, todayRate * (1 + changes[index] / 10000)])];
  const golden = [[TODAY, todayRate], ...futureDates.map((date) => [date, rates.get(date)])];
  const predictedEnd = predicted.at(-1)[1];
  const goldenEnd = golden.at(-1)[1];

  const predictedSignals = futureDates.flatMap((date, index) => {
    const labels = labelsByKey.get(`${corridor}|${date}`) || [];
    if (!labels.includes('Кандидат')) return [];
    const type = candidateType(candidateByKey.get(`${corridor}|${date}`));
    if (!type) return [];
    return [{ date, rate: predicted[index + 1][1], type, series: 'predicted', ...signalMetrics(predicted[index + 1][1], predictedEnd) }];
  });

  const goldenSignals = futureDates.flatMap((date, index) => {
    const labels = labelsByKey.get(`${corridor}|${date}`) || [];
    return labels.filter((label) => signalType[label]).map((label) => ({
      date,
      rate: golden[index + 1][1],
      type: signalType[label],
      series: 'golden',
      ...signalMetrics(golden[index + 1][1], goldenEnd),
    }));
  });

  const todayType = signalType[todayPolicy.final_push_type] || candidateType(todayCandidate) || 'good_now';
  const todaySignal = {
    date: TODAY,
    rate: todayRate,
    type: todayType,
    series: 'today',
    ...signalMetrics(todayRate, goldenEnd),
    timesfm: { meanChangeH5Bps, worseDaysH5, reason: todayPolicy.final_push_reason },
  };
  const mae = predicted.slice(1).reduce((sum, point, index) => sum + Math.abs(point[1] - golden[index + 1][1]), 0) / 5;

  corridors[code] = {
    source: 'TimesFM · final_push_labels_long.csv',
    today: TODAY,
    history: historyDates.map((date) => [date, rates.get(date)]),
    predicted,
    golden,
    predictedSignals,
    goldenSignals,
    todaySignal,
    comparison: {
      mae,
      meanChangeH5Bps,
      worseDaysH5,
      predictedEnd,
      goldenEnd,
      predictedCount: predictedSignals.length + 1,
      goldenCount: goldenSignals.length,
    },
  };
}

await writeFile(join(demoDir, 'replay-data.js'), `window.REPLAY_DATA = ${JSON.stringify({ today: TODAY, model: 'TimesFM', corridors })};\n`);
