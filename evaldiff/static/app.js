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

function render(r) {
  showWarnings(r.warnings);
  $("error").textContent = r.error || "";
  if (r.error) { $("results").hidden = true; $("verdict").textContent = ""; return; }
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
  $("seed").textContent = r.seed;
  const fl = r.flips, cell = (x) => r.score_type === "binary" ? String(x) : f4(x);
  $("count-improved").textContent = fl.improved.length;
  $("count-regressed").textContent = fl.regressed.length;
  $("count-both-pass").textContent = fl.both_pass;
  $("count-both-fail").textContent = fl.both_fail;
  setRows("improved-table", fl.improved, (x) => [x.id, cell(x.a), cell(x.b)]);
  setRows("regressed-table", fl.regressed, (x) => [x.id, cell(x.a), cell(x.b)]);
  $("changes").hidden = r.score_type !== "continuous";
  setRows("changes-table", r.changes, (x) => [x.id, f4(x.a), f4(x.b), sgn(x.d)]);
}

async function compare() {
  const btn = $("compare-btn");
  btn.disabled = true;
  try {
    const body = JSON.stringify({ a: await readSide("a"), b: await readSide("b") });
    const res = await fetch("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body });
    render(await res.json());
  } catch (e) {
    render({ error: e.message, warnings: [] });
  } finally {
    btn.disabled = false;
  }
}

function copyFiles(list) { const dt = new DataTransfer(); for (const f of list) dt.items.add(f); return dt.files; }

function swap() {
  const fa = copyFiles($("file-a").files), fb = copyFiles($("file-b").files);
  $("file-a").files = fb; $("file-b").files = fa;
  for (const id of ["paste", "name"]) {
    const a = $(id + "-a"), b = $(id + "-b"), prop = id === "paste" ? "value" : "textContent";
    [a[prop], b[prop]] = [b[prop], a[prop]];
  }
}

let examples = [];
async function loadExample() {
  const ex = examples.find((e) => e.value === $("example-select").value);
  if (!ex) return;
  const texts = await Promise.all(ex.files.map((f) => fetch("/fixtures/" + f).then((r) => r.text())));
  ["a", "b"].forEach((k, i) => {
    $("file-" + k).value = "";
    $("paste-" + k).value = texts[i];
    $("name-" + k).textContent = ex.files[i];
  });
}

for (const k of ["a", "b"]) {
  $("file-" + k).addEventListener("change", (e) => { $("name-" + k).textContent = e.target.files[0] ? e.target.files[0].name : ""; });
  $("paste-" + k).addEventListener("input", () => { if (!$("file-" + k).files.length) $("name-" + k).textContent = ""; });
}
$("compare-btn").addEventListener("click", compare);
$("swap-btn").addEventListener("click", swap);
$("load-example").addEventListener("click", loadExample);
fetch("/api/examples").then((r) => r.json()).then((list) => {
  examples = list;
  $("example-select").replaceChildren(...list.map((e) => new Option(e.label, e.value)));
});
