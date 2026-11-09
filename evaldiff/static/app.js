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

// Read and validate the settings panel; returns null (and shows why) when a value is out of range.
function readSettings() {
  const num = (id) => $(id).value.trim() === "" ? NaN : Number($(id).value);
  const nBoot = num("n-boot"), seed = num("seed"), threshold = num("threshold");
  let msg = "";
  if (!Number.isInteger(nBoot) || nBoot < 1000 || nBoot > 100000) msg = "Bootstrap resamples must be between 1000 and 100000";
  else if (!Number.isSafeInteger(seed)) msg = "Seed must be an integer";
  else if (!Number.isFinite(threshold)) msg = "Threshold must be a number";
  $("settings-error").textContent = msg;
  if (msg) {  // results on screen no longer match the settings on screen
    $("results").hidden = true; $("verdict").textContent = "";
    return null;
  }
  return { alpha: Number($("alpha").value), seed, n_boot: nBoot, threshold,
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

const hideMapping = () => { $("mapping").hidden = true; };

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
  for (const tr of $("rows-table").querySelectorAll("tbody tr")) tr.tabIndex = 0;
  for (const b of document.querySelectorAll("[data-filter]")) b.setAttribute("aria-pressed", String(b.dataset.filter === ex.filter));
  $("sort-delta").parentElement.setAttribute("aria-sort", ex.sort ? (ex.sort === "asc" ? "ascending" : "descending") : "none");
}

const rawText = (rec) => Object.entries(rec).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ");

function showDetail(id) {
  const r = ex.byId.get(id);
  if (!r) return;
  const box = $("row-detail");
  const h = document.createElement("h4");
  h.textContent = `Row ${id} (${r.status}, Δ ${sgn(r.d)})`;
  const close = document.createElement("button");
  close.type = "button"; close.textContent = "Close"; close.addEventListener("click", () => { box.hidden = true; });
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

function render(r) {
  showWarnings(r.warnings);
  $("error").textContent = r.error || "";
  if (r.columns) fillMapping(r.columns, r.missing_columns);
  if (r.error || r.columns) { $("results").hidden = true; $("verdict").textContent = ""; return; }
  $("results").hidden = false;
  $("verdict").textContent = r.verdict;
  $("note").textContent = r.note;
  $("n-paired").textContent = r.n;
  $("score-type").textContent = r.score_type;
  $("mean-a").textContent = f4(r.mean_a);
  $("mean-b").textContent = f4(r.mean_b);
  $("diff").textContent = sgn(r.diff);
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
}

async function compare() {
  const settings = readSettings();
  if (!settings) return;
  const btn = $("compare-btn");
  btn.disabled = true;
  try {
    const body = JSON.stringify({ a: await readSide("a"), b: await readSide("b"), settings, mapping: readMapping() });
    const res = await fetch("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body });
    render(await res.json());
  } catch (e) {
    render({ error: e.message, warnings: [] });
  } finally {
    btn.disabled = false;
  }
}

async function mapColumns() {
  try {
    const body = JSON.stringify({ a: await readSide("a"), b: await readSide("b") });
    const res = await fetch("/api/columns", { method: "POST", headers: { "Content-Type": "application/json" }, body });
    const cols = await res.json();
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
const rowsBody = $("rows-table").querySelector("tbody");
rowsBody.addEventListener("click", (e) => { const tr = e.target.closest("tr"); if (tr) showDetail(tr.dataset.id); });
rowsBody.addEventListener("keydown", (e) => { const tr = e.target.closest("tr"); if (tr && e.key === "Enter") showDetail(tr.dataset.id); });
fetch("/api/examples").then((r) => r.json()).then((list) => {
  examples = list;
  $("example-select").replaceChildren(...list.map((e) => new Option(e.label, e.value)));
});
