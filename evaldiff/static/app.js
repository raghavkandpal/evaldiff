"use strict";
const $ = (id) => document.getElementById(id);
const MAX_BYTES = 50 * 1024 * 1024;

const f4 = (x) => x.toFixed(4);
// Signed 4-dp difference; anything that rounds to zero shows 0.0000.
const sgn = (x) => { const s = Math.abs(x).toFixed(4); return s === "0.0000" ? s : (x > 0 ? "+" : "-") + s; };
const fp = (p) => p === null || p === undefined ? "n/a" : p < 0.0001 ? "<0.0001" : p.toFixed(4);

async function readSide(k) {
  const file = $("file-" + k).files[0];
  if (file) {  // file input takes precedence over paste
    if (file.size > MAX_BYTES) throw new Error(k.toUpperCase() + ": file is larger than 50 MB.");
    return { name: file.name, text: await file.text() };
  }
  return { name: null, text: $("paste-" + k).value };
}

function setRows(tableId, rows, cols) {
  const tb = $(tableId).querySelector("tbody");
  tb.replaceChildren(...rows.map((r) => {
    const tr = document.createElement("tr");
    tr.dataset.id = r.id;
    for (const v of cols(r)) { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }
    return tr;
  }));
}

function showWarnings(list) {
  $("warnings").replaceChildren(...(list || []).map((w) => { const li = document.createElement("li"); li.textContent = w; return li; }));
}

const num = (id) => $(id).value.trim() === "" ? NaN : Number($(id).value);

// Show the inline settings message (on input too); returns it, "" when valid.
function validateSettings() {
  const nBoot = num("n-boot"), seed = num("seed"), threshold = num("threshold");
  let msg = "";
  if (!Number.isInteger(nBoot) || nBoot < 1000 || nBoot > 100000) msg = "Bootstrap resamples must be between 1000 and 100000";
  else if (!Number.isSafeInteger(seed)) msg = "Seed must be an integer";
  else if (!Number.isFinite(threshold)) msg = "Threshold must be a number";
  $("settings-error").textContent = msg;
  return msg;
}

// Read the settings panel; returns null when a value is invalid.
function readSettings() {
  if (validateSettings()) {  // results on screen no longer match the settings on screen
    $("results").hidden = true; $("verdict").textContent = "";
    return null;
  }
  return { alpha: Number($("alpha").value), seed: num("seed"), n_boot: num("n-boot"), threshold: num("threshold"),
           primary: $("primary-test").value, wilcoxon_zero: $("wilcoxon-zero").value };
}

function fillMapping(cols, missing) {
  $("mapping-missing").replaceChildren(...(missing || []).map((m) => { const li = document.createElement("li"); li.textContent = m; return li; }));
  for (const k of ["a", "b"]) {
    const c = cols[k];
    for (const f of ["id", "score"]) {
      const sel = $(`map-${k}-${f}`);
      sel.replaceChildren(new Option("(choose a column)", ""), ...c.columns.map((h) => new Option(h, h)));
      sel.value = c[f] || "";
    }
  }
  $("mapping").hidden = false;
}

function readMapping() {
  if ($("mapping").hidden) return null;
  const m = {};
  for (const k of ["a", "b"]) m[k] = { id: $(`map-${k}-id`).value, score: $(`map-${k}-score`).value };
  return m;
}

const hideMapping = () => { $("mapping").hidden = true; $("mapping-missing").replaceChildren(); };

const statText = (t) => t.key.startsWith("mcnemar") ? `b = ${t.b}, c = ${t.c}`
  : t.statistic === null ? "n/a" : t.key === "wilcoxon" ? String(+t.statistic.toFixed(4)) : f4(t.statistic);

function renderTests(r) {
  $("tests-table").querySelector("tbody").replaceChildren(...r.tests.map((t) => {
    const tr = document.createElement("tr");
    tr.dataset.test = t.key;
    if (t.key === r.primary) tr.className = "primary-row";
    const ci = t.ci ? `${sgn(t.ci[0])} to ${sgn(t.ci[1])}` : "";
    for (const [col, v] of [["label", t.label], ["statistic", statText(t)], ["p", fp(t.p)], ["ci", ci]]) {
      const td = document.createElement(col === "label" ? "th" : "td");
      td.dataset.col = col; td.textContent = v; tr.appendChild(td);
    }
    return tr;
  }));
}

// Flip explorer state; reset on every new result.
const ex = { rows: [], byId: new Map(), filter: "all", sort: null, cell: String };

function renderRows() {
  const q = $("search-id").value.trim().toLowerCase();
  let rows = ex.rows.filter((r) => (ex.filter === "all" || r.status === ex.filter) && r.id.toLowerCase().includes(q));
  if (ex.sort) rows = rows.slice().sort((x, y) => ex.sort === "asc" ? x.d - y.d : y.d - x.d);
  setRows("rows-table", rows, (x) => [x.id, ex.cell(x.a), ex.cell(x.b), sgn(x.d), x.status]);
  for (const tr of $("rows-table").querySelectorAll("tbody tr")) {  // the id cell is the keyboard/screen-reader control
    const td = tr.children[0], b = document.createElement("button");
    b.type = "button"; b.className = "row-btn"; b.textContent = tr.dataset.id;
    b.setAttribute("aria-label", `Show raw fields for ${tr.dataset.id}`);
    b.setAttribute("aria-controls", "row-detail");
    td.replaceChildren(b);
  }
  for (const b of document.querySelectorAll("[data-filter]")) b.setAttribute("aria-pressed", String(b.dataset.filter === ex.filter));
  $("sort-delta").parentElement.setAttribute("aria-sort", ex.sort ? (ex.sort === "asc" ? "ascending" : "descending") : "none");
}

const rawText = (rec) => Object.entries(rec).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ");

function showDetail(id, tableId = "rows-table") {
  const r = ex.byId.get(id);
  if (!r) return;
  const box = $("row-detail");
  const h = document.createElement("h4");
  h.textContent = `Row ${id} (${r.status}, Δ ${sgn(r.d)})`;
  const close = document.createElement("button");
  close.type = "button"; close.textContent = "Close";
  close.addEventListener("click", () => {  // return the user to the row they opened
    box.hidden = true;
    const tr = $(tableId).querySelector(`tbody tr[data-id="${CSS.escape(id)}"]`);
    const b = tr && tr.querySelector("button");
    if (b) { b.focus(); tr.scrollIntoView({ block: "nearest" }); }
  });
  const parts = [h];
  for (const [k, label] of [["a", "A"], ["b", "B"]]) {
    const div = document.createElement("div");
    div.className = "detail-side"; div.id = "row-detail-" + k;
    const b = document.createElement("b"); b.textContent = label;
    const ul = document.createElement("ul");
    ul.replaceChildren(...r["raw_" + k].map((rec) => { const li = document.createElement("li"); li.textContent = rawText(rec); return li; }));
    div.append(b, ul);
    parts.push(div);
  }
  parts.push(close);
  box.replaceChildren(...parts);
  box.hidden = false;
  box.focus();  // detail sits below the table; on BIG it would be 2000 rows out of view
  box.scrollIntoView({ block: "nearest" });
}

async function postJSON(url, obj) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) });
  return res.json();
}

const POWER_NOTE = "The observed difference is smaller than the minimum detectable effect at this n; " +
  "a non-significant result here is not evidence of no effect.";
let last = null, powerSeq = 0, planSeq = 0;  // seq: drop answers to requests that a newer input superseded

const SVG = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs, text) {
  const e = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}

// Inline SVG line chart of MDE against n (log x axis), with a labelled marker at the current n.
function renderChart(table) {
  const svg = $("mde-chart"), title = $("mde-chart-title");
  const pts = table.filter((t) => t.mde !== null);
  svg.replaceChildren(title);
  if (pts.length < 2) return;
  const W = 480, H = 240, L = 56, R = 16, T = 16, B = 40;
  const lx = pts.map((t) => Math.log(t.n)), x0 = Math.min(...lx), x1 = Math.max(...lx);
  const yMax = Math.max(...pts.map((t) => t.mde)) * 1.1;
  const X = (n) => L + (Math.log(n) - x0) / (x1 - x0) * (W - L - R), Y = (m) => T + (1 - m / yMax) * (H - T - B);
  svg.append(svgEl("line", { x1: L, y1: H - B, x2: W - R, y2: H - B, class: "axis" }),
             svgEl("line", { x1: L, y1: T, x2: L, y2: H - B, class: "axis" }));
  for (const v of [0, yMax / 2, yMax]) {
    svg.append(svgEl("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", class: "tick" }, v.toFixed(3)));
  }
  for (const t of pts) if (!t.current || [50, 100, 200, 500, 1000, 2000].includes(t.n)) {
    svg.append(svgEl("text", { x: X(t.n), y: H - B + 16, "text-anchor": "middle", class: "tick" }, String(t.n)));
  }
  svg.append(svgEl("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", class: "axis-label" }, "n (log scale)"),
             svgEl("text", { x: 12, y: (T + H - B) / 2, "text-anchor": "middle", class: "axis-label",
                             transform: `rotate(-90 12 ${(T + H - B) / 2})` }, "MDE"));
  svg.append(svgEl("polyline", { points: pts.map((t) => `${X(t.n)},${Y(t.mde)}`).join(" "), class: "line" }));
  for (const t of pts) {
    const c = svgEl("circle", { cx: X(t.n), cy: Y(t.mde), r: t.current ? 6 : 3.5, class: t.current ? "point current-marker" : "point" });
    c.append(svgEl("title", {}, `n = ${t.n}, MDE ${f4(t.mde)}`));
    svg.append(c);
    if (t.current) {
      const right = X(t.n) < W / 2;
      svg.append(svgEl("text", { x: X(t.n) + (right ? 10 : -10), y: Y(t.mde) - 8, "text-anchor": right ? "start" : "end",
                                 class: "current-label" }, `current (n = ${t.n})`));
    }
  }
}

const v6 = (x) => x.toFixed(6), pct = (x) => x === null ? "n/a" : (x * 100).toFixed(1) + "%";
const kfmt = (x) => String(+x.toFixed(2));
const NEEDS_J = "n/a (needs ≥2 judge runs)", NEEDS_K = "n/a (needs ≥2 trials)";

// Noise a side adds to Var(d) when run with K' trials and J' judge runs per trial.
const sideNoiseAt = (s, k, j) => (s.sg || 0) / k + (s.sj ? s.sj / (k * j) : 0);
const noiseAt = (nz, k, j) => sideNoiseAt(nz.a, k, j) + sideNoiseAt(nz.b, k, j);
// What-if K' and J' (blank or invalid: the current design); returns [K', J'].
function whatifMsg() {
  const ok = (id) => $(id).value.trim() === "" || (Number.isInteger(num(id)) && num(id) >= 1);
  return ok("whatif-k") && ok("whatif-j") ? "" : "What-if K′ and J′ must be whole numbers of at least 1";
}
function whatif(nz) {
  const bad = whatifMsg() !== "", k = num("whatif-k"), j = num("whatif-j");
  return [!bad && k >= 1 ? k : (nz.a.k + nz.b.k) / 2, !bad && j >= 1 ? j : (nz.a.j + nz.b.j) / 2];
}

function updateWhatif() {
  const nz = last && last.noise;
  if (!nz || !nz.repeated) return;
  const msg = whatifMsg();
  $("whatif-error").textContent = msg;
  const [k, j] = whatif(nz);
  $("whatif-se").textContent = msg || nz.var_d === null ? "n/a" : f4(Math.sqrt((Math.max(0, nz.omega2) + noiseAt(nz, k, j)) / last.n));
}

function renderNoise(r) {
  const nz = r.noise;
  $("noise-none").hidden = nz.repeated; $("noise-body").hidden = !nz.repeated;
  if (!nz.repeated) {  // do not leave the previous comparison's numbers in the hidden panel
    for (const e of $("noise-body").querySelectorAll("td[id], dd[id], small[id], b[id], span[id]")) e.textContent = "";  // leaf value elements only
    for (const id of ["whatif-k", "whatif-j"]) $(id).value = "";
    $("noise-warning").textContent = ""; $("noise-warning").hidden = true;
    $("unstable-table").querySelector("tbody").replaceChildren();
    return;
  }
  for (const k of ["a", "b"]) {
    const s = nz[k], nest = s.nested;
    $("k-" + k).textContent = kfmt(s.k); $("j-" + k).textContent = kfmt(s.j);
    $("sigma2-" + k).textContent = nest ? "n/a (judge runs present)" : s.sg === null ? NEEDS_K : v6(s.sg);
    $("sigmaj-" + k).textContent = s.sj === null ? NEEDS_J : v6(s.sj);
    $("sigmag-" + k).textContent = s.sg === null ? NEEDS_K : nest ? v6(s.sg) : "n/a (no judge runs)";
    $("judge-disagree-" + k).textContent = s.disagree === null ? NEEDS_J : pct(s.disagree);
    $("judge-disagree-count-" + k).textContent = s.disagree === null ? "" : `(${s.disagree_n} of ${s.disagree_cells})`;
  }
  const nest = nz.a.nested || nz.b.nested;
  const noGen = nz.a.sg === null && nz.b.sg === null, noJudge = nz.a.sj === null && nz.b.sj === null;
  $("var-d-noise").textContent = nz.var_d === null ? "n/a" : v6(nz.var_d);
  $("noise-share").textContent = nest ? "n/a" : pct(nz.noise_share);
  $("gen-share").textContent = !nest ? "n/a" : noGen ? NEEDS_K : pct(nz.gen_share);
  $("judge-share").textContent = !nest ? "n/a" : noJudge ? NEEDS_J : pct(nz.judge_share);
  $("signal-share").textContent = pct(nz.signal_share);
  $("omega2").textContent = nz.omega2 === null ? "n/a" : v6(Math.max(0, nz.omega2));  // clamped, like the signal share
  $("noise-warning").hidden = !nz.warning; $("noise-warning").textContent = nz.warning;
  $("whatif-k").value = Math.max(1, Math.round((nz.a.k + nz.b.k) / 2));
  $("whatif-j").value = Math.max(1, Math.round((nz.a.j + nz.b.j) / 2));
  setRows("unstable-table", nz.unstable, (x) => [x.id, x.a.toFixed(2), x.b.toFixed(2)]);
  for (const tr of $("unstable-table").querySelectorAll("tbody tr")) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "row-btn"; b.textContent = tr.dataset.id;
    b.setAttribute("aria-controls", "row-detail");
    tr.children[0].replaceChildren(b);
  }
  updateWhatif();
}

function clearPower() {
  for (const id of ["mde", "n-required"]) $(id).textContent = "n/a";
  $("n-required-note").textContent = "";
  $("power-note").hidden = true; $("power-note").textContent = "";
  $("mde-table").querySelector("tbody").replaceChildren();
  renderChart([]);
}

async function updatePower() {
  const r = last;
  if (!r || r.n < 2) { $("power").hidden = true; return; }
  $("power").hidden = false;
  const binary = r.score_type === "binary", observed = binary ? r.pd : r.var_d;
  const noVar = !(observed > 1e-15);  // all-equal differences can leave float dust in Var(d)
  $("power-variation").hidden = !noVar;
  $("assumed-pd-label").hidden = !binary; $("assumed-sd-label").hidden = binary;
  const trials = !!(r.noise && r.noise.repeated);
  $("pd-box").hidden = !binary; $("var-d-box").hidden = binary && !trials;
  $("pd").textContent = binary ? f4(r.pd) : "";
  $("var-d").textContent = binary && !trials ? "" : r.var_d.toFixed(6);
  $("power-method").textContent = binary ? "Connor (paired binary)" : "Paired normal approximation (Miller 2024)";
  let value = noVar ? 0 : observed;
  const withTrials = trials && !binary;  // binary power is driven by p_d, which has no trial decomposition
  if (withTrials && whatifMsg()) { clearPower(); return; }  // invalid what-if input: power shows n/a, not stale numbers
  if (withTrials && !noVar) value = Math.max(0, r.noise.omega2) + noiseAt(r.noise, ...whatif(r.noise));
  const assumedId = binary ? "assumed-pd" : "assumed-sd";
  if (noVar && $(assumedId).value.trim() !== "") { const a = num(assumedId); value = binary ? a : a * a; }
  const seq = ++powerSeq;
  const p = await postJSON("/api/power", { design: r.score_type, value, alpha: r.alpha, power: num("target-power"),
                                          effect: num("target-effect"), n: r.n });
  if (seq !== powerSeq) return;
  $("power-error").textContent = p.error || "";
  if (p.error) { clearPower(); return; }
  $("power-method").textContent = p.method + (trials ? " with trials" : "");
  $("mde").textContent = p.mde === null ? "n/a" : f4(p.mde);
  $("n-required").textContent = p.n_required === null ? "n/a" : String(p.n_required);
  $("n-required-note").textContent = p.n_required_note || "";
  const notSig = r.p_value === null || r.p_value >= r.alpha;
  const show = notSig && p.mde !== null && Math.abs(r.diff) < p.mde;
  $("power-note").hidden = !show; $("power-note").textContent = show ? POWER_NOTE : "";
  $("mde-table").querySelector("tbody").replaceChildren(...p.table.map((t) => {
    const tr = document.createElement("tr");
    tr.dataset.n = t.n;
    if (t.current) tr.className = "current";
    for (const v of [String(t.n), t.mde === null ? "n/a" : f4(t.mde), t.current ? "current" : ""]) {
      const td = document.createElement("td"); td.textContent = v; tr.appendChild(td);
    }
    return tr;
  }));
  renderChart(p.table);
}

async function updatePlan() {
  const binary = $("plan-design").value === "binary";
  $("plan-pd-label").hidden = !binary; $("plan-sd-label").hidden = binary;
  const sd = num("plan-sd"), nAt = num("plan-n-input");
  const seq = ++planSeq;
  const p = await postJSON("/api/power", { design: binary ? "binary" : "continuous", value: binary ? num("plan-pd") : sd * sd,
    alpha: Number($("alpha").value), power: num("target-power"), effect: num("plan-effect"), n: nAt });
  if (seq !== planSeq) return;
  $("plan-error").textContent = p.error || "";
  $("plan-n").textContent = p.error || p.n_required === null ? "n/a" : String(p.n_required);
  $("plan-mde-at-n").textContent = p.error || p.mde === null ? "n/a" : f4(p.mde);
  $("plan-note").textContent = p.error ? "" : p.n_required_note || "";
}

function render(r) {
  last = r.error || r.columns ? null : r;
  showWarnings(r.warnings);
  $("error").textContent = r.error || "";
  if (r.columns) fillMapping(r.columns, r.missing_columns);
  else if (!r.mapped) hideMapping();  // this comparison did not need the user's mapping
  if (r.error || r.columns) { $("results").hidden = true; $("verdict").textContent = ""; renderNoise({ noise: { repeated: false } }); return; }
  $("results").hidden = false;
  $("verdict").textContent = r.verdict;
  $("note").textContent = r.note;
  $("n-paired").textContent = r.n;
  $("score-type").textContent = r.score_type;
  $("mean-a").textContent = f4(r.mean_a);
  $("mean-b").textContent = f4(r.mean_b);
  $("diff").textContent = sgn(r.diff);
  $("se-paired").textContent = r.var_d === null ? "n/a" : f4(Math.sqrt(r.var_d / r.n));
  $("ci-label").textContent = r.ci_label;
  $("ci-low").textContent = r.ci ? sgn(r.ci[0]) : "n/a";
  $("ci-high").textContent = r.ci ? sgn(r.ci[1]) : "n/a";
  $("test-name").textContent = r.test;
  $("p-value").textContent = fp(r.p_value);
  const fl = r.flips, cell = (x) => r.score_type === "binary" ? String(x) : f4(x);
  $("count-improved").textContent = fl.improved.length;
  $("count-regressed").textContent = fl.regressed.length;
  $("count-both-pass").textContent = fl.both_pass;
  $("count-both-fail").textContent = fl.both_fail;
  setRows("improved-table", fl.improved, (x) => [x.id, cell(x.a), cell(x.b)]);
  setRows("regressed-table", fl.regressed, (x) => [x.id, cell(x.a), cell(x.b)]);
  $("changes").hidden = r.score_type !== "continuous";
  setRows("changes-table", r.changes, (x) => [x.id, f4(x.a), f4(x.b), sgn(x.d)]);
  const unchanged = fl.both_pass + fl.both_fail;
  $("summary").textContent = `${fl.improved.length} improved, ${fl.regressed.length} regressed, ${unchanged} unchanged. ` +
    (r.p_value === null ? `The ${r.test} p-value is undefined for this data, so there is no evidence either way.`
      : `If A and B were equally good, a difference at least this large would occur with probability ${fp(r.p_value)}.`);
  renderTests(r);
  Object.assign(ex, { rows: r.rows, byId: new Map(r.rows.map((x) => [x.id, x])), filter: "all", sort: null, cell });
  $("search-id").value = "";
  $("row-detail").hidden = true;
  renderRows();
  renderNoise(r);
}

async function compare() {
  const settings = readSettings();
  if (!settings) return;
  const btn = $("compare-btn");
  btn.disabled = true;
  try {
    render(await postJSON("/api/compare", { a: await readSide("a"), b: await readSide("b"), settings, mapping: readMapping() }));
    await updatePower();
  } catch (e) {
    render({ error: e.message, warnings: [] });
  } finally {
    btn.disabled = false;
  }
}

async function mapColumns() {
  try {
    const cols = await postJSON("/api/columns", { a: await readSide("a"), b: await readSide("b") });
    const errs = ["a", "b"].map((k) => cols[k] && cols[k].error).filter(Boolean);
    $("error").textContent = errs.join(" ");
    if (errs.length) return;
    fillMapping(cols);
  } catch (e) {
    $("error").textContent = e.message;
  }
}

function copyFiles(list) { const dt = new DataTransfer(); for (const f of list) dt.items.add(f); return dt.files; }

function swap() {
  hideMapping();
  const fa = copyFiles($("file-a").files), fb = copyFiles($("file-b").files);
  $("file-a").files = fb; $("file-b").files = fa;
  for (const id of ["paste", "name"]) {
    const a = $(id + "-a"), b = $(id + "-b"), prop = id === "paste" ? "value" : "textContent";
    [a[prop], b[prop]] = [b[prop], a[prop]];
  }
}

let examples = [];
async function loadExample() {
  const sel = examples.find((e) => e.value === $("example-select").value);
  if (!sel) return;
  hideMapping();
  const texts = await Promise.all(sel.files.map((f) => fetch("/fixtures/" + f).then((r) => r.text())));
  ["a", "b"].forEach((k, i) => {
    $("file-" + k).value = "";
    $("paste-" + k).value = texts[i];
    $("name-" + k).textContent = sel.files[i];
  });
}

for (const k of ["a", "b"]) {
  $("file-" + k).addEventListener("change", (e) => { hideMapping(); $("name-" + k).textContent = e.target.files[0] ? e.target.files[0].name : ""; });
  $("paste-" + k).addEventListener("input", () => { if (!$("file-" + k).files.length) $("name-" + k).textContent = ""; });
}
$("compare-btn").addEventListener("click", compare);
$("swap-btn").addEventListener("click", swap);
$("load-example").addEventListener("click", loadExample);
$("map-columns").addEventListener("click", mapColumns);
for (const b of document.querySelectorAll("[data-filter]")) b.addEventListener("click", () => { ex.filter = b.dataset.filter; renderRows(); });
$("search-id").addEventListener("input", renderRows);
$("sort-delta").addEventListener("click", () => { ex.sort = ex.sort === "asc" ? "desc" : "asc"; renderRows(); });
for (const id of ["whatif-k", "whatif-j"]) $(id).addEventListener("input", () => { updateWhatif(); updatePower(); });
$("unstable-table").querySelector("tbody").addEventListener("click", (e) => { const tr = e.target.closest("tr"); if (tr) showDetail(tr.dataset.id, "unstable-table"); });
const rowsBody = $("rows-table").querySelector("tbody");
rowsBody.addEventListener("click", (e) => { const tr = e.target.closest("tr"); if (tr) showDetail(tr.dataset.id); });
for (const id of ["target-power", "target-effect", "assumed-pd", "assumed-sd"]) $(id).addEventListener("input", () => { updatePower(); updatePlan(); });
for (const id of ["plan-design", "plan-pd", "plan-sd", "plan-effect", "plan-n-input", "alpha"]) for (const t of ["input", "change"]) $(id).addEventListener(t, updatePlan);
updatePlan();
for (const id of ["n-boot", "seed", "threshold"]) for (const t of ["input", "change"]) $(id).addEventListener(t, validateSettings);
fetch("/api/examples").then((r) => r.json()).then((list) => {
  examples = list;
  $("example-select").replaceChildren(...list.map((e) => new Option(e.label, e.value)));
});
