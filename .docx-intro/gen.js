/* 作品介绍文档（图集版）：R5 封面 + 目录 + 七章正文（88 张系统截图内嵌） */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Header, Footer, PageNumber, NumberFormat, AlignmentType, HeadingLevel,
  WidthType, BorderStyle, ShadingType, SectionType, TableLayoutType,
  TableOfContents, VerticalAlign,
} = require("docx");
const fs = require("fs");
const path = require("path");

const IMGD = path.join(__dirname, "..", ".intro-imgs-jpg");
const chapters = JSON.parse(fs.readFileSync(path.join(__dirname, "chapters.json"), "utf-8"));

const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: NB, bottom: NB, left: NB, right: NB };
const allNoBorders = { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: NB, insideVertical: NB };
const F = { hei: { eastAsia: "SimHei", ascii: "Times New Roman" }, song: { eastAsia: "SimSun", ascii: "Times New Roman" } };

function splitTitleLines(title, charsPerLine) {
  if (title.length <= charsPerLine) return [title];
  const breakAfter = new Set([..."\uff0c\u3002\u3001\uff1b\uff1a\uff01\uff1f", ..."\u7684\u4e0e\u548c\u53ca\u4e4b\u5728\u4e8e\u4e3a", ..."-_\u2014\u2013\u00b7/", ..." \t"]);
  const lines = []; let remaining = title;
  while (remaining.length > charsPerLine) {
    let breakAt = -1;
    for (let i = charsPerLine; i >= Math.floor(charsPerLine * 0.6); i--) {
      if (i < remaining.length && breakAfter.has(remaining[i - 1])) { breakAt = i; break; }
    }
    if (breakAt === -1) {
      const limit = Math.min(remaining.length, Math.ceil(charsPerLine * 1.3));
      for (let i = charsPerLine + 1; i < limit; i++) { if (breakAfter.has(remaining[i - 1])) { breakAt = i; break; } }
    }
    if (breakAt === -1) breakAt = charsPerLine;
    lines.push(remaining.slice(0, breakAt).trim());
    remaining = remaining.slice(breakAt).trim();
  }
  if (remaining) lines.push(remaining);
  if (lines.length > 1 && lines[lines.length - 1].length <= 2) {
    const last = lines.pop(); lines[lines.length - 1] += last;
  }
  return lines;
}
function calcTitleLayoutMixed(title, maxWidthTwips, preferredPt = 32, minPt = 22) {
  const units = [...title].reduce((a, ch) => a + (/[\u4e00-\u9fff\u3000-\u303f]/.test(ch) ? 20 : 11), 0);
  let titlePt = preferredPt, lines;
  while (titlePt >= minPt) {
    const widthPt = (units / 20) * titlePt;
    if (widthPt <= maxWidthTwips / 20) { lines = [title]; break; }
    const cpl = Math.max(6, Math.floor(title.length * (maxWidthTwips / 20) / widthPt));
    lines = splitTitleLines(title, cpl);
    if (lines.length <= 2) break;
    titlePt -= 2;
  }
  if (!lines) { lines = splitTitleLines(title, 14); titlePt = minPt; }
  return { titlePt, titleLines: lines };
}
function buildR5MetaTable(metaEntries) {
  const labelPct = 32, valuePct = 68;
  const bottomBorder = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
  const rows = metaEntries.map(entry => new TableRow({
    children: [
      new TableCell({
        width: { size: labelPct, type: WidthType.PERCENTAGE }, borders: noBorders,
        margins: { top: 60, bottom: 60, left: 0, right: 0 },
        children: [new Paragraph({
          alignment: AlignmentType.LEFT, spacing: { before: 60, after: 60, line: 400 },
          children: [new TextRun({ text: entry.label + "\uff1a", size: 24, font: F.song })],
        })],
      }),
      new TableCell({
        width: { size: valuePct, type: WidthType.PERCENTAGE },
        borders: { top: NB, left: NB, right: NB, bottom: bottomBorder },
        margins: { top: 60, bottom: 60, left: 80, right: 0 },
        children: [new Paragraph({
          alignment: AlignmentType.LEFT, spacing: { before: 60, after: 60, line: 400 },
          children: [new TextRun({ text: entry.value, size: 24, font: F.song })],
        })],
      }),
    ],
  }));
  return new Table({
    width: { size: 78, type: WidthType.PERCENTAGE }, alignment: AlignmentType.CENTER,
    layout: TableLayoutType.FIXED, borders: allNoBorders, rows,
  });
}
function buildCoverR5(config) {
  const PAGE_H = 16838, SAFETY = 1200;
  const safeH = PAGE_H - SAFETY;
  const simMarginLR = 1701, simMarginT = 1200;
  const contentW = 11906 - simMarginLR * 2;
  const { titlePt, titleLines } = calcTitleLayoutMixed(config.title, contentW, 32, 22);
  const metaEntries = (config.metaLines || []).map(line => {
    const idx = line.indexOf("\uff1a");
    return idx === -1 ? { label: line, value: "" } : { label: line.slice(0, idx).trim(), value: line.slice(idx + 1).trim() };
  });
  const schoolNameH = config.schoolName ? (22 * 23 + 400) : 0;
  const titleTotalH = titleLines.length * (titlePt * 23 + 200);
  const subtitleH = config.subtitle ? (15 * 23 + 600) : 0;
  const metaTableH = metaEntries.length * 520;
  const footerH = config.footerRight ? (12 * 23 + 200) : 0;
  const fixedH = schoolNameH + titleTotalH + subtitleH + metaTableH + footerH + 3 * 350;
  const remaining = Math.max(safeH - fixedH, 600);
  const topSpacing = Math.min(Math.floor(remaining * 0.26) + simMarginT, 4100);
  const bottomSpacing = Math.min(Math.floor(remaining * 0.24), 4900);
  const midSpacing = Math.min(Math.max(remaining - topSpacing - bottomSpacing + simMarginT, 0), 3200);
  const children = [];
  children.push(new Paragraph({ spacing: { before: topSpacing } }));
  if (config.schoolName) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 400 },
      children: [new TextRun({ text: config.schoolName, size: 44, characterSpacing: 40, font: F.song })],
    }));
  }
  for (let i = 0; i < titleLines.length; i++) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: i < titleLines.length - 1 ? 120 : 300, line: Math.ceil(titlePt * 23), lineRule: "atLeast" },
      children: [new TextRun({ text: titleLines[i], size: titlePt * 2, bold: true, font: { eastAsia: "SimHei", ascii: "Times New Roman" } })],
    }));
  }
  if (config.subtitle) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: config.subtitle, size: 30, font: F.song })],
    }));
  }
  children.push(new Paragraph({ spacing: { before: midSpacing } }));
  children.push(buildR5MetaTable(metaEntries));
  children.push(new Paragraph({ spacing: { before: bottomSpacing } }));
  if (config.footerRight) {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: config.footerRight, size: 24, color: "404040", font: F.song })],
    }));
  }
  return [new Table({
    width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: allNoBorders,
    rows: [new TableRow({
      height: { value: PAGE_H, rule: "exact" },
      children: [new TableCell({
        shading: { type: ShadingType.CLEAR, fill: "FFFFFF" }, borders: noBorders,
        verticalAlign: VerticalAlign.TOP, margins: { left: simMarginLR, right: simMarginLR }, children,
      })],
    })],
  })];
}

const H1 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER,
  spacing: { before: 400, after: 240, line: 312 },
  children: [new TextRun({ text: t, size: 32, bold: true, color: "000000", font: F.hei })],
});
const H2 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 160, line: 312 },
  children: [new TextRun({ text: t, size: 30, bold: true, color: "000000", font: F.hei })],
});
const H3 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_3, spacing: { before: 220, after: 120, line: 312 },
  children: [new TextRun({ text: t, size: 28, bold: true, color: "000000", font: F.hei })],
});
const P = (t) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 100, line: 312 },
  indent: { firstLine: 480 },
  children: [new TextRun({ text: t, size: 24, color: "000000", font: F.song })],
});
function figureBlock(imgPath, pw, ph, caption) {
  const maxW = 560, maxH = 600;
  const scale = Math.min(maxW / pw, maxH / ph, 1);
  const w = Math.max(80, Math.floor(pw * scale));
  const h = Math.max(60, Math.floor(ph * scale));
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 },
      children: [new ImageRun({ data: fs.readFileSync(imgPath), transformation: { width: w, height: h }, type: "jpg" })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 160, line: 280 },
      children: [new TextRun({ text: caption, size: 21, color: "404040", font: F.song })],
    }),
  ];
}
function tableBlock(caption, header, rows) {
  const mk = (text, bold) => new TableCell({
    margins: { top: 50, bottom: 50, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { line: 312 },
      children: [new TextRun({ text, size: 21, bold, color: "000000", font: bold ? F.hei : F.song })],
    })],
  });
  const title = new Paragraph({
    keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 160, after: 100, line: 312 },
    children: [new TextRun({ text: caption, size: 21, bold: true, color: "000000", font: F.hei })],
  });
  const tbl = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 8, color: "000000" },
      bottom: { style: BorderStyle.SINGLE, size: 8, color: "000000" },
      left: NB, right: NB,
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "000000" },
      insideVertical: NB,
    },
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: header.map(h => mk(h, true)) }),
      ...rows.map(r => new TableRow({ cantSplit: true, children: r.map(c => mk(c, false)) })),
    ],
  });
  return [title, tbl, new Paragraph({ spacing: { after: 120 } })];
}

const pageNumFooter = () => new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "606060", font: F.song })],
  })],
});
const docHeader = () => new Header({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "B0B0B0", space: 4 } },
    children: [new TextRun({ text: "\u667a\u8bfe\u5171\u751f\u2014\u2014AI \u4e92\u52a8\u667a\u8bfe\u751f\u6210\u4e0e\u5b9e\u65f6\u95ee\u7b54\u7cfb\u7edf", size: 18, color: "707070", font: F.song })],
  })],
});

const body = [];
let curChapter = 0, figSeq = 0, embedded = 0;
let prevWasImage = false;
for (const it of chapters) {
  if (it.t === "h1") { curChapter += 1; figSeq = 0; prevWasImage = false; body.push(H1(it.x)); }
  else if (it.t === "h2") { prevWasImage = false; body.push(H2(it.x)); }
  else if (it.t === "h3") { prevWasImage = false; body.push(H3(it.x)); }
  else if (it.t === "p") { prevWasImage = false; body.push(P(it.x)); }
  else if (it.t === "tablecap") { prevWasImage = false; body.push(...tableBlock(it.x, it.header, it.rows)); }
  else if (it.t === "imgcap") {
    const fp = path.join(IMGD, it.f);
    if (!fs.existsSync(fp)) continue;
    figSeq += 1; embedded += 1; prevWasImage = true;
    const cap = it.x.replace(/^图-\s*/, "").trim() || "系统运行界面";
    body.push(...figureBlock(fp, it.w, it.h, `图${curChapter}-${figSeq}  ${cap}`));
  }
}
console.log("embedded images:", embedded);

const pgSize = { width: 11906, height: 16838 };
const pgMargin = { top: 1440, bottom: 1440, left: 1701, right: 1417 };
const doc = new Document({
  styles: { default: { document: { run: { font: { eastAsia: "SimSun", ascii: "Times New Roman" }, size: 24, color: "000000" } } } },
  features: { updateFields: true },
  sections: [
    {
      properties: { page: { size: pgSize, margin: { top: 0, bottom: 0, left: 0, right: 0 } } },
      children: buildCoverR5({
        title: "\u667a\u8bfe\u5171\u751f\u2014\u2014AI \u4e92\u52a8\u667a\u8bfe\u751f\u6210\u4e0e\u5b9e\u65f6\u95ee\u7b54\u7cfb\u7edf",
        subtitle: "\u4f5c \u54c1 \u4ecb \u7ecd \u6587 \u6863",
        metaLines: [
          "\u53c2\u8d5b\u8d5b\u9053\uff1a\u4f20\u667a\u676f AI WEB \u7f51\u9875\u5f00\u53d1\u6311\u6218\u8d5b",
          "\u53c2\u8d5b\u56e2\u961f\uff1a\u667a\u8bfe\u5171\u751f\u56e2\u961f",
          "\u5b8c\u6210\u65e5\u671f\uff1a2026 \u5e74 11 \u6708",
        ],
        footerRight: "2026 \u5e74 11 \u6708",
      }),
    },
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: { size: pgSize, margin: pgMargin, pageNumbers: { start: 1, formatType: NumberFormat.UPPER_ROMAN } },
      },
      footers: { default: pageNumFooter() },
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER, spacing: { before: 240, after: 240, line: 312 },
          children: [new TextRun({ text: "\u76ee\u5f55", size: 32, bold: true, color: "000000", font: F.hei })],
        }),
        new TableOfContents("\u76ee\u5f55", { hyperlink: true, headingStyleRange: "1-2" }),
        new Paragraph({
          spacing: { before: 200 },
          children: [new TextRun({ text: "\u63d0\u793a\uff1a\u5728 Word \u4e2d\u53f3\u952e\u70b9\u51fb\u76ee\u5f55\u9009\u62e9\u300c\u66f4\u65b0\u57df\u300d\u4ee5\u5237\u65b0\u9875\u7801\u3002", italics: true, size: 18, color: "909090", font: F.song })],
        }),
      ],
    },
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: { size: pgSize, margin: pgMargin, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } },
      },
      headers: { default: docHeader() },
      footers: { default: pageNumFooter() },
      children: body,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("output.docx", buf);
  console.log("output.docx:", (buf.length / 1048576).toFixed(1) + " MB");
});
