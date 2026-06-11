const pptxgen = require("pptxgenjs");

// ── Palette ───────────────────────────────────────────────────────────────────
const C = {
  navy:    "0B2447",
  teal:    "19376D",
  accent:  "0096C7",
  light:   "A5D8DD",
  white:   "FFFFFF",
  offwhite:"F4F6F8",
  grey:    "64748B",
  green:   "27AE60",
  red:     "E74C3C",
  orange:  "E67E22",
  amber:   "F59E0B",
  bg:      "0D1B2A",
};

// ── Sizes (inches, 16:9 = 10 x 5.625) ────────────────────────────────────────
const W = 10, H = 5.625;

// ── Shared styles ─────────────────────────────────────────────────────────────
const TITLE_STYLE = { fontFace: "Calibri", bold: true, color: C.white };
const BODY_STYLE  = { fontFace: "Calibri", color: C.white };
const DARK_BODY   = { fontFace: "Calibri", color: C.navy };

// ─────────────────────────────────────────────────────────────────────────────
// DATA (pulled from Python analysis results)
// ─────────────────────────────────────────────────────────────────────────────
const FUNDS_1Y = [
  { name: "ICICI Pru Equity & Debt",     cagr: 63.7,  sharpe: 4.046, vol: 14.1, mdd: -4.9,  risk: "Moderately High", cat: "Hybrid"   },
  { name: "Axis Midcap Fund",             cagr: 57.9,  sharpe: 2.443, vol: 21.0, mdd: -11.5, risk: "Moderately High", cat: "Equity"   },
  { name: "ABSL Frontline Equity",        cagr: 39.3,  sharpe: 1.996, vol: 16.4, mdd: -9.2,  risk: "Moderate",        cat: "Equity"   },
  { name: "Mirae Asset Large Cap",        cagr: 32.9,  sharpe: 1.684, vol: 15.6, mdd: -7.1,  risk: "Moderate",        cat: "Equity"   },
  { name: "Kotak Emerging Equity",        cagr: 29.0,  sharpe: 1.023, vol: 21.9, mdd: -16.3, risk: "Moderately High", cat: "Equity"   },
  { name: "ICICI Pru Flexicap",           cagr: 25.9,  sharpe: 1.031, vol: 18.8, mdd: -12.0, risk: "Moderately High", cat: "Equity"   },
  { name: "HDFC Index Fund Nifty 50",     cagr: 23.6,  sharpe: 1.186, vol: 14.4, mdd: -8.9,  risk: "Moderate",        cat: "Index"    },
  { name: "UTI Nifty Index Fund",         cagr: 20.5,  sharpe: 0.906, vol: 15.4, mdd: -8.7,  risk: "Moderate",        cat: "Index"    },
  { name: "Axis Bluechip Fund",           cagr: 18.2,  sharpe: 0.752, vol: 15.6, mdd: -9.0,  risk: "Moderate",        cat: "Equity"   },
  { name: "Parag Parikh Flexi Cap",       cagr: 11.8,  sharpe: 0.320, vol: 16.5, mdd: -7.7,  risk: "Moderately High", cat: "Equity"   },
  { name: "Axis ELSS Tax Saver",          cagr: 10.9,  sharpe: 0.239, vol: 18.3, mdd: -22.3, risk: "Moderately High", cat: "Equity"   },
  { name: "ICICI Pru Corporate Bond",     cagr: 10.2,  sharpe: 0.943, vol:  4.0, mdd: -1.5,  risk: "Moderate",        cat: "Debt"     },
  { name: "Mirae Asset Cash Mgmt",        cagr:  6.1,  sharpe:-0.851, vol:  0.5, mdd: -0.1,  risk: "Low",             cat: "Debt"     },
  { name: "SBI Bluechip Fund",            cagr:  5.5,  sharpe:-0.310, vol:  3.3, mdd: -2.2,  risk: "Moderate",        cat: "Equity"   },
  { name: "HDFC Liquid Fund",             cagr:  3.7,  sharpe:-5.250, vol:  0.5, mdd: -0.1,  risk: "Low",             cat: "Debt"     },
  { name: "SBI Small Cap Fund",           cagr:  1.1,  sharpe:-0.200, vol: 27.1, mdd: -18.2, risk: "High",            cat: "Equity"   },
  { name: "HDFC Balanced Advantage",      cagr:  0.4,  sharpe:-0.501, vol: 12.2, mdd: -23.3, risk: "Moderately High", cat: "Hybrid"   },
  { name: "HDFC Top 100 Fund",            cagr:-12.1,  sharpe:-0.645, vol: 28.9, mdd: -36.9, risk: "Moderate",        cat: "Equity"   },
  { name: "HDFC Mid-Cap Opportunities",   cagr:-16.8,  sharpe:-0.985, vol: 23.6, mdd: -28.1, risk: "Moderately High", cat: "Equity"   },
];

const CAT_AVG = [
  { cat: "Aggressive Hybrid",  cagr_1y: 63.7, cagr_3y: 40.3, cagr_5y: 25.4 },
  { cat: "Mid Cap",            cagr_1y: 23.4, cagr_3y: 15.6, cagr_5y: 12.1 },
  { cat: "Large Cap Index",    cagr_1y: 22.0, cagr_3y: 24.8, cagr_5y: 18.9 },
  { cat: "Large Cap",          cagr_1y: 16.7, cagr_3y: 22.2, cagr_5y: 18.5 },
  { cat: "Flexi Cap",          cagr_1y: 18.8, cagr_3y: 20.2, cagr_5y: 11.1 },
  { cat: "ELSS",               cagr_1y: 10.9, cagr_3y: 14.6, cagr_5y: 10.3 },
  { cat: "Corporate Bond",     cagr_1y: 10.2, cagr_3y: 12.6, cagr_5y:  8.8 },
  { cat: "Small Cap",          cagr_1y:  1.1, cagr_3y: 25.0, cagr_5y: 27.0 },
  { cat: "Balanced Advantage", cagr_1y:  0.4, cagr_3y:  9.2, cagr_5y:  8.9 },
  { cat: "Liquid",             cagr_1y:  4.9, cagr_3y:  5.0, cagr_5y:  5.1 },
];

// ─────────────────────────────────────────────────────────────────────────────
// HELPER FUNCTIONS
// ─────────────────────────────────────────────────────────────────────────────

function darkSlide(prs) {
  const sl = prs.addSlide();
  sl.background = { color: C.bg };
  return sl;
}

function navySlide(prs) {
  const sl = prs.addSlide();
  sl.background = { color: C.navy };
  return sl;
}

function lightSlide(prs) {
  const sl = prs.addSlide();
  sl.background = { color: C.offwhite };
  return sl;
}

function addSectionTitle(sl, text) {
  // Left accent bar
  sl.addShape(prs.shapes.RECTANGLE, {
    x: 0.4, y: 0.25, w: 0.06, h: 0.45,
    fill: { color: C.accent }, line: { color: C.accent }
  });
  sl.addText(text, {
    x: 0.55, y: 0.22, w: 9.0, h: 0.55,
    fontSize: 22, bold: true, color: C.white,
    fontFace: "Calibri", valign: "middle", margin: 0
  });
}

function addSlideNum(sl, num, total) {
  sl.addText(`${num} / ${total}`, {
    x: 8.8, y: 5.35, w: 1.0, h: 0.2,
    fontSize: 8, color: C.grey, align: "right",
    fontFace: "Calibri", margin: 0
  });
}

function kpiBox(sl, x, y, w, h, value, label, color) {
  sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h: h,
    fill: { color: color || C.teal },
    line: { color: color || C.teal },
    rectRadius: 0.08
  });
  sl.addText(value, {
    x, y: y + 0.05, w, h: h * 0.58,
    fontSize: 20, bold: true, color: C.white,
    align: "center", valign: "middle", fontFace: "Calibri", margin: 0
  });
  sl.addText(label, {
    x, y: y + h * 0.60, w, h: h * 0.35,
    fontSize: 8.5, color: C.light,
    align: "center", valign: "top", fontFace: "Calibri", margin: 0
  });
}

function barH(sl, x, y, barW, barH_px, value, maxVal, color, label, pctLabel) {
  const filledW = (value / maxVal) * barW;
  // Background bar
  sl.addShape(prs.shapes.RECTANGLE, {
    x, y, w: barW, h: barH_px,
    fill: { color: "1E2E45" }, line: { color: "1E2E45" }
  });
  // Value bar
  if (filledW > 0.01) {
    sl.addShape(prs.shapes.RECTANGLE, {
      x, y, w: filledW, h: barH_px,
      fill: { color: color }, line: { color: color }
    });
  }
  // Label
  sl.addText(label, {
    x: 0.35, y: y - 0.01, w: x - 0.45, h: barH_px + 0.02,
    fontSize: 7.5, color: C.white, align: "right",
    fontFace: "Calibri", valign: "middle", margin: 0
  });
  // Value label
  sl.addText(pctLabel, {
    x: x + filledW + 0.05, y: y - 0.01, w: 0.7, h: barH_px + 0.02,
    fontSize: 7.5, color: C.accent, fontFace: "Calibri",
    valign: "middle", margin: 0
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// BUILD PRESENTATION
// ─────────────────────────────────────────────────────────────────────────────

const prs = new pptxgen();
prs.layout = "LAYOUT_16x9";
prs.title  = "Bluestock Mutual Fund Analytics Capstone";
prs.author = "Bluestock Analytics Team";

const TOTAL = 14;

// ─── SLIDE 1: COVER ──────────────────────────────────────────────────────────
{
  const sl = navySlide(prs);

  // Geometric accent shapes
  sl.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: 0, w: W, h: 1.2,
    fill: { color: C.teal }, line: { color: C.teal }
  });
  sl.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: H - 0.9, w: W, h: 0.9,
    fill: { color: C.accent }, line: { color: C.accent }
  });
  sl.addShape(prs.shapes.OVAL, {
    x: 7.2, y: 0.8, w: 3.5, h: 3.5,
    fill: { color: "FFFFFF08" }, line: { color: "FFFFFF15", width: 1 }
  });
  sl.addShape(prs.shapes.OVAL, {
    x: -0.8, y: 3.2, w: 2.5, h: 2.5,
    fill: { color: "FFFFFF05" }, line: { color: "FFFFFF10", width: 1 }
  });

  sl.addText("BLUESTOCK", {
    x: 0.6, y: 1.3, w: 8.8, h: 0.55,
    fontSize: 13, bold: true, color: C.accent,
    charSpacing: 8, fontFace: "Calibri", margin: 0
  });
  sl.addText("Mutual Fund Analytics", {
    x: 0.6, y: 1.85, w: 8.8, h: 0.85,
    fontSize: 38, bold: true, color: C.white,
    fontFace: "Calibri", margin: 0
  });
  sl.addText("Capstone Project — Final Presentation", {
    x: 0.6, y: 2.72, w: 8.8, h: 0.5,
    fontSize: 17, color: C.light,
    fontFace: "Calibri", margin: 0
  });

  sl.addShape(prs.shapes.LINE, {
    x: 0.6, y: 3.32, w: 4.0, h: 0,
    line: { color: C.accent, width: 1.5 }
  });

  sl.addText([
    { text: "19 Funds  ", options: { bold: true, color: C.accent } },
    { text: "·  70,797 NAV Records  ·  5 Years  ·  4 Categories  ·  10 Benchmarks", options: { color: C.light } }
  ], { x: 0.6, y: 3.5, w: 8.8, h: 0.35, fontSize: 11, fontFace: "Calibri", margin: 0 });

  sl.addText("Data Source: AMFI India via mfapi.in  |  Bluestock Analytics Team  |  2025", {
    x: 0, y: H - 0.75, w: W, h: 0.35,
    fontSize: 9, color: C.white, align: "center",
    fontFace: "Calibri", margin: 0
  });
}

// ─── SLIDE 2: AGENDA ─────────────────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Agenda");
  addSlideNum(sl, 2, TOTAL);

  const items = [
    ["01", "Project Overview & Objectives"],
    ["02", "Dataset & Data Pipeline"],
    ["03", "Exploratory Data Analysis"],
    ["04", "Performance Analytics — Returns"],
    ["05", "Risk Analytics"],
    ["06", "Advanced Analytics (VaR · Monte Carlo · Markowitz)"],
    ["07", "Streamlit Dashboard Demo"],
    ["08", "Key Insights & Recommendations"],
    ["09", "Limitations & Future Work"],
    ["10", "Conclusion"],
  ];

  const cols = [items.slice(0, 5), items.slice(5)];
  cols.forEach((col, ci) => {
    col.forEach(([num, text], i) => {
      const y = 1.05 + i * 0.43;
      const x = ci === 0 ? 0.5 : 5.2;
      sl.addShape(prs.shapes.RECTANGLE, {
        x, y, w: 0.32, h: 0.3,
        fill: { color: C.accent }, line: { color: C.accent }
      });
      sl.addText(num, {
        x, y, w: 0.32, h: 0.3,
        fontSize: 9, bold: true, color: C.white,
        align: "center", valign: "middle", fontFace: "Calibri", margin: 0
      });
      sl.addText(text, {
        x: x + 0.38, y: y, w: 4.1, h: 0.3,
        fontSize: 11, color: C.white,
        fontFace: "Calibri", valign: "middle", margin: 0
      });
    });
  });
}

// ─── SLIDE 3: PROJECT OVERVIEW ───────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Project Overview");
  addSlideNum(sl, 3, TOTAL);

  // Objective box
  sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
    x: 0.4, y: 0.92, w: 9.2, h: 0.85,
    fill: { color: C.teal }, line: { color: C.teal }, rectRadius: 0.06
  });
  sl.addText("Objective: Build a production-grade mutual fund analytics platform to ingest, clean, transform, and analyse Indian MF NAV data — computing institutional-quality metrics and delivering insights via interactive dashboards.", {
    x: 0.55, y: 0.95, w: 8.9, h: 0.78,
    fontSize: 10.5, color: C.white, fontFace: "Calibri",
    valign: "middle", margin: 0
  });

  // 5 layers
  const layers = [
    { n: "L1", label: "Ingestion",       desc: "mfapi.in API + CSV adapter" },
    { n: "L2", label: "Cleaning",        desc: "Dedup · FFill · Outlier flag" },
    { n: "L3", label: "Transform",       desc: "Returns · Vol · 52W H/L" },
    { n: "L4", label: "Analytics",       desc: "15 metrics × 4 periods" },
    { n: "L5", label: "Delivery",        desc: "SQLite · Notebooks · Dashboard" },
  ];

  const xStart = 0.4, boxW = 1.72, gap = 0.1;
  layers.forEach((l, i) => {
    const x = xStart + i * (boxW + gap);
    sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x, y: 2.05, w: boxW, h: 1.6,
      fill: { color: i === 4 ? C.accent : "1E3A5F" },
      line: { color: C.accent, width: 0.8 }, rectRadius: 0.07
    });
    sl.addText(l.n, {
      x, y: 2.1, w: boxW, h: 0.38,
      fontSize: 14, bold: true, color: C.accent,
      align: "center", fontFace: "Calibri", margin: 0
    });
    sl.addText(l.label, {
      x, y: 2.5, w: boxW, h: 0.35,
      fontSize: 11, bold: true, color: C.white,
      align: "center", fontFace: "Calibri", margin: 0
    });
    sl.addText(l.desc, {
      x, y: 2.87, w: boxW, h: 0.6,
      fontSize: 8.5, color: C.light,
      align: "center", fontFace: "Calibri", margin: 0
    });
    // Arrow
    if (i < 4) {
      sl.addShape(prs.shapes.LINE, {
        x: x + boxW, y: 2.85, w: gap, h: 0,
        line: { color: C.accent, width: 1.5 }
      });
    }
  });

  // Deliverables row
  const delivs = ["D1 ETL Pipeline","D2 SQLite DB","D3 EDA","D4 Metrics","D5 Dashboard","D6 Advanced","D7 Report + Slides","B1–B4 Bonus"];
  sl.addText("Deliverables: " + delivs.join("  ·  "), {
    x: 0.4, y: 3.9, w: 9.2, h: 0.35,
    fontSize: 8.5, color: C.grey, fontFace: "Calibri", margin: 0
  });

  // Stats row
  [
    ["19", "Funds"],["70,797","NAV Rows"],["5 Yrs","History"],
    ["15","Metrics"],["4","Periods"],["6","DB Views"],["31","Unit Tests"],
  ].forEach(([val, lbl], i) => {
    kpiBox(sl, 0.4 + i * 1.32, 4.35, 1.22, 0.9, val, lbl, "1E3A5F");
  });
}

// ─── SLIDE 4: DATASET ────────────────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Dataset & Data Pipeline");
  addSlideNum(sl, 4, TOTAL);

  // Left: table of categories
  sl.addText("Fund Universe — 19 Funds Across 4 Categories", {
    x: 0.4, y: 0.95, w: 5.5, h: 0.35,
    fontSize: 11, bold: true, color: C.accent, fontFace: "Calibri", margin: 0
  });

  const cats = [
    ["Category",        "Sub-Category",       "#"],
    ["Equity",          "Large Cap",           "4"],
    ["Equity",          "Mid Cap",             "4"],
    ["Equity",          "Small Cap",           "1"],
    ["Equity",          "Flexi Cap",           "2"],
    ["Equity",          "ELSS",                "1"],
    ["Debt",            "Liquid",              "2"],
    ["Debt",            "Corporate Bond",      "1"],
    ["Hybrid",          "Aggressive Hybrid",   "1"],
    ["Hybrid",          "Balanced Advantage",  "1"],
    ["Index",           "Large Cap Index",     "2"],
  ];

  cats.forEach((row, i) => {
    const y = 1.35 + i * 0.34;
    const isHdr = i === 0;
    const bg = isHdr ? C.teal : (i % 2 === 0 ? "121E2E" : "162438");
    sl.addShape(prs.shapes.RECTANGLE, {
      x: 0.4, y, w: 5.4, h: 0.33,
      fill: { color: bg }, line: { color: "1E3A5F", width: 0.3 }
    });
    [row[0], row[1], row[2]].forEach((cell, ci) => {
      const cx = [0.45, 1.65, 4.9][ci];
      const cw = [1.15, 3.20, 0.65][ci];
      sl.addText(cell, {
        x: cx, y: y + 0.04, w: cw, h: 0.26,
        fontSize: isHdr ? 9 : 8.5,
        bold: isHdr, color: isHdr ? C.white : (ci === 2 ? C.accent : C.white),
        fontFace: "Calibri", valign: "middle",
        align: ci === 2 ? "center" : "left", margin: 0
      });
    });
  });

  // Right: pipeline stats
  sl.addText("Pipeline & Database Stats", {
    x: 6.1, y: 0.95, w: 3.6, h: 0.35,
    fontSize: 11, bold: true, color: C.accent, fontFace: "Calibri", margin: 0
  });

  const stats = [
    ["70,797",  "NAV Rows (5 years)"],
    ["13,052",  "Benchmark Data Points"],
    ["76",      "Metric Records (19×4)"],
    ["8",       "DB Tables"],
    ["6",       "Analytical Views"],
    ["12",      "Performance Indexes"],
    ["2021–2026","Date Range"],
    ["10",      "Benchmark Indices"],
  ];
  stats.forEach(([val, lbl], i) => {
    const row = Math.floor(i / 2), col = i % 2;
    kpiBox(sl, 6.1 + col * 1.82, 1.35 + row * 1.0, 1.72, 0.85, val, lbl, "1E3A5F");
  });
}

// ─── SLIDE 5: EDA ─────────────────────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Exploratory Data Analysis");
  addSlideNum(sl, 5, TOTAL);

  // 6 insight boxes
  const insights = [
    { icon: "📈", title: "Equity Dominance",  text: "Equity avg 1Y CAGR: 17.4% vs Debt avg: 6.5%" },
    { icon: "🔗", title: "Correlation",        text: "Inter-fund correlations 0.3–0.7; diversification benefits exist" },
    { icon: "📉", title: "Debt Stability",     text: "Liquid funds: max drawdown <0.1%, volatility <0.5%" },
    { icon: "🌊", title: "Volatility Spread",  text: "Liquid: 0.5% vol → Small Cap: 27.1% vol annualised" },
    { icon: "📅", title: "No Seasonality",     text: "No significant monthly return pattern found across funds" },
    { icon: "🏆", title: "Hybrid Edge",        text: "Aggressive Hybrid: equity-like return with 14% volatility" },
  ];

  insights.forEach((ins, i) => {
    const col = i % 3, row = Math.floor(i / 2);
    const x = 0.4 + col * 3.1, y = 1.05 + row * 1.88;
    sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x, y, w: 2.95, h: 1.72,
      fill: { color: "12263D" }, line: { color: C.teal, width: 0.8 }, rectRadius: 0.08
    });
    sl.addText(ins.icon + "  " + ins.title, {
      x: x + 0.12, y: y + 0.15, w: 2.72, h: 0.38,
      fontSize: 11, bold: true, color: C.accent,
      fontFace: "Calibri", margin: 0
    });
    sl.addText(ins.text, {
      x: x + 0.12, y: y + 0.55, w: 2.72, h: 0.95,
      fontSize: 9.5, color: C.white, fontFace: "Calibri",
      margin: 0, valign: "top"
    });
  });
}

// ─── SLIDE 6: RETURNS LEADERBOARD ────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Performance Analytics — 1-Year CAGR");
  addSlideNum(sl, 6, TOTAL);

  // Two columns: top 8 + bottom 5
  const sorted = [...FUNDS_1Y].sort((a, b) => b.cagr - a.cagr);
  const top8   = sorted.slice(0, 8);
  const bot5   = sorted.slice(-5);

  sl.addText("Top Performers", {
    x: 0.35, y: 0.95, w: 5.5, h: 0.3,
    fontSize: 10, bold: true, color: C.green, fontFace: "Calibri", margin: 0
  });

  const maxCagr = 70;
  const barX = 2.35, barMaxW = 3.3, bH = 0.3, bGap = 0.1;

  top8.forEach((f, i) => {
    const y = 1.3 + i * (bH + bGap);
    const color = f.cagr >= 30 ? C.green : f.cagr >= 10 ? C.accent : C.amber;
    barH(sl, barX, y, barMaxW, bH, f.cagr, maxCagr, color,
         f.name.slice(0, 22), `${f.cagr.toFixed(1)}%`);
  });

  sl.addText("Underperformers", {
    x: 5.9, y: 0.95, w: 3.8, h: 0.3,
    fontSize: 10, bold: true, color: C.red, fontFace: "Calibri", margin: 0
  });

  bot5.forEach((f, i) => {
    const y = 1.3 + i * (bH + bGap);
    const x = 6.85, bW = 2.5;
    const absV = Math.abs(f.cagr);
    const filledW = (absV / maxCagr) * bW;
    sl.addShape(prs.shapes.RECTANGLE, {
      x, y, w: bW, h: bH,
      fill: { color: "1E2E45" }, line: { color: "1E2E45" }
    });
    if (filledW > 0.01) {
      sl.addShape(prs.shapes.RECTANGLE, {
        x, y, w: filledW, h: bH,
        fill: { color: C.red }, line: { color: C.red }
      });
    }
    sl.addText(f.name.slice(0, 22), {
      x: 5.9, y: y - 0.01, w: 2.85, h: bH + 0.02,
      fontSize: 7.5, color: C.white, align: "right",
      fontFace: "Calibri", valign: "middle", margin: 0
    });
    sl.addText(`${f.cagr.toFixed(1)}%`, {
      x: x + filledW + 0.05, y: y - 0.01, w: 0.7, h: bH + 0.02,
      fontSize: 7.5, color: C.red, fontFace: "Calibri",
      valign: "middle", margin: 0
    });
  });

  // Category averages at bottom
  sl.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: 4.95, w: W, h: 0.65,
    fill: { color: "0D1E30" }, line: { color: "0D1E30" }
  });
  const catKeys = ["Aggressive Hybrid","Mid Cap","Large Cap Index","Large Cap","Flexi Cap","Corporate Bond","Liquid"];
  const catVals  = [63.7, 23.4, 22.0, 16.7, 18.8, 10.2, 4.9];
  catKeys.forEach((k, i) => {
    const x = 0.5 + i * 1.36;
    sl.addText(catVals[i].toFixed(1) + "%", {
      x, y: 5.0, w: 1.25, h: 0.25,
      fontSize: 11, bold: true, color: C.accent,
      align: "center", fontFace: "Calibri", margin: 0
    });
    sl.addText(k, {
      x, y: 5.25, w: 1.25, h: 0.28,
      fontSize: 7, color: C.grey,
      align: "center", fontFace: "Calibri", margin: 0
    });
  });
}

// ─── SLIDE 7: RISK ANALYTICS ──────────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Risk Analytics");
  addSlideNum(sl, 7, TOTAL);

  // Left: Risk metrics for top funds
  sl.addText("Key Risk Metrics — 1Y", {
    x: 0.4, y: 0.95, w: 5.5, h: 0.3,
    fontSize: 11, bold: true, color: C.accent, fontFace: "Calibri", margin: 0
  });

  const riskFunds = FUNDS_1Y.slice(0, 8);
  const hdrs = ["Fund", "Vol%", "MDD%", "Sharpe", "Beta"];
  const hdrW = [2.4, 0.65, 0.72, 0.72, 0.72];

  hdrs.forEach((h, ci) => {
    const hx = ci === 0 ? 0.4 : 2.4 + (ci - 1) * 0.72;
    sl.addShape(prs.shapes.RECTANGLE, {
      x: hx, y: 1.28, w: hdrW[ci], h: 0.28,
      fill: { color: C.teal }, line: { color: C.teal }
    });
    sl.addText(h, {
      x: hx + 0.03, y: 1.28, w: hdrW[ci] - 0.06, h: 0.28,
      fontSize: 8.5, bold: true, color: C.white,
      align: ci === 0 ? "left" : "center",
      fontFace: "Calibri", valign: "middle", margin: 0
    });
  });

  riskFunds.forEach((f, i) => {
    const y = 1.58 + i * 0.33;
    const bg = i % 2 === 0 ? "121E2E" : "162438";
    sl.addShape(prs.shapes.RECTANGLE, {
      x: 0.4, y, w: 5.1, h: 0.32,
      fill: { color: bg }, line: { color: "1E3A5F", width: 0.3 }
    });

    const cells = [
      { v: f.name.slice(0, 23), align: "left",   x: 0.43, w: 2.34 },
      { v: f.vol.toFixed(1)+"%", align: "center", x: 2.4,  w: 0.64 },
      { v: f.mdd.toFixed(1)+"%", align: "center", x: 3.12, w: 0.70 },
      { v: f.sharpe.toFixed(3),  align: "center", x: 3.84, w: 0.70 },
      { v: "—",                  align: "center", x: 4.56, w: 0.70 },
    ];
    const sharpeColor = f.sharpe >= 1 ? C.green : f.sharpe >= 0 ? C.amber : C.red;
    cells.forEach((c, ci) => {
      sl.addText(c.v, {
        x: c.x, y: y + 0.04, w: c.w, h: 0.25,
        fontSize: 8, color: ci === 3 ? sharpeColor : C.white,
        align: c.align, fontFace: "Calibri", valign: "middle", margin: 0
      });
    });
  });

  // Right: 4 risk insight boxes
  sl.addText("Risk Insights", {
    x: 6.0, y: 0.95, w: 3.6, h: 0.3,
    fontSize: 11, bold: true, color: C.accent, fontFace: "Calibri", margin: 0
  });

  const riskInsights = [
    { title: "Sharpe > 1",  val: "8 of 19",  desc: "funds delivered risk-adjusted return above threshold" },
    { title: "Avg Vol",     val: "14.1%",     desc: "average annualised volatility across all equity funds" },
    { title: "Worst MDD",   val: "-36.9%",    desc: "HDFC Top 100 Fund over the measured period" },
    { title: "Best MDD",    val: "-0.09%",    desc: "HDFC Liquid Fund — near-zero drawdown as expected" },
  ];
  riskInsights.forEach((ins, i) => {
    const y = 1.28 + i * 1.05;
    sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x: 6.0, y, w: 3.65, h: 0.92,
      fill: { color: "12263D" }, line: { color: C.teal, width: 0.7 }, rectRadius: 0.06
    });
    sl.addText(ins.title, {
      x: 6.12, y: y + 0.08, w: 1.4, h: 0.28,
      fontSize: 9, bold: true, color: C.accent,
      fontFace: "Calibri", margin: 0
    });
    sl.addText(ins.val, {
      x: 7.55, y: y + 0.08, w: 1.95, h: 0.28,
      fontSize: 16, bold: true, color: C.white,
      fontFace: "Calibri", align: "right", margin: 0
    });
    sl.addText(ins.desc, {
      x: 6.12, y: y + 0.42, w: 3.38, h: 0.42,
      fontSize: 8.5, color: C.light, fontFace: "Calibri",
      valign: "top", margin: 0
    });
  });
}

// ─── SLIDE 8: ADVANCED ANALYTICS ─────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Advanced Analytics");
  addSlideNum(sl, 8, TOTAL);

  const methods = [
    {
      title: "Value at Risk (VaR)",
      icon: "📊",
      points: [
        "Historical 95% VaR computed for all equity funds",
        "CVaR (Expected Shortfall) captures tail risk beyond VaR",
        "Liquid funds: VaR < 0.05% · Equity funds: 1.2%–2.3%",
        "Methodology: Historical simulation, 5th percentile of daily returns"
      ]
    },
    {
      title: "Monte Carlo Simulation",
      icon: "🎲",
      points: [
        "1,000 GBM paths · 1-year horizon · Base ₹1,00,000",
        "ICICI Equity & Debt: median FV ₹1.58L, P(profit) 79%",
        "Axis Midcap: median FV ₹1.44L with wide confidence band",
        "Models both expected returns and downside scenarios"
      ]
    },
    {
      title: "Markowitz Efficient Frontier",
      icon: "🎯",
      points: [
        "3,000 random portfolios simulated across equity universe",
        "Max-Sharpe portfolio identified (Sharpe ≈ 2.1)",
        "Min-Volatility portfolio: ~12.3% vol, ~18% return",
        "Demonstrates diversification reduces risk without proportional return loss"
      ]
    },
    {
      title: "Fund Clustering (K-Means)",
      icon: "🔍",
      points: [
        "K=4 clusters: Conservative · Balanced · Aggressive · High-Alpha",
        "Features: CAGR, vol, Sharpe, beta, alpha, max drawdown",
        "Cluster analysis aids investor profiling and fund selection",
        "Elbow method confirmed k=4 as optimal cluster count"
      ]
    },
  ];

  methods.forEach((m, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.35 + col * 4.85, y = 1.02 + row * 2.2;
    sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x, y, w: 4.6, h: 2.08,
      fill: { color: "0D1B2A" }, line: { color: C.teal, width: 0.8 }, rectRadius: 0.07
    });
    sl.addShape(prs.shapes.RECTANGLE, {
      x, y, w: 4.6, h: 0.42,
      fill: { color: C.teal }, line: { color: C.teal }
    });
    sl.addText(m.icon + "  " + m.title, {
      x: x + 0.12, y: y + 0.06, w: 4.36, h: 0.32,
      fontSize: 11, bold: true, color: C.white,
      fontFace: "Calibri", valign: "middle", margin: 0
    });
    m.points.forEach((pt, pi) => {
      sl.addText("▸  " + pt, {
        x: x + 0.15, y: y + 0.5 + pi * 0.36, w: 4.3, h: 0.34,
        fontSize: 9, color: pi === 2 ? C.accent : C.white,
        fontFace: "Calibri", valign: "top", margin: 0
      });
    });
  });
}

// ─── SLIDE 9: DASHBOARD ───────────────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Interactive Dashboard — Streamlit App (B2)");
  addSlideNum(sl, 9, TOTAL);

  const pages = [
    { num: "1", title: "Executive Summary",   desc: "KPI cards · Top/Bottom performers · Risk-return scatter · Fund snapshot table · Universe breakdown donut" },
    { num: "2", title: "Fund Performance",     desc: "NAV trend (indexed) · Rolling returns · 90d volatility · Benchmark vs Fund · Monthly return heatmap" },
    { num: "3", title: "Risk Analytics",       desc: "Volatility ranking · Drawdown history · Daily VaR comparison · Full risk metrics table" },
    { num: "4", title: "Portfolio Optimiser",  desc: "Markowitz efficient frontier · Max Sharpe weights · Min Vol weights · SIP calculator with growth chart" },
    { num: "5", title: "Fund Comparison",      desc: "Side-by-side metrics · Winner highlighting · Indexed NAV comparison · Performance radar chart" },
  ];

  sl.addText("5 fully interactive pages with slicers on every page:", {
    x: 0.4, y: 0.95, w: 9.2, h: 0.3,
    fontSize: 10, color: C.light, fontFace: "Calibri", margin: 0
  });

  pages.forEach((p, i) => {
    const y = 1.35 + i * 0.82;
    sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x: 0.4, y, w: 0.4, h: 0.58,
      fill: { color: C.accent }, line: { color: C.accent }, rectRadius: 0.05
    });
    sl.addText(p.num, {
      x: 0.4, y, w: 0.4, h: 0.58,
      fontSize: 16, bold: true, color: C.white,
      align: "center", valign: "middle", fontFace: "Calibri", margin: 0
    });
    sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x: 0.88, y, w: 8.82, h: 0.58,
      fill: { color: "12263D" }, line: { color: "1E3A5F", width: 0.4 }, rectRadius: 0.05
    });
    sl.addText(p.title, {
      x: 1.02, y: y + 0.05, w: 2.3, h: 0.25,
      fontSize: 10.5, bold: true, color: C.white,
      fontFace: "Calibri", valign: "top", margin: 0
    });
    sl.addText(p.desc, {
      x: 1.02, y: y + 0.3, w: 8.5, h: 0.24,
      fontSize: 8.5, color: C.grey,
      fontFace: "Calibri", valign: "top", margin: 0
    });
  });

  sl.addText("Run: streamlit run source_code/streamlit_app/app.py  →  localhost:8501", {
    x: 0.4, y: 5.35, w: 9.2, h: 0.2,
    fontSize: 8.5, color: C.accent, fontFace: "Calibri", italic: true, margin: 0
  });
}

// ─── SLIDE 10: CATEGORY PERFORMANCE ─────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Category Performance — CAGR Across Periods");
  addSlideNum(sl, 10, TOTAL);

  // Grouped bar chart (visual)
  sl.addText("Average CAGR % by Sub-Category", {
    x: 0.4, y: 0.95, w: 9.2, h: 0.3,
    fontSize: 10, bold: true, color: C.accent, fontFace: "Calibri", margin: 0
  });

  const sortedCat = [...CAT_AVG].sort((a, b) => b.cagr_1y - a.cagr_1y);
  const maxC = 70, bX = 2.5, bMaxW = 6.5, catBarH = 0.28, catGap = 0.12;
  const periods = [
    { key: "cagr_1y", color: C.accent, label: "1Y" },
    { key: "cagr_3y", color: C.green,  label: "3Y" },
    { key: "cagr_5y", color: C.amber,  label: "5Y" },
  ];

  sortedCat.forEach((c, i) => {
    const baseY = 1.35 + i * (catBarH * 3 + catGap + 0.1);
    sl.addText(c.cat, {
      x: 0.35, y: baseY, w: 2.1, h: catBarH * 3 + 0.08,
      fontSize: 8, color: C.white, align: "right",
      fontFace: "Calibri", valign: "middle", margin: 0
    });
    periods.forEach((p, pi) => {
      const y = baseY + pi * (catBarH + 0.01);
      const val = c[p.key];
      const fw  = Math.max(0, (val / maxC)) * bMaxW;
      sl.addShape(prs.shapes.RECTANGLE, {
        x: bX, y, w: bMaxW, h: catBarH,
        fill: { color: "1A2E44" }, line: { color: "1A2E44" }
      });
      if (fw > 0.02) {
        sl.addShape(prs.shapes.RECTANGLE, {
          x: bX, y, w: fw, h: catBarH,
          fill: { color: p.color }, line: { color: p.color }
        });
      }
      sl.addText(`${p.label}: ${val.toFixed(1)}%`, {
        x: bX + fw + 0.06, y: y - 0.01, w: 1.3, h: catBarH + 0.02,
        fontSize: 7.5, color: p.color,
        fontFace: "Calibri", valign: "middle", margin: 0
      });
    });
  });
}

// ─── SLIDE 11: KEY INSIGHTS ───────────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Key Insights & Recommendations");
  addSlideNum(sl, 11, TOTAL);

  const insightCards = [
    { color: C.green,  title: "🏆 Best Return",       body: "ICICI Pru Equity & Debt Fund — 63.7% 1Y CAGR with Sharpe of 4.05. Aggressive Hybrid category outperformed all equity sub-categories on risk-adjusted basis." },
    { color: C.accent, title: "📊 Index Funds Win",    body: "Large Cap Index funds (Sharpe >1.0) outperformed majority of active large-cap funds — lower expense ratios compound the advantage over time." },
    { color: C.amber,  title: "⚖️ Risk-Return Law",   body: "Mid/Small Cap funds: highest CAGR (23–27%) but worst drawdowns (18–37%). Debt/Liquid funds: 4–10% CAGR but near-zero risk. No free lunch exists." },
    { color: C.red,    title: "⚠️ Inconsistency Risk", body: "HDFC Mid-Cap: -16.8% 1Y but +25% 3Y CAGR. Short-term performance is not predictive. Rolling CAGR consistency matters more than point-in-time returns." },
    { color: C.green,  title: "💡 For Conservative",  body: "Liquid + Corporate Bond funds (4–10% CAGR, Sharpe >0.9). HDFC Liquid and Mirae Asset Cash Management for sub-1-year horizons." },
    { color: C.accent, title: "🚀 For Aggressive",    body: "Mid Cap + Small Cap + Aggressive Hybrid for 5Y+ horizon. Accept 20–30% drawdowns. SBI Small Cap: 27% 5Y CAGR despite weak 1Y performance." },
  ];

  insightCards.forEach((card, i) => {
    const col = i % 3, row = Math.floor(i / 2);
    const x = 0.35 + col * 3.2, y = 1.0 + row * 2.25;
    sl.addShape(prs.shapes.ROUNDED_RECTANGLE, {
      x, y, w: 3.05, h: 2.1,
      fill: { color: "0D1B2A" }, line: { color: card.color, width: 1.2 }, rectRadius: 0.07
    });
    sl.addShape(prs.shapes.RECTANGLE, {
      x, y, w: 3.05, h: 0.45,
      fill: { color: card.color }, line: { color: card.color }
    });
    sl.addText(card.title, {
      x: x + 0.1, y: y + 0.07, w: 2.85, h: 0.32,
      fontSize: 10.5, bold: true, color: C.white,
      fontFace: "Calibri", valign: "middle", margin: 0
    });
    sl.addText(card.body, {
      x: x + 0.1, y: y + 0.52, w: 2.85, h: 1.48,
      fontSize: 9, color: C.white,
      fontFace: "Calibri", valign: "top", margin: 0
    });
  });
}

// ─── SLIDE 12: TECHNICAL SUMMARY ─────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Technical Stack & Deliverables");
  addSlideNum(sl, 12, TOTAL);

  // Left: tech stack
  sl.addText("Technology Stack", {
    x: 0.4, y: 0.95, w: 4.8, h: 0.3,
    fontSize: 11, bold: true, color: C.accent, fontFace: "Calibri", margin: 0
  });
  const tech = [
    ["Python 3.10+", "Core language"],
    ["pandas / numpy", "Data processing"],
    ["scipy", "Statistics & optimisation"],
    ["SQLite (WAL mode)", "Database — 8 tables, 6 views"],
    ["Streamlit + Plotly", "Interactive dashboard"],
    ["Jupyter Lab", "Analytical notebooks"],
    ["ReportLab", "PDF report generation"],
    ["PptxGenJS", "Presentation slides"],
    ["schedule / APScheduler", "ETL automation"],
    ["pytest (31 tests)", "Unit testing — all passing"],
  ];
  tech.forEach(([tool, desc], i) => {
    const y = 1.32 + i * 0.38;
    const bg = i % 2 === 0 ? "121E2E" : "162438";
    sl.addShape(prs.shapes.RECTANGLE, {
      x: 0.4, y, w: 5.0, h: 0.36,
      fill: { color: bg }, line: { color: "1E3A5F", width: 0.3 }
    });
    sl.addText(tool, {
      x: 0.5, y: y + 0.04, w: 2.2, h: 0.28,
      fontSize: 8.5, bold: true, color: C.accent,
      fontFace: "Calibri", valign: "middle", margin: 0
    });
    sl.addText(desc, {
      x: 2.75, y: y + 0.04, w: 2.6, h: 0.28,
      fontSize: 8.5, color: C.white,
      fontFace: "Calibri", valign: "middle", margin: 0
    });
  });

  // Right: deliverables checklist
  sl.addText("Deliverables", {
    x: 5.7, y: 0.95, w: 4.0, h: 0.3,
    fontSize: 11, bold: true, color: C.accent, fontFace: "Calibri", margin: 0
  });
  const delivs = [
    ["D1","ETL Pipeline (.py)","✅"],
    ["D2","SQLite Database (.db)","✅"],
    ["D3","EDA Notebook (.ipynb)","✅"],
    ["D4","Performance Metrics (.ipynb + CSV)","✅"],
    ["D5","Dashboard (Streamlit + Power BI guide)","✅"],
    ["D6","Advanced Analytics (.ipynb)","✅"],
    ["D7","Final Report (.pdf) + Slides (.pptx)","✅"],
    ["B1","Automated ETL Scheduling","✅"],
    ["B2","Streamlit Web App","✅"],
    ["B3","Monte Carlo Simulation","✅"],
    ["B4","Markowitz Optimisation","✅"],
  ];
  delivs.forEach(([id, label, status], i) => {
    const y = 1.32 + i * 0.38;
    const bg = i % 2 === 0 ? "121E2E" : "162438";
    sl.addShape(prs.shapes.RECTANGLE, {
      x: 5.7, y, w: 4.0, h: 0.36,
      fill: { color: bg }, line: { color: "1E3A5F", width: 0.3 }
    });
    sl.addText(id, {
      x: 5.75, y: y + 0.04, w: 0.38, h: 0.28,
      fontSize: 8, bold: true, color: C.accent,
      fontFace: "Calibri", valign: "middle", align: "center", margin: 0
    });
    sl.addText(label, {
      x: 6.18, y: y + 0.04, w: 2.9, h: 0.28,
      fontSize: 8, color: C.white,
      fontFace: "Calibri", valign: "middle", margin: 0
    });
    sl.addText(status, {
      x: 9.1, y: y + 0.04, w: 0.45, h: 0.28,
      fontSize: 10, color: C.green,
      fontFace: "Calibri", valign: "middle", align: "center", margin: 0
    });
  });
}

// ─── SLIDE 13: LIMITATIONS ───────────────────────────────────────────────────
{
  const sl = darkSlide(prs);
  addSectionTitle(sl, "Limitations & Future Enhancements");
  addSlideNum(sl, 13, TOTAL);

  sl.addText("Current Limitations", {
    x: 0.4, y: 0.95, w: 4.6, h: 0.3,
    fontSize: 11, bold: true, color: C.red, fontFace: "Calibri", margin: 0
  });
  const limits = [
    "Past performance does not guarantee future returns",
    "5-year window includes post-COVID recovery rally (may inflate CAGR)",
    "Benchmark matching uses stated benchmark, not actual fund exposure",
    "Expense ratios missing for some funds — net return comparisons affected",
    "Synthetic benchmark data uses GBM approximation for some indices",
    "19-fund universe is illustrative — full AMFI list has 2,000+ schemes",
  ];
  limits.forEach((l, i) => {
    sl.addText("⚠  " + l, {
      x: 0.5, y: 1.32 + i * 0.48, w: 4.6, h: 0.42,
      fontSize: 9.5, color: C.white, fontFace: "Calibri",
      valign: "top", margin: 0
    });
  });

  sl.addText("Future Enhancements", {
    x: 5.5, y: 0.95, w: 4.2, h: 0.3,
    fontSize: 11, bold: true, color: C.green, fontFace: "Calibri", margin: 0
  });
  const futures = [
    "Expand to 500+ fund universe (full AMFI scheme list)",
    "XIRR-based SIP return analysis for periodic investments",
    "AUM-weighted return calculations for market-cap perspective",
    "Bull/bear regime detection for conditional performance analysis",
    "Collaborative filtering fund recommendation engine",
    "Deploy Streamlit app on cloud (Streamlit Cloud / AWS EC2)",
    "Real-time NAV updates via scheduled API polling",
    "Automated HTML email reports (B5 bonus deliverable)",
  ];
  futures.forEach((f, i) => {
    sl.addText("✦  " + f, {
      x: 5.6, y: 1.32 + i * 0.48, w: 4.1, h: 0.42,
      fontSize: 9.5, color: C.white, fontFace: "Calibri",
      valign: "top", margin: 0
    });
  });
}

// ─── SLIDE 14: CLOSING ────────────────────────────────────────────────────────
{
  const sl = navySlide(prs);

  sl.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: 0, w: W, h: 1.5,
    fill: { color: C.teal }, line: { color: C.teal }
  });
  sl.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: H - 1.2, w: W, h: 1.2,
    fill: { color: C.accent }, line: { color: C.accent }
  });
  sl.addShape(prs.shapes.OVAL, {
    x: 6.5, y: 1.0, w: 4.5, h: 4.5,
    fill: { color: "FFFFFF08" }, line: { color: "FFFFFF12", width: 1 }
  });

  sl.addText("Thank You", {
    x: 0.6, y: 1.7, w: 8.8, h: 1.0,
    fontSize: 44, bold: true, color: C.white,
    fontFace: "Calibri", margin: 0
  });
  sl.addText("Bluestock Mutual Fund Analytics Capstone", {
    x: 0.6, y: 2.75, w: 8.8, h: 0.5,
    fontSize: 16, color: C.light, fontFace: "Calibri", margin: 0
  });

  sl.addShape(prs.shapes.LINE, {
    x: 0.6, y: 3.42, w: 5.0, h: 0,
    line: { color: C.accent, width: 1.5 }
  });

  const bullets = [
    "📊  19 Funds  ·  70,797 NAV Records  ·  5 Years  ·  15 Metrics per Fund",
    "🔧  D1–D7 Complete  ·  B1 B2 B3 B4 Bonus Delivered  ·  31 Tests Passing",
    "🌐  Data Source: AMFI India via mfapi.in  ·  Bluestock Analytics Team · 2025",
  ];
  bullets.forEach((b, i) => {
    sl.addText(b, {
      x: 0.6, y: 3.6 + i * 0.38, w: 8.8, h: 0.35,
      fontSize: 10, color: C.light, fontFace: "Calibri", margin: 0
    });
  });

  sl.addText("Questions & Discussion", {
    x: 0, y: H - 1.0, w: W, h: 0.65,
    fontSize: 14, bold: true, color: C.white,
    align: "center", valign: "middle", fontFace: "Calibri", margin: 0
  });
}

// ─── WRITE FILE ───────────────────────────────────────────────────────────────
const outPath = "/home/claude/bluestock_mf_capstone/ppt_slides/Final_Presentation.pptx";
prs.writeFile({ fileName: outPath }).then(() => {
  console.log(`Saved: ${outPath}`);
}).catch(err => {
  console.error("Error:", err);
});
