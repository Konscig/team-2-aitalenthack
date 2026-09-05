import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "https://nbt.tj";
const outPath = "/Users/cuperuser/kostyA/Talent Hub/team-2-aitalenthack/outputs/fx_volumes_central_asia_caucasus_2015_2026.xlsx";
const tmpDir = "/tmp/nbt_bulletins";
await fs.mkdir(tmpDir, { recursive: true });
const reports = {
  2015: "/upload/iblock/d1e/Bulettin_12_(145).pdf",
  2016: "/upload/iblock/9d1/Bulletin_12.pdf",
  2017: "/upload/iblock/94f/december_2017.pdf",
  2018: "/upload/iblock/e57/december_2018-2.pdf",
  2019: "/upload/iblock/bde/2019_12.pdf",
  2020: "/upload/iblock/088/mx8xke6zdse9vqnxa6wft759zy46gezs/2020.pdf",
  2021: "/upload/iblock/009/1ctan2uf9vp7mswb34spxpmsgjvg4yho/BULL_12_2021.pdf",
  2022: "/upload/iblock/ef7/14gh7n3nf8a44vpcogu3td8337230xvg/BULL_12_2022.pdf",
  2023: "/upload/iblock/5bb/sgedn3244ly8ejxki4045zbebb0cn9hr/BULL12 new.pdf",
  2024: "/upload/iblock/65f/xp88v7dpikpplfvgen939i6alttestgf/BULL_12_04.pdf",
  2025: "/upload/iblock/bb6/v5xmiyf9lwgcs8pbi5k91lpi9zq5ypfb/BULL_12_03.pdf",
};
const roman = new Map([["I", 1], ["II", 2], ["III", 3], ["IV", 4], ["V", 5], ["VI", 6], ["VII", 7], ["VIII", 8], ["IX", 9], ["X", 10], ["XI", 11], ["XII", 12]]);
const numeric = (value) => Number(value.replace(/\s/g, "").replace(",", "."));

function extract(text, sourceUrl) {
  const phrase = "Покупка и продажа на межбанковском валютном рынке";
  const starts = [];
  for (let index = text.indexOf(phrase); index >= 0; index = text.indexOf(phrase, index + 1)) starts.push(index);
  const start = starts.find((index) => /(?:^|\n)\s*20\d{2}\s*\n[\s\S]{0,3000}(?:^|\n)\s*(?:I|II|III|IV)\s+\d/m.test(text.slice(index, index + 14000)));
  if (start === undefined) return [];
  const section = text.slice(start, start + 12000).replace(/\f/g, "\n");
  let year = null;
  const rows = [];
  for (const raw of section.split(/\r?\n/)) {
    const line = raw.trim();
    if (/^20\d{2}$/.test(line)) { year = Number(line); continue; }
    const fields = line.split(/\s{2,}/).filter(Boolean);
    if (!year || fields.length < 5 || !roman.has(fields[0])) continue;
    const [monthName, transactionCount, rate, volumeTjs, volumeUsd] = fields;
    const month = roman.get(monthName);
    if (!month) continue;
    rows.push([
      new Date(Date.UTC(year, month - 1, 1)),
      "NBT interbank FX market",
      "USDTJS",
      numeric(transactionCount),
      numeric(rate),
      numeric(volumeTjs),
      numeric(volumeUsd),
      sourceUrl,
    ]);
  }
  return rows;
}

const keyed = new Map();
for (const [reportYear, filePath] of Object.entries(reports)) {
  const prefix = `${tmpDir}/${reportYear}`;
  try { await fs.access(`${prefix}.txt`); } catch {
    execFileSync("curl", ["-L", "-sS", "--max-time", "180", "-o", `${prefix}.pdf`, encodeURI(`${root}${filePath}`)], { stdio: "inherit" });
    execFileSync("pdftotext", ["-layout", `${prefix}.pdf`, `${prefix}.txt`]);
  }
  const parsed = extract(await fs.readFile(`${prefix}.txt`, "utf8"), `${root}${filePath}`);
  console.log(JSON.stringify({ reportYear, parsed: parsed.length }));
  for (const row of parsed) keyed.set(row[0].toISOString().slice(0, 7), row);
}
const rows = [...keyed.values()].filter((row) => row[0].getUTCFullYear() >= 2015).sort((a, b) => a[0] - b[0]);
console.log(JSON.stringify({ tjsRows: rows.length, coverage: rows.map((row) => row[0].toISOString().slice(0, 7)) }));
if (rows.length < 100) throw new Error(`Unexpected TJS row count: ${rows.length}`);
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(outPath));
book.worksheets.getItem("NBT_TJS_monthly").delete();
const sheet = book.worksheets.add("NBT_TJS_monthly");
const header = [["month", "venue", "pair", "transaction_count", "weighted_avg_tjs_per_usd", "volume_tjs_mn", "volume_usd_mn", "source_url"]];
sheet.getRangeByIndexes(0, 0, rows.length + 1, header[0].length).values = [...header, ...rows];
const range = sheet.getRangeByIndexes(0, 0, rows.length + 1, header[0].length);
range.format.font = { name: "Arial", size: 10 };
range.format.borders = { preset: "outside", style: "thin", color: "#D9D9D9" };
sheet.getRange("A1:H1").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
sheet.getRange("A1:H1").format.rowHeight = 22;
sheet.tables.add(`A1:H${rows.length + 1}`, true, "NbtTjsVolumes");
sheet.freezePanes.freezeRows(1);
sheet.getRange(`A2:A${rows.length + 1}`).format.numberFormat = "yyyy-mm";
sheet.getRange(`D2:G${rows.length + 1}`).format.numberFormat = "#,##0.####";
sheet.getRange("A:A").format.columnWidth = 12;
sheet.getRange("B:B").format.columnWidth = 28;
sheet.getRange("C:C").format.columnWidth = 12;
sheet.getRange("D:G").format.columnWidth = 24;
sheet.getRange("H:H").format.columnWidth = 68;
sheet.showGridLines = false;
const check = await book.inspect({ kind: "table", range: "NBT_TJS_monthly!A1:H14", include: "values", tableMaxRows: 14, tableMaxCols: 8 });
console.log(check.ndjson);
const file = await SpreadsheetFile.exportXlsx(book);
await file.save(outPath);
