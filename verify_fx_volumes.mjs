import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import fs from "node:fs/promises";

const path = "/Users/cuperuser/kostyA/Talent Hub/team-2-aitalenthack/outputs/fx_volumes_central_asia_caucasus_2015_2026.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
const summary = await workbook.inspect({
  kind: "table",
  range: "NBT_TJS_monthly!A1:H14",
  include: "values",
  tableMaxRows: 14,
  tableMaxCols: 8,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula-error scan",
});
const preview = await workbook.render({ sheetName: "NBT_TJS_monthly", range: "A1:H14", scale: 1.5 });
await fs.writeFile("/Users/cuperuser/kostyA/Talent Hub/team-2-aitalenthack/outputs/kase_preview.png", new Uint8Array(await preview.arrayBuffer()));
console.log(summary.ndjson);
console.log(errors.ndjson);
