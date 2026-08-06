const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";              // 13.3 x 7.5
pres.author = "mohammed alshaigi";
pres.title = "Hajj & Tourism Crowd Operations Data Platform";

// ---- palette: deep green + sand + gold, chosen for the Saudi crowd-safety domain
const INK   = "0A2E24";   // near-black green  (dark slide bg)
const DEEP  = "12513C";   // primary green
const MID   = "2E7D5B";   // supporting green
const SAND  = "F4EFE4";   // light bg
const CARD  = "FFFFFF";
const GOLD  = "C8A951";   // accent
const RED   = "B4453C";   // failure / rejection
const MUTED = "6B7B74";
const WHITE = "FFFFFF";

const HFONT = "Cambria";   // headers
const BFONT = "Calibri";   // body

// ---------- helpers ----------
function darkSlide() {
  const s = pres.addSlide();
  s.background = { color: INK };
  return s;
}
function lightSlide(title, kicker) {
  const s = pres.addSlide();
  s.background = { color: SAND };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: 0.6, y: 0.36, w: 12.1, h: 0.28, fontFace: BFONT, fontSize: 11,
      bold: true, color: GOLD, charSpacing: 2, margin: 0,
    });
  }
  s.addText(title, {
    x: 0.6, y: kicker ? 0.64 : 0.5, w: 12.1, h: 0.7,
    fontFace: HFONT, fontSize: 34, bold: true, color: DEEP, margin: 0,
  });
  return s;
}
function card(s, x, y, w, h, fill) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, fill: { color: fill || CARD }, rectRadius: 0.09,
    line: { color: fill || CARD, width: 0 },
    shadow: { type: "outer", angle: 90, blur: 10, offset: 1.5, color: "1A1A1A", opacity: 0.10 },
  });
}
function iconDot(s, x, y, label, bg, fg) {
  s.addShape(pres.ShapeType.ellipse, {
    x, y, w: 0.44, h: 0.44, fill: { color: bg || DEEP }, line: { color: bg || DEEP, width: 0 },
  });
  s.addText(label, {
    x, y, w: 0.44, h: 0.44, align: "center", valign: "middle",
    fontFace: BFONT, fontSize: 13, bold: true, color: fg || WHITE, margin: 0,
  });
}
function stat(s, x, y, w, value, label, color) {
  s.addText(value, {
    x, y, w, h: 0.72, fontFace: HFONT, fontSize: 40, bold: true,
    color: color || DEEP, margin: 0, align: "left",
  });
  s.addText(label, {
    x, y: y + 0.72, w, h: 0.46, fontFace: BFONT, fontSize: 11.5,
    color: MUTED, margin: 0, align: "left",
  });
}
function bullets(s, x, y, w, items, size) {
  s.addText(
    items.map((t, i) => ({
      text: t, options: { bullet: true, breakLine: i !== items.length - 1 },
    })),
    { x, y, w, h: 0.4 * items.length + 0.3, fontFace: BFONT, fontSize: size || 13.5,
      color: "27352F", paraSpaceAfter: 7, margin: 0, lineSpacing: 19 }
  );
}

// =====================================================================
// 1 — TITLE
// =====================================================================
{
  const s = darkSlide();
  s.addShape(pres.ShapeType.ellipse, {
    x: 9.4, y: -1.5, w: 5.6, h: 5.6, fill: { color: DEEP }, line: { width: 0 },
  });
  s.addShape(pres.ShapeType.ellipse, {
    x: 10.9, y: 3.6, w: 3.4, h: 3.4, fill: { color: MID }, line: { width: 0 },
  });
  s.addText("SDAIA ACADEMY  ·  CAPSTONE PROJECT", {
    x: 0.75, y: 1.5, w: 8.6, h: 0.3, fontFace: BFONT, fontSize: 12,
    bold: true, color: GOLD, charSpacing: 2.5, margin: 0,
  });
  s.addText("Hajj & Tourism\nCrowd Operations\nData Platform", {
    x: 0.75, y: 2.0, w: 8.8, h: 2.5, fontFace: HFONT, fontSize: 44,
    bold: true, color: WHITE, lineSpacing: 46, margin: 0,
  });
  s.addText("Real-time crowd telemetry from Kafka to a Delta lakehouse, gated by automated quality checks, with a retrieval copilot that answers procedural questions from official standard operating procedures — with citations.", {
    x: 0.78, y: 4.75, w: 8.4, h: 1.0, fontFace: BFONT, fontSize: 13.5,
    color: "BFD3C8", margin: 0, lineSpacing: 20,
  });
  s.addText("mohammed alshaigi   ·   github.com/Mohammed-07th", {
    x: 0.78, y: 6.15, w: 8.4, h: 0.3, fontFace: BFONT, fontSize: 12.5, bold: true, color: WHITE, margin: 0,
  });
  s.addText("Modern Data Engineering for AI Systems  ·  Cohort 2–6 August 2026  ·  Trainer: Mohammed Albeladi", {
    x: 0.78, y: 6.5, w: 9.0, h: 0.3, fontFace: BFONT, fontSize: 10.5, color: MUTED, margin: 0,
  });
  s.addNotes("Open with the 30-second pitch, then immediately state that all operational data is synthetic.");
}

// =====================================================================
// 2 — THE PROBLEM
// =====================================================================
{
  const s = lightSlide("A duty officer at 2am needs an answer, not a search", "The problem");
  card(s, 0.6, 1.7, 6.0, 4.3);
  s.addText("What happens on the ground", {
    x: 0.95, y: 1.95, w: 5.3, h: 0.35, fontFace: BFONT, fontSize: 15, bold: true, color: DEEP, margin: 0,
  });
  bullets(s, 0.95, 2.4, 5.35, [
    "Gate sensors report entries, exits and estimated occupancy for every zone, every few seconds.",
    "Field staff raise service requests — medical, lost person, crowd pressure, water, security — that move through a lifecycle over minutes to hours.",
    "Zones include the Mataf, the Mas'a, the Jamarat bridge levels, Mina camps, Arafat, Muzdalifah, plus AlUla and Diriyah year-round.",
  ]);

  card(s, 7.0, 1.7, 5.7, 4.3, DEEP);
  s.addText("The moment that defines the product", {
    x: 7.35, y: 1.95, w: 5.0, h: 0.35, fontFace: BFONT, fontSize: 15, bold: true, color: GOLD, margin: 0,
  });
  s.addText("“MATAF_01 has been above 90% capacity for 12 minutes.\n\nWho authorises diversion? What is the medical response SLA? What must I do first?”", {
    x: 7.35, y: 2.45, w: 5.0, h: 1.9, fontFace: HFONT, fontSize: 17, italic: true,
    color: WHITE, margin: 0, lineSpacing: 25,
  });
  s.addText("The answer must come from the actual published procedure, with a citation the officer can verify — not from memory, not from a colleague, and not invented by a language model.", {
    x: 7.35, y: 4.5, w: 5.0, h: 1.3, fontFace: BFONT, fontSize: 13, color: "BFD3C8", margin: 0, lineSpacing: 19,
  });
  s.addNotes("The citation is the point: it makes the answer checkable.");
}

// =====================================================================
// 3 — WHO USES IT
// =====================================================================
{
  const s = lightSlide("Four roles, four different questions", "Who uses it");
  const users = [
    ["1", "Duty Operations Director", "Site-wide authority. Needs the daily picture: which zones ran hot, for how long, and where SLAs were breached.", "Gold tables + briefing metrics"],
    ["2", "SOC Controller", "Real-time zone control. Authorises diversion at the CRITICAL threshold. Needs current occupancy and the escalation ladder.", "Live occupancy + copilot"],
    ["3", "Sector Supervisor / Zone Marshal", "On the floor. Needs a procedural answer in seconds, in their own language, while a crowd builds.", "Copilot, Arabic and English"],
    ["4", "Data & analytics team", "Needs trustworthy history to model against — and needs to know when it cannot be trusted.", "Lakehouse + quality gates"],
  ];
  let y = 1.72;
  users.forEach(([n, role, need, uses]) => {
    card(s, 0.6, y, 12.1, 1.12);
    iconDot(s, 0.92, y + 0.33, n, DEEP);
    s.addText(role, { x: 1.55, y: y + 0.18, w: 3.5, h: 0.3, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
    s.addText(need, { x: 1.55, y: y + 0.5, w: 7.5, h: 0.55, fontFace: BFONT, fontSize: 11.5, color: "3D4A44", margin: 0, lineSpacing: 15 });
    s.addText(uses, { x: 9.3, y: y + 0.38, w: 3.1, h: 0.45, fontFace: BFONT, fontSize: 11, bold: true, color: MID, margin: 0, align: "right" });
    y += 1.22;
  });
  s.addNotes("Point out that the copilot and the lakehouse serve different roles — that is why the project has both halves.");
}

// =====================================================================
// 4 — WHAT IT DOES
// =====================================================================
{
  const s = lightSlide("Two halves of one platform", "What it does");
  card(s, 0.6, 1.75, 6.0, 4.4);
  iconDot(s, 0.95, 2.05, "A", MID);
  s.addText("The lakehouse", { x: 1.55, y: 2.08, w: 4.5, h: 0.4, fontFace: HFONT, fontSize: 21, bold: true, color: DEEP, margin: 0 });
  s.addText("Turns raw telemetry into answerable questions", { x: 0.95, y: 2.62, w: 5.3, h: 0.3, fontFace: BFONT, fontSize: 12, italic: true, color: MUTED, margin: 0 });
  bullets(s, 0.95, 3.05, 5.35, [
    "Every sensor reading and every request state change is captured and validated.",
    "Bad records are quarantined with a reason, never silently dropped.",
    "Aggregates answer questions no single reading can: “how many minutes did MATAF_01 spend above 90% yesterday?”",
  ], 12.5);

  card(s, 7.0, 1.75, 5.7, 4.4);
  iconDot(s, 7.35, 2.05, "B", GOLD, INK);
  s.addText("The copilot", { x: 7.95, y: 2.08, w: 4.3, h: 0.4, fontFace: HFONT, fontSize: 21, bold: true, color: DEEP, margin: 0 });
  s.addText("Answers procedure, with citations", { x: 7.35, y: 2.62, w: 5.0, h: 0.3, fontFace: BFONT, fontSize: 12, italic: true, color: MUTED, margin: 0 });
  bullets(s, 7.35, 3.05, 5.05, [
    "Searches 10 standard operating procedures by meaning and by exact keyword.",
    "Cites the document code and section for every claim it makes.",
    "Refuses when the procedures do not cover the question, instead of inventing an answer.",
    "Works in Arabic and English.",
  ], 12.5);
  s.addNotes("Half A is Deliverables 1, 2, 4, 5. Half B is Deliverable 3.");
}

// =====================================================================
// 5 — ARCHITECTURE
// =====================================================================
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("HOW THE DATA FLOWS", { x: 0.6, y: 0.4, w: 12, h: 0.3, fontFace: BFONT, fontSize: 11, bold: true, color: GOLD, charSpacing: 2, margin: 0 });
  s.addText("Architecture", { x: 0.6, y: 0.68, w: 12, h: 0.6, fontFace: HFONT, fontSize: 32, bold: true, color: WHITE, margin: 0 });

  const box = (x, y, w, h, title, sub, fill, tcol) => {
    s.addShape(pres.ShapeType.roundRect, {
      x, y, w, h, fill: { color: fill }, rectRadius: 0.08, line: { color: fill, width: 0 },
    });
    s.addText(title, { x: x + 0.12, y: y + 0.1, w: w - 0.24, h: 0.3, fontFace: BFONT, fontSize: 12.5, bold: true, color: tcol, align: "center", margin: 0 });
    if (sub) s.addText(sub, { x: x + 0.12, y: y + 0.42, w: w - 0.24, h: 0.5, fontFace: BFONT, fontSize: 9.5, color: tcol, align: "center", margin: 0, lineSpacing: 12 });
  };
  const arrow = (x, y, w) => s.addShape(pres.ShapeType.rightArrow, {
    x, y, w, h: 0.22, fill: { color: GOLD }, line: { color: GOLD, width: 0 },
  });

  box(0.6, 1.7, 2.1, 1.0, "2 Producers", "occupancy +\nservice requests", MID, WHITE);
  arrow(2.78, 2.09, 0.4);
  box(3.28, 1.7, 2.1, 1.0, "Kafka", "4 topics, KRaft", DEEP, WHITE);
  arrow(5.46, 2.09, 0.4);
  box(5.96, 1.7, 2.3, 1.0, "Pydantic contract", "strict validation\nat the boundary", GOLD, INK);
  arrow(8.34, 2.09, 0.4);
  box(8.84, 1.28, 1.9, 0.82, "BRONZE", "raw, append-only", "1D6A4F", WHITE);
  box(8.84, 2.30, 1.9, 0.82, "DLQ + quarantine", "with reason", RED, WHITE);

  // gate 1
  box(0.6, 3.35, 2.1, 0.75, "GATE 1", "Great Expectations", "8A6D1F", WHITE);
  arrow(2.78, 3.62, 0.4);
  box(3.28, 3.35, 2.6, 0.75, "SILVER", "dedupe · MERGE · PII hashed", "1D6A4F", WHITE);
  arrow(5.98, 3.62, 0.4);
  box(6.48, 3.35, 1.9, 0.75, "GATE 2", "Great Expectations", "8A6D1F", WHITE);
  arrow(8.46, 3.62, 0.4);
  box(8.96, 3.35, 1.8, 0.75, "GOLD", "GROUP BY aggregate", "1D6A4F", WHITE);

  box(0.6, 4.5, 3.2, 0.85, "10 SOP documents", "chunk → embed", MID, WHITE);
  arrow(3.88, 4.85, 0.4);
  box(4.38, 4.5, 2.2, 0.85, "Qdrant + BM25", "vector + keyword", DEEP, WHITE);
  arrow(6.66, 4.85, 0.4);
  box(7.16, 4.5, 1.9, 0.85, "RRF fusion", "k = 60", GOLD, INK);
  arrow(9.14, 4.85, 0.4);
  box(9.64, 4.5, 2.0, 0.85, "Rerank → answer", "with citations", MID, WHITE);

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 5.65, w: 12.1, h: 0.75, fill: { color: "133B2E" }, rectRadius: 0.08, line: { color: "133B2E", width: 0 },
  });
  s.addText("Airflow orchestrates all 13 tasks  ·  OpenLineage emits START / COMPLETE / FAIL for every stage  ·  a failed gate stops everything downstream", {
    x: 0.8, y: 5.85, w: 11.7, h: 0.4, fontFace: BFONT, fontSize: 12.5, color: WHITE, align: "center", margin: 0,
  });
  s.addNotes("Trace the arrows left to right, then point at the two gates.");
}

// =====================================================================
// 6 — THE STACK
// =====================================================================
{
  const s = lightSlide("Every component is the real library", "What we used");
  const groups = [
    ["Ingestion", ["confluent-kafka 2.5.0", "Apache Kafka 3.8.1 (KRaft)", "Pydantic v2 — strict mode", "Docker via colima"]],
    ["Lakehouse", ["deltalake 0.20.2 (delta-rs)", "polars 1.9.0", "pyarrow 17.0.0", "no JVM in the stack"]],
    ["Quality & lineage", ["great-expectations 0.18.22", "openlineage-python 1.22.0", "pytest — 44 tests"]],
    ["RAG", ["Qdrant 1.11.3 (Docker)", "multilingual-e5-small (384d)", "rank-bm25 + hand-written RRF", "cross-encoder reranker", "OpenRouter via openai SDK"]],
    ["Orchestration", ["apache-airflow 2.10.5", "13-task DAG, host install", "SequentialExecutor"]],
    ["Discipline", ["anti-substitution audit script", "65-check rubric self-check", "48 incremental commits"]],
  ];
  let x = 0.6, y = 1.72;
  groups.forEach((g, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const cx = 0.6 + col * 4.12, cy = 1.72 + row * 2.35;
    card(s, cx, cy, 3.85, 2.15);
    s.addText(g[0], { x: cx + 0.28, y: cy + 0.22, w: 3.3, h: 0.32, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
    s.addText(g[1].map((t, j) => ({ text: t, options: { bullet: true, breakLine: j !== g[1].length - 1 } })), {
      x: cx + 0.28, y: cy + 0.62, w: 3.3, h: 1.4, fontFace: BFONT, fontSize: 11, color: "3D4A44", margin: 0, paraSpaceAfter: 4, lineSpacing: 15,
    });
  });
  s.addText("The rubric states plainly that a simulation earns nothing. An audit script runs after every phase and fails the build if a queue ever stands in for Kafka, pandas for Delta, or numpy for a vector store.", {
    x: 0.6, y: 6.5, w: 12.1, h: 0.5, fontFace: BFONT, fontSize: 12, italic: true, color: MUTED, margin: 0,
  });
}

// =====================================================================
// 7 — D1 INGESTION
// =====================================================================
{
  const s = lightSlide("Bad data is stopped at the door", "Deliverable 1 · Ingestion · 20 pts");
  card(s, 0.6, 1.72, 7.4, 2.15);
  s.addText("The data contract", { x: 0.92, y: 1.94, w: 6.8, h: 0.32, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
  s.addText("Every message is validated against a Pydantic v2 contract in strict mode before it is allowed into storage. Strict mode is the point: normally Python converts the text \"1500\" into the number 1500 without complaint. That is how corrupt data enters a warehouse wearing a valid disguise.", {
    x: 0.92, y: 2.32, w: 6.8, h: 1.3, fontFace: BFONT, fontSize: 12.5, color: "3D4A44", margin: 0, lineSpacing: 18,
  });

  card(s, 8.4, 1.72, 4.3, 2.15, DEEP);
  s.addText("Rejections go to two places", { x: 8.7, y: 1.94, w: 3.7, h: 0.32, fontFace: BFONT, fontSize: 13.5, bold: true, color: GOLD, margin: 0 });
  s.addText([
    { text: "dlq_* Kafka topic — so alerting can react in real time", options: { bullet: true, breakLine: true } },
    { text: "quarantine Delta table — so “what did we drop yesterday, by rule?” is a SQL question", options: { bullet: true, breakLine: false } },
  ], { x: 8.7, y: 2.34, w: 3.7, h: 1.3, fontFace: BFONT, fontSize: 11.5, color: WHITE, margin: 0, paraSpaceAfter: 6, lineSpacing: 15 });

  stat(s, 0.75, 4.15, 3.0, "200,000", "events produced across 7 simulated days");
  stat(s, 3.9, 4.15, 3.0, "185,843", "accepted into bronze", MID);
  stat(s, 7.0, 4.15, 3.0, "14,157", "rejected with a reason", RED);
  stat(s, 10.1, 4.15, 2.6, "10", "corruption types per stream");

  card(s, 0.6, 5.5, 12.1, 1.15, "FBF3E0");
  s.addText("The headline rejection", { x: 0.92, y: 5.66, w: 3.2, h: 0.28, fontFace: BFONT, fontSize: 12, bold: true, color: "8A6D1F", margin: 0 });
  s.addText("entries: Input should be a valid integer        ·        rule: int_type", {
    x: 0.92, y: 5.98, w: 11.5, h: 0.32, fontFace: "Courier New", fontSize: 12.5, color: INK, margin: 0,
  });
  s.addNotes("Demo step 2 lands here: 100 events, 20 malformed, 80 accepted, 20 rejected, DEMO PASSED.");
}

// =====================================================================
// 8 — D1 chart: rejections by rule
// =====================================================================
{
  const s = lightSlide("Ten injected faults, eight distinct rules", "Deliverable 1 · evidence");
  s.addChart(pres.ChartType.bar, [{
    name: "Rejected records",
    labels: ["cross-field rule", "strict type (int)", "malformed JSON", "range (>= 0)", "wrong type (str)", "invalid enum", "missing field", "extra field"],
    values: [4221, 1462, 1449, 1445, 1423, 1402, 1390, 1365],
  }], {
    x: 0.6, y: 1.75, w: 7.6, h: 4.6,
    barDir: "bar", chartColors: [DEEP],
    showTitle: true, title: "Quarantined records by the rule that caught them",
    titleFontFace: BFONT, titleFontSize: 13, titleColor: INK,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10,
    dataLabelColor: "3D4A44", dataLabelFontFace: BFONT,
    catAxisLabelColor: "3D4A44", catAxisLabelFontFace: BFONT, catAxisLabelFontSize: 11,
    valAxisLabelColor: MUTED, valAxisLabelFontFace: BFONT, valAxisLabelFontSize: 10,
    valGridLine: { color: "DDD5C4", size: 1 }, catGridLine: { style: "none" },
    showLegend: false, valAxisMaxVal: 5000,
  });
  card(s, 8.5, 1.75, 4.2, 4.6);
  s.addText("Why this matters", { x: 8.82, y: 1.98, w: 3.6, h: 0.32, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
  s.addText("Ten corruption types are injected per stream. They collapse to eight distinct rule identifiers, because several different faults violate the same rule — an unknown zone code and an impossible occupancy figure both fail as a cross-field value error, which is why that bar dominates.\n\nEvery rejected record carries a machine-readable rule identifier and a human-readable reason, plus the exact Kafka partition and offset it came from — so it can be found again on the broker.\n\nA dead-letter queue without the reason is just a second copy of the corrupt data.", {
    x: 8.82, y: 2.42, w: 3.6, h: 3.7, fontFace: BFONT, fontSize: 12, color: "3D4A44", margin: 0, lineSpacing: 18,
  });
}

// =====================================================================
// 9 — D2 LAKEHOUSE
// =====================================================================
{
  const s = lightSlide("Three layers, and a real upsert", "Deliverable 2 · Delta Lakehouse · 25 pts");
  const layers = [
    ["BRONZE", "Raw, exactly as received, never edited. Carries the Kafka topic, partition and offset that produced each row.", "185,843 readings\n11,054 request events"],
    ["SILVER", "Deduplicated, joined to reference data, PII hashed. Service requests collapsed by MERGE to current state.", "185,843 readings\n2,500 requests"],
    ["GOLD", "Aggregated by GROUP BY into one row per zone per hour, with metrics that exist nowhere upstream.", "2,688 zone-hours"],
  ];
  let x = 0.6;
  layers.forEach(([name, desc, num], i) => {
    card(s, x, 1.72, 3.9, 2.5, i === 2 ? DEEP : CARD);
    const tc = i === 2 ? WHITE : DEEP;
    s.addText(name, { x: x + 0.3, y: 1.94, w: 3.3, h: 0.34, fontFace: HFONT, fontSize: 19, bold: true, color: i === 2 ? GOLD : DEEP, margin: 0 });
    s.addText(desc, { x: x + 0.3, y: 2.38, w: 3.3, h: 1.15, fontFace: BFONT, fontSize: 11.5, color: i === 2 ? "CFE3D8" : "3D4A44", margin: 0, lineSpacing: 16 });
    s.addText(num, { x: x + 0.3, y: 3.5, w: 3.3, h: 0.6, fontFace: BFONT, fontSize: 12, bold: true, color: i === 2 ? WHITE : MID, margin: 0, lineSpacing: 16 });
    x += 4.11;
  });

  card(s, 0.6, 4.42, 6.0, 2.2, "FBF3E0");
  s.addText("The MERGE — an upsert on a business key", { x: 0.92, y: 4.62, w: 5.4, h: 0.3, fontFace: BFONT, fontSize: 13.5, bold: true, color: "8A6D1F", margin: 0 });
  s.addText("A request emits a message on every status change, so one request arrives 4–6 times. MERGE keeps one row per request_id holding its current state.", {
    x: 0.92, y: 5.0, w: 5.4, h: 0.7, fontFace: BFONT, fontSize: 12, color: "3D4A44", margin: 0, lineSpacing: 17,
  });
  s.addText("11,054 events   →   2,500 current-state rows", { x: 0.92, y: 5.85, w: 5.4, h: 0.4, fontFace: HFONT, fontSize: 17, bold: true, color: DEEP, margin: 0 });

  card(s, 6.85, 4.42, 5.85, 2.2);
  s.addText("Gold is a genuine aggregate", { x: 7.17, y: 4.62, w: 5.2, h: 0.3, fontFace: BFONT, fontSize: 13.5, bold: true, color: DEEP, margin: 0 });
  s.addText("minutes_above_90pct is the number a duty officer acts on — and it cannot be read off any single sensor reading. It only exists after grouping.", {
    x: 7.17, y: 5.0, w: 5.2, h: 0.7, fontFace: BFONT, fontSize: 12, color: "3D4A44", margin: 0, lineSpacing: 17,
  });
  s.addText("185,843 readings   →   2,688 zone-hours   ·   69 : 1", { x: 7.17, y: 5.85, w: 5.3, h: 0.4, fontFace: HFONT, fontSize: 17, bold: true, color: DEEP, margin: 0 });
  s.addNotes("Proved the MERGE updates, not just inserts: ACKNOWLEDGED went 1375 to 9, RESOLVED went 0 to 1945 across two waves.");
}

// =====================================================================
// 10 — D2 schema enforcement
// =====================================================================
{
  const s = lightSlide("A bad write is actually refused", "Deliverable 2 · proving the failure path");
  card(s, 0.6, 1.75, 6.0, 2.5, "FDF0EE");
  iconDot(s, 0.92, 2.0, "✕", RED);
  s.addText("Breaking change — REFUSED", { x: 1.52, y: 2.05, w: 4.6, h: 0.34, fontFace: BFONT, fontSize: 14, bold: true, color: RED, margin: 0 });
  s.addText("Appending a text column where the table holds integers:", { x: 0.92, y: 2.55, w: 5.4, h: 0.3, fontFace: BFONT, fontSize: 12, color: "3D4A44", margin: 0 });
  s.addText("ValueError: Schema of data\ndoes not match table schema\n  Data schema:  occupancy_estimate: string\n  Table schema: occupancy_estimate: int64", {
    x: 0.92, y: 2.92, w: 5.4, h: 1.1, fontFace: "Courier New", fontSize: 10.5, color: INK, margin: 0, lineSpacing: 15,
  });

  card(s, 6.85, 1.75, 5.85, 2.5, "EEF5F0");
  iconDot(s, 7.17, 2.0, "✓", MID);
  s.addText("Additive change — ACCEPTED", { x: 7.77, y: 2.05, w: 4.6, h: 0.34, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
  s.addText("A genuinely new column, under an explicit flag:", { x: 7.17, y: 2.55, w: 5.2, h: 0.3, fontFace: BFONT, fontSize: 12, color: "3D4A44", margin: 0 });
  s.addText("schema_mode=\"merge\"\n  → sensor_firmware_version added\n  → existing rows keep NULL\n  → no rewrite, no data loss", {
    x: 7.17, y: 2.92, w: 5.2, h: 1.1, fontFace: "Courier New", fontSize: 10.5, color: INK, margin: 0, lineSpacing: 15,
  });

  card(s, 0.6, 4.5, 12.1, 1.9, DEEP);
  s.addText("Rejecting a breaking change and accepting an additive one are the same mechanism", {
    x: 0.95, y: 4.75, w: 11.4, h: 0.35, fontFace: HFONT, fontSize: 19, bold: true, color: GOLD, margin: 0,
  });
  s.addText("Knowing the difference is the whole skill. The demo also shows that delta-rs has two write engines that behave differently — the default one silently casts the text to a number. That is the same silent-coercion failure the Pydantic contract exists to prevent, so the pipeline writes through the strict engine. Both engines are shown, so the difference is on the record rather than asserted.", {
    x: 0.95, y: 5.2, w: 11.4, h: 1.0, fontFace: BFONT, fontSize: 12.5, color: "CFE3D8", margin: 0, lineSpacing: 18,
  });
}

// =====================================================================
// 11 — D3 RAG
// =====================================================================
{
  const s = lightSlide("Finding the right paragraph, two different ways", "Deliverable 3 · RAG Pipeline · 25 pts");
  const steps = [
    ["1", "Chunk", "10 SOP documents split on their own headings, then paragraphs, then sentences — 87 chunks, 512-token ceiling."],
    ["2", "Embed", "multilingual-e5-small, 384 dimensions, run locally. Multilingual because one golden question is in Arabic."],
    ["3", "Search twice", "Qdrant finds by meaning. BM25 finds by exact keyword. Each fails where the other succeeds."],
    ["4", "Fuse with RRF", "Reciprocal Rank Fusion, k=60, written by hand. Combines positions, not scores — 0.83 and 14.2 are not comparable, but 1st and 3rd always are."],
    ["5", "Rerank", "A cross-encoder reads the question and passage together, and cuts 50 candidates to the best 5."],
    ["6", "Answer", "The model may only use the supplied passages, must cite the document code for every claim, and must refuse when they do not cover the question."],
  ];
  let y = 1.72;
  steps.forEach(([n, t, d], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const cx = 0.6 + col * 6.25, cy = 1.72 + row * 1.62;
    card(s, cx, cy, 5.95, 1.46);
    iconDot(s, cx + 0.28, cy + 0.28, n, i === 3 ? GOLD : DEEP, i === 3 ? INK : WHITE);
    s.addText(t, { x: cx + 0.88, y: cy + 0.22, w: 4.8, h: 0.3, fontFace: BFONT, fontSize: 13.5, bold: true, color: DEEP, margin: 0 });
    s.addText(d, { x: cx + 0.88, y: cy + 0.55, w: 4.85, h: 0.8, fontFace: BFONT, fontSize: 10.5, color: "3D4A44", margin: 0, lineSpacing: 14 });
  });
  s.addText("score(d)  =  Σ  1 / (k + rank of d in list i),      k = 60", {
    x: 0.6, y: 6.62, w: 12.1, h: 0.4, fontFace: "Courier New", fontSize: 14, bold: true, color: DEEP, align: "center", margin: 0,
  });
}

// =====================================================================
// 12 — D3 example
// =====================================================================
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("THE COPILOT IN ACTION", { x: 0.6, y: 0.42, w: 12, h: 0.3, fontFace: BFONT, fontSize: 11, bold: true, color: GOLD, charSpacing: 2, margin: 0 });
  s.addText("Three questions, three behaviours", { x: 0.6, y: 0.72, w: 12, h: 0.6, fontFace: HFONT, fontSize: 32, bold: true, color: WHITE, margin: 0 });

  const qa = [
    ["Q", "MATAF_01 has been above 90% for 12 minutes. Who authorizes diversion?",
     "The SOC Controller authorizes diversion. At 90% the zone is in the CRITICAL band; the authority matrix permits diversion of arriving flow at this threshold  [2, SOP-CS-011].",
     "Correct, and every claim is traceable to a document code."],
    ["ع", "ما هي إجراءات الإخلاء؟",
     "إجراءات الإخلاء: تحرك بهدوء في الاتجاه المذكور في الإعلان، واتبع تعليمات الموظفين… الإخلاء يتطلب موافقة مشتركة من مدير العمليات المناوب ومنسق الدفاع المدني  [4, SOP-CS-015].",
     "Answers in Arabic, from Arabic source passages."],
    ["!", "What is the refund policy for a cancelled Umrah booking?",
     "This is not covered in the available procedures.",
     "Refusing is the most important behaviour of all — a model that invents a plausible policy is worse than useless."],
  ];
  let y = 1.62;
  qa.forEach(([mark, q, a, note], i) => {
    s.addShape(pres.ShapeType.roundRect, {
      x: 0.6, y, w: 12.1, h: 1.62, fill: { color: i === 2 ? "3A2620" : "133B2E" }, rectRadius: 0.08,
      line: { color: i === 2 ? "3A2620" : "133B2E", width: 0 },
    });
    iconDot(s, 0.92, y + 0.24, mark, i === 2 ? RED : GOLD, i === 2 ? WHITE : INK);
    s.addText(q, { x: 1.55, y: y + 0.18, w: 10.9, h: 0.32, fontFace: BFONT, fontSize: 13, bold: true, color: WHITE, margin: 0 });
    s.addText(a, { x: 1.55, y: y + 0.55, w: 10.9, h: 0.62, fontFace: BFONT, fontSize: 11.5, color: "CFE3D8", margin: 0, lineSpacing: 15 });
    s.addText(note, { x: 1.55, y: y + 1.2, w: 10.9, h: 0.3, fontFace: BFONT, fontSize: 10.5, italic: true, color: GOLD, margin: 0 });
    y += 1.72;
  });
  s.addText("Golden question set:  9 / 9 retrieved the right document   ·   9 / 9 cited it   ·   9 / 9 contained the right fact", {
    x: 0.6, y: 6.85, w: 12.1, h: 0.35, fontFace: BFONT, fontSize: 12.5, bold: true, color: WHITE, align: "center", margin: 0,
  });
}

// =====================================================================
// 13 — D4 ORCHESTRATION / gate
// =====================================================================
{
  const s = lightSlide("When the gate fails, nothing downstream runs", "Deliverables 4 & 5 · Orchestration, Quality, Lineage · 30 pts");
  const tasks = [
    ["validate_bronze", "GATE 1 passed", "PASS"],
    ["build_silver_occupancy", "ran normally", "PASS"],
    ["build_silver_requests_merge", "ran normally", "PASS"],
    ["validate_silver", "GATE 2 FAILED", "FAIL"],
    ["build_gold_zone_hourly", "never executed", "STOP"],
    ["refresh_rag_index", "never executed", "STOP"],
    ["smoke_test_rag", "never executed", "STOP"],
  ];
  card(s, 0.6, 1.72, 6.6, 4.75);
  s.addText("A real Airflow run, with a deliberately degraded feed", {
    x: 0.92, y: 1.94, w: 6.0, h: 0.3, fontFace: BFONT, fontSize: 13, bold: true, color: DEEP, margin: 0,
  });
  let ty = 2.42;
  tasks.forEach(([name, state, kind]) => {
    const c = kind === "PASS" ? MID : kind === "FAIL" ? RED : "B8860B";
    s.addShape(pres.ShapeType.ellipse, { x: 0.95, y: ty + 0.06, w: 0.2, h: 0.2, fill: { color: c }, line: { width: 0 } });
    s.addText(name, { x: 1.28, y: ty, w: 3.5, h: 0.3, fontFace: "Courier New", fontSize: 11, color: INK, margin: 0 });
    s.addText(state, { x: 4.8, y: ty, w: 2.2, h: 0.3, fontFace: BFONT, fontSize: 11, bold: kind !== "PASS", color: c, margin: 0, align: "right" });
    ty += 0.56;
  });

  card(s, 7.45, 1.72, 5.25, 2.25, DEEP);
  s.addText("The gate genuinely gates", { x: 7.77, y: 1.94, w: 4.6, h: 0.3, fontFace: BFONT, fontSize: 13.5, bold: true, color: GOLD, margin: 0 });
  s.addText("A failing Great Expectations checkpoint raises, exits non-zero, and turns the Airflow task red. Airflow's default rule then leaves everything downstream upstream_failed. The pipeline stops rather than publishing numbers nobody should trust.", {
    x: 7.77, y: 2.34, w: 4.6, h: 1.5, fontFace: BFONT, fontSize: 11.5, color: "CFE3D8", margin: 0, lineSpacing: 16,
  });

  card(s, 7.45, 4.22, 5.25, 2.25, "FBF3E0");
  s.addText("Why a volume check, not a value check?", { x: 7.77, y: 4.44, w: 4.6, h: 0.3, fontFace: BFONT, fontSize: 13, bold: true, color: "8A6D1F", margin: 0 });
  s.addText("The contract already keeps malformed records out of bronze — they go to the dead-letter queue. So the gate never sees bad values. What it catches is a volume shortfall: far fewer rows than expected. That is the volume pillar catching an upstream incident that row-level checks structurally cannot see.", {
    x: 7.77, y: 4.84, w: 4.6, h: 1.5, fontFace: BFONT, fontSize: 11.5, color: "3D4A44", margin: 0, lineSpacing: 16,
  });
  s.addNotes("This is the strongest single moment in the demo. Show the Airflow graph live.");
}

// =====================================================================
// 14 — lineage
// =====================================================================
{
  const s = lightSlide("Every stage reports what it read and what it wrote", "Deliverable 5 · Lineage");
  card(s, 0.6, 1.75, 5.9, 2.4);
  s.addText("OpenLineage, one line per stage", { x: 0.92, y: 1.97, w: 5.3, h: 0.3, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
  s.addText("Each stage emits START before it reads, COMPLETE after it writes — with the output row count attached — and FAIL from its exception handler.\n\nIt is written as a context manager, so instrumenting a stage costs one line and required zero changes to the pipeline logic itself.", {
    x: 0.92, y: 2.4, w: 5.3, h: 1.6, fontFace: BFONT, fontSize: 12, color: "3D4A44", margin: 0, lineSpacing: 17,
  });

  card(s, 6.75, 1.75, 5.95, 2.4, DEEP);
  s.addText("Healthy run", { x: 7.07, y: 1.97, w: 2.4, h: 0.3, fontFace: BFONT, fontSize: 13, bold: true, color: GOLD, margin: 0 });
  s.addText("8 START   ·   8 COMPLETE   ·   0 FAIL", { x: 7.07, y: 2.32, w: 5.3, h: 0.35, fontFace: "Courier New", fontSize: 13, color: WHITE, margin: 0 });
  s.addText("Gate-failure run", { x: 7.07, y: 2.85, w: 2.6, h: 0.3, fontFace: BFONT, fontSize: 13, bold: true, color: GOLD, margin: 0 });
  s.addText("9 START   ·   5 COMPLETE   ·   4 FAIL", { x: 7.07, y: 3.2, w: 5.3, h: 0.35, fontFace: "Courier New", fontSize: 13, color: WHITE, margin: 0 });
  s.addText("The lineage stream alone tells you which stage broke, and why.", { x: 7.07, y: 3.62, w: 5.3, h: 0.35, fontFace: BFONT, fontSize: 11, italic: true, color: "CFE3D8", margin: 0 });

  card(s, 0.6, 4.4, 12.1, 2.05, "FBF3E0");
  s.addText("Quality suites that assert governance, not just data quality", {
    x: 0.92, y: 4.6, w: 11.5, h: 0.32, fontFace: BFONT, fontSize: 14, bold: true, color: "8A6D1F", margin: 0,
  });
  bullets(s, 0.92, 5.0, 11.5, [
    "Bronze suite — 10 expectations, including a volume pillar that catches an upstream feed drop.",
    "Silver suite — 11 expectations, including uniqueness of request_id, which proves the MERGE produced current state rather than duplicates.",
    "Two of them prove PII handling: the hash columns are populated, and the exact column set is pinned — so if a raw identifier ever reappeared, the pipeline halts.",
  ], 12);
}

// =====================================================================
// 15 — gold chart
// =====================================================================
{
  const s = lightSlide("The number a duty officer actually acts on", "Gold layer · a real result");
  s.addChart(pres.ChartType.bar, [{
    name: "Minutes above 90% capacity",
    labels: ["MUZ_Z1", "MATAF_03", "MASAA_L1", "HARAM_GATE_79", "MASAA_L2", "MATAF_02"],
    values: [299.9, 215.2, 213.7, 210.8, 203.6, 198.0],
  }], {
    x: 0.6, y: 1.75, w: 7.6, h: 4.5,
    barDir: "bar", chartColors: [GOLD],
    showTitle: true, title: "Total minutes above 90% capacity, per zone, across 7 simulated days",
    titleFontFace: BFONT, titleFontSize: 12.5, titleColor: INK,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10,
    dataLabelColor: "3D4A44", dataLabelFontFace: BFONT,
    catAxisLabelColor: "3D4A44", catAxisLabelFontFace: BFONT, catAxisLabelFontSize: 11,
    valAxisLabelColor: MUTED, valAxisLabelFontFace: BFONT, valAxisLabelFontSize: 10,
    valGridLine: { color: "DDD5C4", size: 1 }, catGridLine: { style: "none" },
    showLegend: false, valAxisMaxVal: 360,
  });
  card(s, 8.5, 1.75, 4.2, 4.5);
  s.addText("Shape, not noise", { x: 8.82, y: 1.98, w: 3.6, h: 0.32, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
  s.addText("The generator builds in prayer-time peaks, a Jamarat surge on the simulated 10th of Dhul-Hijjah, an Arafat day and a Muzdalifah overnight spike.\n\nThat shape is deliberate. A flat synthetic line would make every threshold metric zero, and the whole gold layer would look pointless in a demo.\n\nMuzdalifah tops the list because of its single overnight gathering. The Haram zones accumulate hours across the week. The tourism sites at AlUla and Diriyah never come close.", {
    x: 8.82, y: 2.42, w: 3.6, h: 3.6, fontFace: BFONT, fontSize: 11.5, color: "3D4A44", margin: 0, lineSpacing: 16,
  });
}

// =====================================================================
// 16 — HOW YOU USE IT
// =====================================================================
{
  const s = lightSlide("Six commands, from empty to proven", "How it is used");
  const cmds = [
    ["Start the infrastructure", "make up", "Kafka and Qdrant containers, health-checked, topics created."],
    ["Run the whole pipeline", "make pipeline", "Reset → produce 200k events → ingest → GATE 1 → silver + MERGE → GATE 2 → gold. About two minutes."],
    ["Orchestrate it instead", "make airflow", "Webserver and scheduler on localhost:8080. Trigger the 13-task DAG from the UI."],
    ["Ask the copilot", "make ask Q=\"…\"", "Hybrid retrieval, rerank, and a grounded answer with citations."],
    ["Prove nothing is faked", "make audit", "Fails the build if a queue ever stands in for Kafka, or pandas for Delta."],
    ["Check every requirement", "rubric_selfcheck.py", "65 checks against actual repository state — not against memory."],
  ];
  let y = 1.72;
  cmds.forEach(([t, cmd, d], i) => {
    card(s, 0.6, y, 12.1, 0.78);
    s.addText(t, { x: 0.92, y: y + 0.1, w: 2.9, h: 0.3, fontFace: BFONT, fontSize: 12.5, bold: true, color: DEEP, margin: 0 });
    s.addShape(pres.ShapeType.roundRect, {
      x: 3.85, y: y + 0.16, w: 2.75, h: 0.44, fill: { color: "E8E1D2" }, rectRadius: 0.06, line: { width: 0 },
    });
    s.addText(cmd, { x: 3.95, y: y + 0.22, w: 2.6, h: 0.32, fontFace: "Courier New", fontSize: 11.5, color: INK, margin: 0 });
    s.addText(d, { x: 6.85, y: y + 0.22, w: 5.6, h: 0.4, fontFace: BFONT, fontSize: 11, color: "3D4A44", margin: 0 });
    y += 0.86;
  });
}

// =====================================================================
// 17 — HONEST FINDINGS
// =====================================================================
{
  const s = lightSlide("Three results that contradicted expectations", "What we found");
  const finds = [
    ["The storage layer silently coerced data",
     "delta-rs has two write engines. The default one accepts the text \"1500\" into an integer column and quietly stores 1500 — no error. That is the same silent-coercion failure the ingestion contract exists to prevent, so the pipeline writes through the strict engine instead. Both are demonstrated rather than asserted."],
    ["The textbook hybrid-search demo did not reproduce",
     "Dense search was supposed to miss exact document codes that keyword search rescues. Across 31 identifiers it never missed — it found all of them in the top three, because 87 chunks is too small a corpus for that failure mode. The negative result is reported, with the reason, and the opposite direction is demonstrated instead: on paraphrases sharing no vocabulary, keyword search drops to rank 7 while dense search holds rank 1."],
    ["Rank fusion is not always an improvement",
     "On one query, dense returned the target at rank 2 and keyword at rank 4, yet the fused result placed it at rank 5. Chunks that both retrievers ranked moderately accumulate two scores and overtake one that a single retriever ranked highly. RRF optimises for consensus, and consensus is not always correctness."],
  ];
  let y = 1.72;
  finds.forEach(([t, d], i) => {
    card(s, 0.6, y, 12.1, 1.55);
    iconDot(s, 0.92, y + 0.28, String(i + 1), GOLD, INK);
    s.addText(t, { x: 1.55, y: y + 0.22, w: 10.8, h: 0.32, fontFace: BFONT, fontSize: 14, bold: true, color: DEEP, margin: 0 });
    s.addText(d, { x: 1.55, y: y + 0.6, w: 10.8, h: 0.85, fontFace: BFONT, fontSize: 11.5, color: "3D4A44", margin: 0, lineSpacing: 16 });
    y += 1.65;
  });
  s.addText("Reporting a result that did not match the expectation is the difference between an engineering project and a demo.", {
    x: 0.6, y: 6.7, w: 12.1, h: 0.35, fontFace: BFONT, fontSize: 12.5, italic: true, bold: true, color: DEEP, align: "center", margin: 0,
  });
}

// =====================================================================
// 18 — DATA HONESTY
// =====================================================================
{
  const s = darkSlide();
  s.addShape(pres.ShapeType.ellipse, { x: -1.6, y: 4.2, w: 5.0, h: 5.0, fill: { color: DEEP }, line: { width: 0 } });
  s.addText("DATA PROVENANCE", { x: 0.7, y: 0.9, w: 12, h: 0.3, fontFace: BFONT, fontSize: 11, bold: true, color: GOLD, charSpacing: 2, margin: 0 });
  s.addText("Where the data came from", { x: 0.7, y: 1.2, w: 12, h: 0.65, fontFace: HFONT, fontSize: 34, bold: true, color: WHITE, margin: 0 });
  s.addText("All operational data in this project is synthetic, generated for training purposes. Zone capacities, SLA targets and standard operating procedures are illustrative constructions and do not represent official figures or procedures of any Saudi authority.", {
    x: 0.7, y: 2.2, w: 11.6, h: 1.3, fontFace: HFONT, fontSize: 19, italic: true, color: GOLD, margin: 0, lineSpacing: 28,
  });
  const rows = [
    ["Zone and site names", "Real places"],
    ["Occupancy and service-request events", "Synthetic — generated, reproducible from a seed"],
    ["Zone capacities and SLA targets", "Illustrative, labelled as such"],
    ["SOP numeric thresholds", "Informed by public standards — Fruin density bands, ISO 7243 WBGT — and cited as that"],
  ];
  let y = 3.85;
  rows.forEach(([a, b]) => {
    s.addText(a, { x: 0.75, y, w: 4.6, h: 0.34, fontFace: BFONT, fontSize: 13, bold: true, color: WHITE, margin: 0 });
    s.addText(b, { x: 5.5, y, w: 7.1, h: 0.34, fontFace: BFONT, fontSize: 12.5, color: "BFD3C8", margin: 0 });
    y += 0.58;
  });
  s.addText("There is no public real-time Hajj crowd dataset — that telemetry is operationally sensitive. The rubric grades the pipeline, and every stage is proven with data that can be regenerated deterministically.", {
    x: 0.75, y: 6.35, w: 11.8, h: 0.6, fontFace: BFONT, fontSize: 12, color: MUTED, margin: 0, lineSpacing: 17,
  });
  s.addNotes("Say this in the first minute. Volunteered it reads as rigour; extracted under questioning it reads as concealment.");
}

// =====================================================================
// 19 — RESULTS
// =====================================================================
{
  const s = lightSlide("Everything was executed, and the output was kept", "Results & evidence");
  const stats = [
    ["185,843", "records validated into bronze", DEEP],
    ["14,157", "rejected with a recorded reason", RED],
    ["69 : 1", "gold aggregation ratio", DEEP],
    ["9 / 9", "golden questions answered and cited", MID],
    ["44", "unit tests passing", DEEP],
    ["65 / 65", "rubric self-checks passing", MID],
    ["13", "orchestrated Airflow tasks", DEEP],
    ["48", "incremental commits", DEEP],
  ];
  stats.forEach(([v, l, c], i) => {
    const col = i % 4, row = Math.floor(i / 4);
    const cx = 0.6 + col * 3.09, cy = 1.75 + row * 1.55;
    card(s, cx, cy, 2.9, 1.35);
    s.addText(v, { x: cx + 0.24, y: cy + 0.2, w: 2.5, h: 0.55, fontFace: HFONT, fontSize: 27, bold: true, color: c, margin: 0 });
    s.addText(l, { x: cx + 0.24, y: cy + 0.78, w: 2.5, h: 0.45, fontFace: BFONT, fontSize: 10.5, color: MUTED, margin: 0, lineSpacing: 13 });
  });
  card(s, 0.6, 4.95, 12.1, 1.5, DEEP);
  s.addText("Committed evidence", { x: 0.95, y: 5.15, w: 5.0, h: 0.3, fontFace: BFONT, fontSize: 13.5, bold: true, color: GOLD, margin: 0 });
  s.addText("Real terminal logs from every stage  ·  two Airflow screenshots, healthy and failed  ·  the OpenLineage event stream  ·  the golden-question run  ·  the hybrid-search and rerank proofs  ·  an executed notebook with all 14 cells' output saved", {
    x: 0.95, y: 5.55, w: 11.4, h: 0.75, fontFace: BFONT, fontSize: 12.5, color: "CFE3D8", margin: 0, lineSpacing: 18,
  });
}

// =====================================================================
// 20 — SCOPE / CLOSING
// =====================================================================
{
  const s = darkSlide();
  s.addShape(pres.ShapeType.ellipse, { x: 9.9, y: 4.4, w: 4.6, h: 4.6, fill: { color: DEEP }, line: { width: 0 } });
  s.addText("SCOPE & NEXT STEPS", { x: 0.7, y: 0.75, w: 12, h: 0.3, fontFace: BFONT, fontSize: 11, bold: true, color: GOLD, charSpacing: 2, margin: 0 });
  s.addText("Built breadth-first, in four slices", { x: 0.7, y: 1.05, w: 12, h: 0.6, fontFace: HFONT, fontSize: 32, bold: true, color: WHITE, margin: 0 });
  s.addText("A thin path through all five deliverables first, so nothing scored zero — then depth. Everything required was finished before anything optional was started.", {
    x: 0.7, y: 1.8, w: 11.4, h: 0.6, fontFace: BFONT, fontSize: 13, color: "BFD3C8", margin: 0, lineSpacing: 19,
  });

  s.addShape(pres.ShapeType.roundRect, { x: 0.7, y: 2.6, w: 5.75, h: 2.5, fill: { color: "133B2E" }, rectRadius: 0.08, line: { width: 0 } });
  s.addText("Deliberately deferred", { x: 1.0, y: 2.8, w: 5.2, h: 0.3, fontFace: BFONT, fontSize: 13.5, bold: true, color: GOLD, margin: 0 });
  s.addText([
    { text: "SCD Type 2 history table", options: { bullet: true, breakLine: true } },
    { text: "FastAPI serving layer", options: { bullet: true, breakLine: true } },
    { text: "OPTIMIZE / ZORDER tuning", options: { bullet: true, breakLine: true } },
    { text: "Live weather and prayer-time feeds", options: { bullet: true, breakLine: true } },
    { text: "Two further gold tables", options: { bullet: true, breakLine: false } },
  ], { x: 1.0, y: 3.2, w: 5.2, h: 1.7, fontFace: BFONT, fontSize: 12, color: "CFE3D8", margin: 0, paraSpaceAfter: 5, lineSpacing: 16 });

  s.addShape(pres.ShapeType.roundRect, { x: 6.85, y: 2.6, w: 5.75, h: 2.5, fill: { color: "133B2E" }, rectRadius: 0.08, line: { width: 0 } });
  s.addText("Where it would go next", { x: 7.15, y: 2.8, w: 5.2, h: 0.3, fontFace: BFONT, fontSize: 13.5, bold: true, color: GOLD, margin: 0 });
  s.addText([
    { text: "Spark for genuine Hajj-scale volume", options: { bullet: true, breakLine: true } },
    { text: "Document codes as filterable metadata, not lexical matches", options: { bullet: true, breakLine: true } },
    { text: "A multilingual reranker on larger hardware", options: { bullet: true, breakLine: true } },
    { text: "Real sensor feeds replacing the generators", options: { bullet: true, breakLine: false } },
  ], { x: 7.15, y: 3.2, w: 5.2, h: 1.7, fontFace: BFONT, fontSize: 12, color: "CFE3D8", margin: 0, paraSpaceAfter: 5, lineSpacing: 16 });

  s.addText("github.com/Mohammed-07th/hajj-crowd-ops-platform", {
    x: 0.7, y: 5.5, w: 11.6, h: 0.5, fontFace: HFONT, fontSize: 22, bold: true, color: WHITE, margin: 0,
  });
  s.addText("Completed as the capstone for Modern Data Engineering for AI Systems, SDAIA Academy, delivered via Learning Space.\nCohort 2–6 August 2026  ·  Trainer: Mohammed Albeladi  ·  github.com/SDAIAAcademy", {
    x: 0.7, y: 6.1, w: 11.6, h: 0.8, fontFace: BFONT, fontSize: 11.5, color: MUTED, margin: 0, lineSpacing: 17,
  });
}

pres.writeFile({ fileName: process.argv[2] || "capstone.pptx" }).then(f => console.log("wrote", f));
