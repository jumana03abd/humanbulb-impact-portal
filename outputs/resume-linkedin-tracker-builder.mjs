import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "/Users/jumanaabdullah/Documents/New project/humanbulb-impact-portal/outputs/resume-linkedin-tracker";
const workbook = Workbook.create();

const overview = workbook.worksheets.add("Overview");
const tracker = workbook.worksheets.add("Tracker");

overview.showGridLines = false;
tracker.showGridLines = false;
overview.freezePanes.freezeRows(4);
tracker.freezePanes.freezeRows(5);

overview.getRange("A1:F1").merge();
overview.getRange("A1").values = [["HUMANBULB Resume + LinkedIn Completion Tracker"]];
overview.getRange("A2:F2").merge();
overview.getRange("A2").values = [["Green Careers Launchpad | Staff-facing workbook for tracking participant career materials"]];

overview.getRange("A4:B9").values = [
  ["Metric", "Current"],
  ["Participants entered", null],
  ["Resume complete", null],
  ["LinkedIn complete", null],
  ["Both complete", null],
  ["Both completion rate", null],
];

overview.getRange("B5:B9").formulas = [
  ["=COUNTA('Tracker'!A6:A205)"],
  ['=COUNTIF(\'Tracker\'!E6:E205,"Complete")'],
  ['=COUNTIF(\'Tracker\'!G6:G205,"Complete")'],
  ['=COUNTIFS(\'Tracker\'!E6:E205,"Complete",\'Tracker\'!G6:G205,"Complete")'],
  ['=IF(B5=0,0,B8/B5)'],
];

overview.getRange("D4:F9").values = [
  ["How to use", null, null],
  ["1", "Enter one participant per row on the Tracker sheet.", null],
  ["2", "Update Resume Status and LinkedIn Status as staff verify completion.", null],
  ["3", "Add completion dates when materials are finalized.", null],
  ["4", "Use Verified By and Last Updated for auditability.", null],
  ["5", "The summary on the left updates automatically.", null],
];

overview.getRange("A11:F13").merge();
overview.getRange("A11").values = [[
  "Suggested portal rule: count a participant as fully career-materials complete only when both Resume Status and LinkedIn Status are marked Complete."
]];

tracker.getRange("A1:K2").merge();
tracker.getRange("A1").values = [["Participant-Level Tracking"]];
tracker.getRange("A3:K3").merge();
tracker.getRange("A3").values = [[
  "Update status fields as participants complete their materials. Use the Notes column for exceptions such as missing consent, no LinkedIn account, or pending staff review."
]];

tracker.getRange("A5:K5").values = [[
  "Participant ID",
  "First Name",
  "Last Name",
  "Pathway / Cohort",
  "Resume Status",
  "Resume Completed Date",
  "LinkedIn Status",
  "LinkedIn Completed Date",
  "Verified By",
  "Last Updated",
  "Notes",
]];

const dataRows = Array.from({ length: 20 }, (_, index) => [
  `GCL-${String(index + 1).padStart(3, "0")}`,
  "",
  "",
  "",
  "Not Started",
  null,
  "Not Started",
  null,
  "",
  null,
  "",
]);

tracker.getRange(`A6:K${5 + dataRows.length}`).values = dataRows;

overview.getRange("A1:F13").format = {
  verticalAlignment: "Center",
};
overview.getRange("A1:F1").format = {
  fill: "#21446C",
  font: { bold: true, color: "#FFFFFF", size: 16 },
  horizontalAlignment: "Left",
};
overview.getRange("A2:F2").format = {
  fill: "#FDE895",
  font: { color: "#21446C", italic: true, size: 10 },
};
overview.getRange("A4:B4").format = {
  fill: "#F4C430",
  font: { bold: true, color: "#0F2747" },
};
overview.getRange("D4:F4").format = {
  fill: "#21446C",
  font: { bold: true, color: "#FFFFFF" },
};
overview.getRange("A5:B9").format = {
  fill: "#FFFDF4",
  borders: { preset: "all", style: "thin", color: "#D7D9DD" },
};
overview.getRange("D5:F9").format = {
  fill: "#FFFDF4",
  borders: { preset: "all", style: "thin", color: "#D7D9DD" },
  wrapText: true,
};
overview.getRange("A11:F13").format = {
  fill: "#FFF5CC",
  font: { color: "#5A4A10" },
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#E3C458" },
};
overview.getRange("B5:B8").format.numberFormat = "#,##0";
overview.getRange("B9").format.numberFormat = "0%";

tracker.getRange("A1:K2").format = {
  fill: "#21446C",
  font: { bold: true, color: "#FFFFFF", size: 15 },
  horizontalAlignment: "Left",
  verticalAlignment: "Center",
};
tracker.getRange("A3:K3").format = {
  fill: "#FFF5CC",
  font: { color: "#5A4A10", size: 10 },
  wrapText: true,
};
tracker.getRange("A5:K5").format = {
  fill: "#F4C430",
  font: { bold: true, color: "#0F2747" },
  horizontalAlignment: "Center",
  verticalAlignment: "Center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D3B24A" },
};
tracker.getRange(`A6:K${5 + dataRows.length}`).format = {
  fill: "#FFFFFF",
  borders: { preset: "all", style: "thin", color: "#D9D9D9" },
  verticalAlignment: "Center",
};

tracker.getRange("E6:E205").dataValidation = {
  rule: { type: "list", values: ["Not Started", "In Progress", "Complete", "Not Applicable"] },
};
tracker.getRange("G6:G205").dataValidation = {
  rule: { type: "list", values: ["Not Started", "In Progress", "Complete", "Not Applicable"] },
};

tracker.getRange("F6:F205").format.numberFormat = "yyyy-mm-dd";
tracker.getRange("H6:H205").format.numberFormat = "yyyy-mm-dd";
tracker.getRange("J6:J205").format.numberFormat = "yyyy-mm-dd";

tracker.getRange("E6:E205").conditionalFormats.add("cellIs", {
  operator: "equal",
  formula: '"Complete"',
  format: { fill: "#DCEEE2", font: { color: "#256F47", bold: true } },
});
tracker.getRange("G6:G205").conditionalFormats.add("cellIs", {
  operator: "equal",
  formula: '"Complete"',
  format: { fill: "#DCEEE2", font: { color: "#256F47", bold: true } },
});
tracker.getRange("E6:E205").conditionalFormats.add("cellIs", {
  operator: "equal",
  formula: '"In Progress"',
  format: { fill: "#FFF5CC", font: { color: "#7C6106", bold: true } },
});
tracker.getRange("G6:G205").conditionalFormats.add("cellIs", {
  operator: "equal",
  formula: '"In Progress"',
  format: { fill: "#FFF5CC", font: { color: "#7C6106", bold: true } },
});

overview.getRange("A1:F13").format.autofitColumns();
overview.getRange("A1:F13").format.autofitRows();
tracker.getRange("A1:K25").format.autofitColumns();
tracker.getRange("A1:K25").format.autofitRows();
tracker.getRange("5:5").format.rowHeight = 34;
tracker.getRange("3:3").format.rowHeight = 28;

tracker.getRange("A:A").format.columnWidth = 14;
tracker.getRange("B:C").format.columnWidth = 14;
tracker.getRange("D:D").format.columnWidth = 18;
tracker.getRange("E:E").format.columnWidth = 16;
tracker.getRange("F:F").format.columnWidth = 16;
tracker.getRange("G:G").format.columnWidth = 16;
tracker.getRange("H:H").format.columnWidth = 18;
tracker.getRange("I:I").format.columnWidth = 14;
tracker.getRange("J:J").format.columnWidth = 14;
tracker.getRange("K:K").format.columnWidth = 26;

const overviewInspect = await workbook.inspect({
  kind: "table",
  sheetId: "Overview",
  range: "A4:F13",
  tableMaxRows: 12,
  tableMaxCols: 6,
  maxChars: 2500,
});
console.log(overviewInspect.ndjson);

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
  maxChars: 1500,
});
console.log(formulaErrors.ndjson);

await fs.mkdir(outputDir, { recursive: true });

const overviewPreview = await workbook.render({
  sheetName: "Overview",
  range: "A1:F13",
  autoCrop: "all",
  scale: 2,
  format: "png",
});
await fs.writeFile(path.join(outputDir, "overview-preview.png"), new Uint8Array(await overviewPreview.arrayBuffer()));

const trackerPreview = await workbook.render({
  sheetName: "Tracker",
  range: "A1:K20",
  autoCrop: "all",
  scale: 2,
  format: "png",
});
await fs.writeFile(path.join(outputDir, "tracker-preview.png"), new Uint8Array(await trackerPreview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, "humanbulb-resume-linkedin-completion-tracker.xlsx"));
