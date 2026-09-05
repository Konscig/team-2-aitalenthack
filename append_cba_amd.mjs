import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const outputPath = "/Users/cuperuser/kostyA/Talent Hub/team-2-aitalenthack/outputs/fx_volumes_central_asia_caucasus_2015_2026.xlsx";
const basePath = "/Users/cuperuser/kostyA/Talent Hub/team-2-aitalenthack/outputs/fx_volumes_kase_nbkr_2015_2026.xlsx";
const sourcePath = "/tmp/armenia_fx_daily.xlsx";
const sourceUrl = "https://old.cba.am/stat/stat_data_eng/FOREX%20ENG_Daily.xlsx";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(basePath));
const source = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));
const input = source.worksheets.getItem("6.6-Forex (Banks)").getRange("A1:AK1186").values;
const rows = [];
const metrics = [
  ["USDAMD", "USD", "intrabank", "buy", 1],
  ["USDAMD", "USD", "intrabank", "sell", 4],
  ["USDAMD", "USD", "interbank", "buy", 7],
  ["USDAMD", "USD", "interbank", "sell", 10],
  ["EURAMD", "EUR", "intrabank", "buy", 13],
  ["EURAMD", "EUR", "intrabank", "sell", 16],
  ["EURAMD", "EUR", "interbank", "buy", 19],
  ["EURAMD", "EUR", "interbank", "sell", 22],
];
for (const line of input.slice(6)) {
  if (!(line[0] instanceof Date) && typeof line[0] !== "number") continue;
  const date = line[0] instanceof Date ? line[0] : new Date(Date.UTC(1899, 11, 30) + line[0] * 86400000);
  for (const [pair, currency, segment, side, index] of metrics) {
    const volume = line[index];
    if (volume === null || volume === undefined || volume === "") continue;
    rows.push([date, "CBA Armenia commercial banks", pair, currency, segment, side, volume, sourceUrl]);
  }
}
if (rows.length < 5000) throw new Error(`Unexpected CBA row count: ${rows.length}`);
const sheet = workbook.worksheets.add("CBA_AMD");
const header = [["date", "venue", "pair", "volume_currency", "segment", "side", "volume", "source_url"]];
sheet.getRangeByIndexes(0, 0, rows.length + 1, header[0].length).values = [...header, ...rows];
const range = sheet.getRangeByIndexes(0, 0, rows.length + 1, header[0].length);
range.format.font = { name: "Arial", size: 10 };
range.format.borders = { preset: "outside", style: "thin", color: "#D9D9D9" };
sheet.getRange("A1:H1").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
sheet.getRange("A1:H1").format.rowHeight = 22;
sheet.tables.add(`A1:H${rows.length + 1}`, true, "CbaAmdVolumes");
sheet.freezePanes.freezeRows(1);
sheet.getRange(`A2:A${rows.length + 1}`).format.numberFormat = "yyyy-mm-dd";
sheet.getRange(`G2:G${rows.length + 1}`).format.numberFormat = "#,##0.####";
sheet.getRange("A:A").format.columnWidth = 14;
sheet.getRange("B:B").format.columnWidth = 30;
sheet.getRange("C:F").format.columnWidth = 16;
sheet.getRange("G:G").format.columnWidth = 18;
sheet.getRange("H:H").format.columnWidth = 62;
sheet.showGridLines = false;
const check = await workbook.inspect({ kind: "table", range: "CBA_AMD!A1:H10", include: "values", tableMaxRows: 10, tableMaxCols: 8 });
console.log(check.ndjson);
const file = await SpreadsheetFile.exportXlsx(workbook);
await file.save(outputPath);
console.log(JSON.stringify({ cbaRows: rows.length, outputPath }));
