import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "https://cbu.uz";
const listUrl = `${root}/ru/statistics/buleten/`;
const outputPath = "/Users/cuperuser/kostyA/Talent Hub/team-2-aitalenthack/outputs/fx_volumes_central_asia_caucasus_2015_2026.xlsx";
const tmpDir = "/tmp/cbu_fx_bulletins";
await fs.mkdir(tmpDir, { recursive: true });
const issues = [[2018, "04"], [2019, "11"], [2020, "12"], [2021, "12"], [2022, "11"], [2023, "12"], [2024, "11"], [2025, "12"], [2026, "06"]];
const months = new Map([["Январь", 1], ["Февраль", 2], ["Март", 3], ["Апрель", 4], ["Май", 5], ["Июнь", 6], ["Июль", 7], ["Август", 8], ["Сентябрь", 9], ["Октябрь", 10], ["Ноябрь", 11], ["Декабрь", 12]]);
const number = (s) => Number(s.replace(/\s/g, "").replace(",", "."));

async function fetchText(url) {
  let lastError;
  for (let attempt = 1; attempt <= 4; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.text();
      lastError = new Error(`${response.status} ${url}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 750 * attempt));
  }
  throw lastError;
}

async function getPdfUrl(year, month) {
  const page = await fetchText(`${listUrl}?arFilter_ff%5BSECTION_ID%5D=3664&year=${year}&month=${month}&set_filter=Y`);
  const detail = page.match(/href="(\/ru\/statistics\/buleten\/\d+\/)"/i)?.[1];
  if (!detail) throw new Error(`No bulletin for ${year}-${month}`);
  const detailPage = await fetchText(`${root}${detail}`);
  const pdf = detailPage.match(/(?:href=")?(\/upload\/[^"'\s]+\.pdf)/i)?.[1];
  if (!pdf) throw new Error(`No PDF in ${detail}`);
  return `${root}${pdf}`;
}

function parseRows(text, sourceUrl) {
  const starts = [];
  for (let index = text.indexOf("Объем торгов иностранных валют"); index >= 0; index = text.indexOf("Объем торгов иностранных валют", index + 1)) starts.push(index);
  const start = starts.find((index) => /(?:^|\n)\s*20\d{2} год\s+х/m.test(text.slice(index, index + 10000)));
  if (start === undefined) return [];
  const end = text.indexOf("Таблица 4.2.2", start);
  const section = text.slice(start, end > start ? end : start + 10000).replace(/\f/g, "\n");
  let currentYear = null;
  const rows = [];
  for (const raw of section.split(/\r?\n/)) {
    const line = raw.trim();
    const year = line.match(/^(\d{4}) год/);
    if (year) { currentYear = Number(year[1]); continue; }
    const month = [...months.entries()].find(([name]) => line.startsWith(name));
    if (!month || !currentYear) continue;
    const values = [...line.matchAll(/\d[\d ]*(?:,\d+)?/g)].map((match) => number(match[0]));
    if (values.length < 3) continue;
    const [rate, banksBuy, banksSell] = values.length >= 5 ? values.slice(-5, -2) : values.slice(-3);
    const date = new Date(Date.UTC(currentYear, month[1] - 1, 1));
    rows.push([date, "CBU / UZRVB", "USDUZS", "USD", "commercial_banks", "buy", banksBuy * 1_000_000, rate, sourceUrl]);
    rows.push([date, "CBU / UZRVB", "USDUZS", "USD", "commercial_banks", "sell", banksSell * 1_000_000, rate, sourceUrl]);
    if (values.length >= 5) {
      const [, , , cbBuy, cbSell] = values.slice(-5);
      rows.push([date, "CBU / UZRVB", "USDUZS", "USD", "central_bank", "buy", cbBuy * 1_000_000, rate, sourceUrl]);
      rows.push([date, "CBU / UZRVB", "USDUZS", "USD", "central_bank", "sell", cbSell * 1_000_000, rate, sourceUrl]);
    }
  }
  return rows;
}

const byMonth = new Map();
for (const [year, month] of issues) {
  const pdfUrl = await getPdfUrl(year, month);
  const prefix = `${tmpDir}/${year}-${month}`;
  try { await fs.access(`${prefix}.txt`); } catch {
    execFileSync("curl", ["-L", "-sS", "--max-time", "120", "-o", `${prefix}.pdf`, pdfUrl], { stdio: "inherit" });
    execFileSync("pdftotext", ["-layout", `${prefix}.pdf`, `${prefix}.txt`]);
  }
  const extracted = parseRows(await fs.readFile(`${prefix}.txt`, "utf8"), pdfUrl);
  for (const row of extracted) {
    const key = `${row[0].toISOString().slice(0, 7)}-${row[4]}-${row[5]}`;
    byMonth.set(key, row);
  }
}
const rows = [...byMonth.values()].filter((row) => row[0].getUTCFullYear() >= 2017).sort((a, b) => a[0] - b[0] || a[4].localeCompare(b[4]) || a[5].localeCompare(b[5]));
console.log(JSON.stringify({ uzsExtractedRows: rows.length, months: [...new Set(rows.map((row) => row[0].toISOString().slice(0, 7)))] }));
if (rows.length < 200) throw new Error(`Unexpected UZS row count: ${rows.length}`);
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
book.worksheets.getItem("CBU_UZS_monthly").delete();
const sheet = book.worksheets.add("CBU_UZS_monthly");
const header = [["month", "venue", "pair", "volume_currency", "participant", "side", "volume_usd", "avg_uzs_per_usd", "source_url"]];
sheet.getRangeByIndexes(0, 0, rows.length + 1, header[0].length).values = [...header, ...rows];
const range = sheet.getRangeByIndexes(0, 0, rows.length + 1, header[0].length);
range.format.font = { name: "Arial", size: 10 };
range.format.borders = { preset: "outside", style: "thin", color: "#D9D9D9" };
sheet.getRange("A1:I1").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
sheet.getRange("A1:I1").format.rowHeight = 22;
sheet.tables.add(`A1:I${rows.length + 1}`, true, "CbuUzsVolumes");
sheet.freezePanes.freezeRows(1);
sheet.getRange(`A2:A${rows.length + 1}`).format.numberFormat = "yyyy-mm";
sheet.getRange(`G2:H${rows.length + 1}`).format.numberFormat = "#,##0.####";
sheet.getRange("A:A").format.columnWidth = 12;
sheet.getRange("B:B").format.columnWidth = 18;
sheet.getRange("C:F").format.columnWidth = 18;
sheet.getRange("G:H").format.columnWidth = 20;
sheet.getRange("I:I").format.columnWidth = 65;
sheet.showGridLines = false;
const check = await book.inspect({ kind: "table", range: "CBU_UZS_monthly!A1:I10", include: "values", tableMaxRows: 10, tableMaxCols: 9 });
console.log(check.ndjson);
const file = await SpreadsheetFile.exportXlsx(book);
await file.save(outputPath);
console.log(JSON.stringify({ uzsRows: rows.length, outputPath }));
