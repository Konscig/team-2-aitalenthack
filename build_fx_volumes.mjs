import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const outDir = "/Users/cuperuser/kostyA/Talent Hub/team-2-aitalenthack/outputs";
const endDate = "2026-09-04";
const startDate = "2015-01-01";

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const toDate = (iso) => new Date(`${iso}T00:00:00Z`);
const isoDate = (date) => date.toISOString().slice(0, 10);

async function fetchJson(url, attempts = 3) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
      if (attempt === attempts) throw new Error(`${response.status} ${url}`);
    } catch (error) {
      if (attempt === attempts) throw error;
    }
    await delay(1000 * attempt);
  }
}

async function mapWithConcurrency(items, concurrency, worker) {
  const output = new Array(items.length);
  let next = 0;
  await Promise.all(Array.from({ length: concurrency }, async () => {
    while (true) {
      const index = next;
      next += 1;
      if (index >= items.length) return;
      output[index] = await worker(items[index]);
    }
  }));
  return output;
}

async function getKaseRows() {
  const dates = [];
  for (let cursor = toDate(startDate); isoDate(cursor) <= endDate; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    dates.push(isoDate(cursor));
  }
  const datasets = await mapWithConcurrency(dates, 8, async (date) => {
    const url = `https://kase.kz/api/trade-results/currency-spot?date_trade=${date}`;
    const records = await fetchJson(url);
    return records
      .filter((row) => /^(USD|EUR|CNY)KZT_/.test(row.code))
      .map((row) => [
        toDate(row.date_trade.slice(0, 10)),
        "KASE",
        row.code,
        row.code.split("_")[1] ?? "",
        row.num_sess,
        row.volume ?? null,
        row.deals ?? null,
        row.average ?? null,
        row.low ?? null,
        row.high ?? null,
        `https://kase.kz/api/trade-results/currency-spot?date_trade=${row.date_trade.slice(0, 10)}`,
      ]);
  });
  return datasets.flat().sort((a, b) => a[0] - b[0] || a[2].localeCompare(b[2]) || (a[4] ?? 0) - (b[4] ?? 0));
}

function cleanHtml(value) {
  return value
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function parseNumber(value) {
  const normalized = value.replace(/\s/g, "").replace(/,/g, ".");
  return normalized === "" || normalized === "-" ? null : Number(normalized);
}

function parseNbkrRows(html, sourceUrl) {
  const rows = [];
  for (const row of html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)) {
    const cells = [...row[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map((cell) => cleanHtml(cell[1]));
    if (!/^\d{2}\.\d{2}\.\d{4}$/.test(cells[0] ?? "")) continue;
    const [day, month, year] = cells[0].split(".");
    rows.push([
      toDate(`${year}-${month}-${day}`),
      "NBKR interbank FX market",
      "USDKGS",
      parseNumber(cells[1] ?? ""),
      parseNumber(cells[2] ?? ""),
      null,
      parseNumber(cells[3] ?? ""),
      parseNumber(cells[4] ?? ""),
      sourceUrl,
    ]);
  }
  return rows;
}

async function getNbkrRows() {
  const years = Array.from({ length: 2026 - 2015 + 1 }, (_, index) => 2015 + index);
  const datasets = await mapWithConcurrency(years, 3, async (year) => {
    const end = year === 2026 ? "04&end_month=09&end_year=2026" : `31&end_month=12&end_year=${year}`;
    const url = `https://www.nbkr.kg/index1.jsp?begin_day=01&begin_month=01&begin_year=${year}&end_day=${end}&item=118&lang=ENG`;
    const html = await fetchText(url, 6);
    return parseNbkrRows(html, url);
  });
  return datasets.flat().sort((a, b) => a[0] - b[0]);
}

async function fetchText(url, attempts = 3) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.text();
      if (attempt === attempts) throw new Error(`${response.status} ${url}`);
    } catch (error) {
      if (attempt === attempts) throw error;
    }
    await delay(1500 * attempt);
  }
}

function formatTable(sheet, range) {
  range.format.font = { name: "Arial", size: 10 };
  range.format.borders = { preset: "outside", style: "thin", color: "#D9D9D9" };
  const header = range.getRow(0);
  header.format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center" };
  header.format.rowHeight = 22;
}

async function buildWorkbook(kaseRows, nbkrRows) {
  const workbook = Workbook.create();
  const readme = workbook.worksheets.add("README");
  const kase = workbook.worksheets.add("KASE_KZT");
  const nbkr = workbook.worksheets.add("NBKR_KGS");

  readme.getRange("A1:B9").values = [
    ["FX volume dataset", ""],
    ["Coverage", "Daily records from 2015-01-01 to 2026-09-04"],
    ["KASE", "KZT FX market: USD/KZT, EUR/KZT, CNY/KZT; volume is the base-currency amount reported by KASE."],
    ["NBKR", "KGS interbank FX market: USD/KGS; volumes are USD and are split by settlement date."],
    ["Important", "Do not add volumes across venues or currencies without normalization. Keep the venue and pair fields."],
    ["KASE source", "https://kase.kz/api/trade-results/currency-spot?date_trade=YYYY-MM-DD"],
    ["NBKR source", "https://www.nbkr.kg/index1.jsp?item=118&lang=ENG"],
    ["Collected KASE rows", kaseRows.length],
    ["Collected NBKR rows", nbkrRows.length],
  ];
  readme.getRange("A1:B1").format = { fill: "#1F4E78", font: { name: "Arial", size: 14, bold: true, color: "#FFFFFF" } };
  readme.getRange("A1:B9").format.font = { name: "Arial", size: 10 };
  readme.getRange("A1:A9").format.font = { name: "Arial", size: 10, bold: true };
  readme.getRange("A1:B9").format.wrapText = true;
  readme.getRange("A:A").format.columnWidth = 26;
  readme.getRange("B:B").format.columnWidth = 95;
  readme.showGridLines = false;

  const kaseHeader = [["date", "venue", "pair", "settlement", "session", "volume_base_currency", "deal_count", "weighted_avg_price", "low", "high", "source_url"]];
  kase.getRangeByIndexes(0, 0, 1 + kaseRows.length, kaseHeader[0].length).values = [...kaseHeader, ...kaseRows];
  const kaseRange = kase.getRangeByIndexes(0, 0, 1 + kaseRows.length, kaseHeader[0].length);
  formatTable(kase, kaseRange);
  kase.tables.add(`A1:K${kaseRows.length + 1}`, true, "KaseKztVolumes");
  kase.freezePanes.freezeRows(1);
  kase.getRange(`A2:A${kaseRows.length + 1}`).format.numberFormat = "yyyy-mm-dd";
  kase.getRange(`F2:J${kaseRows.length + 1}`).format.numberFormat = "#,##0.####";
  kase.getRange("A:A").format.columnWidth = 14;
  kase.getRange("B:B").format.columnWidth = 12;
  kase.getRange("C:D").format.columnWidth = 16;
  kase.getRange("E:J").format.columnWidth = 16;
  kase.getRange("K:K").format.columnWidth = 68;
  kase.showGridLines = false;

  const nbkrHeader = [["date", "venue", "pair", "volume_same_day_usd", "volume_other_settlement_usd", "volume_total_usd", "open_kgs_per_usd", "close_kgs_per_usd", "source_url"]];
  const nbkrData = nbkrRows.map((row) => [...row.slice(0, 5), (row[3] ?? 0) + (row[4] ?? 0), ...row.slice(6)]);
  nbkr.getRangeByIndexes(0, 0, 1 + nbkrData.length, nbkrHeader[0].length).values = [...nbkrHeader, ...nbkrData];
  const nbkrRange = nbkr.getRangeByIndexes(0, 0, 1 + nbkrData.length, nbkrHeader[0].length);
  formatTable(nbkr, nbkrRange);
  nbkr.tables.add(`A1:I${nbkrData.length + 1}`, true, "NbkrKgsVolumes");
  nbkr.freezePanes.freezeRows(1);
  nbkr.getRange(`A2:A${nbkrData.length + 1}`).format.numberFormat = "yyyy-mm-dd";
  nbkr.getRange(`D2:H${nbkrData.length + 1}`).format.numberFormat = "#,##0.####";
  nbkr.getRange("A:A").format.columnWidth = 14;
  nbkr.getRange("B:B").format.columnWidth = 28;
  nbkr.getRange("C:C").format.columnWidth = 12;
  nbkr.getRange("D:H").format.columnWidth = 24;
  nbkr.getRange("I:I").format.columnWidth = 68;
  nbkr.showGridLines = false;

  return workbook;
}

const [kaseRows, nbkrRows] = await Promise.all([getKaseRows(), getNbkrRows()]);
if (kaseRows.length < 1000 || nbkrRows.length < 1000) throw new Error(`Unexpected record count: KASE=${kaseRows.length}; NBKR=${nbkrRows.length}`);
const workbook = await buildWorkbook(kaseRows, nbkrRows);
await fs.mkdir(outDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outDir}/fx_volumes_kase_nbkr_2015_2026.xlsx`);

const check = await workbook.inspect({ kind: "table", range: "KASE_KZT!A1:K8", include: "values", tableMaxRows: 8, tableMaxCols: 11 });
console.log(check.ndjson);
console.log(JSON.stringify({ kaseRows: kaseRows.length, nbkrRows: nbkrRows.length }));
