import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const book = await SpreadsheetFile.importXlsx(await FileBlob.load("/tmp/armenia_fx_daily.xlsx"));
console.log(JSON.stringify({ sheets: book.worksheets.items.map((sheet) => sheet.name) }));
for (const sheet of book.worksheets.items) {
  const result = await book.inspect({ kind: "table", range: `${sheet.name}!A1:Z20`, include: "values", tableMaxRows: 20, tableMaxCols: 26 });
  console.log(result.ndjson);
}
