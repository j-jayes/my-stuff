"""photo-options.json -> photo-picker.html and picker-index.json."""
import json
from pathlib import Path

HERE = Path(__file__).parent
products = json.loads((HERE / "photo-options.json").read_text())
products.sort(key=lambda p: (p["gifted"], p["category"] or "", p["name"]))
for n, p in enumerate(products, 1):
    p["key"] = f"p{n:03d}"

with_options = [p for p in products if p["options"]]
without = [p for p in products if not p["options"]]
(HERE / "picker-index.json").write_text(json.dumps(
    [{k: p[k] for k in ("key", "ids", "brand", "name")} | {"options": [{"image_url": o["image_url"], "page": o["page"]} for o in p["options"]]} for p in with_options],
    ensure_ascii=False, indent=1))

data = [{
    "key": p["key"],
    "title": " ".join(filter(None, [p["brand"], p["name"]])),
    "category": p["category"] or "No category",
    "gifted": p["gifted"],
    "count": len(p["ids"]),
    "options": [{"thumb": o["thumb"], "host": o["host"], "title": o["title"], "page": o["page"]} for o in p["options"]],
} for p in with_options]
missing = [" ".join(filter(None, [p["brand"], p["name"]])) for p in without]

PAGE = r"""<title>Photo Picker</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700&family=Noto+Serif+JP:wght@300&display=swap">
<style>
/* A contact sheet: one row per item, three photos, pick one or none. House colours from My Stuff. */
:root{--bg:#fcfbf8;--surface:#fff;--sunken:#f4f2ec;--line:#e6e3dc;--ink:#26262a;--text:#404040;--muted:#6b6b6b;--accent:#1a6d94;--accent-soft:#deebf7;--on-accent:#fff;
--display:'Noto Serif JP',Georgia,serif;--body:'Lato',system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#16161a;--surface:#1e1e23;--sunken:#141418;--line:#32323a;--ink:#f2f2ee;--text:#ddddd8;--muted:#9a9a97;--accent:#9ed2ef;--accent-soft:#1b3243;--on-accent:#10222e;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#16161a;--surface:#1e1e23;--sunken:#141418;--line:#32323a;--ink:#f2f2ee;--text:#ddddd8;--muted:#9a9a97;--accent:#9ed2ef;--accent-soft:#1b3243;--on-accent:#10222e;color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--text);font:16px/1.5 var(--body);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:32px 64px}
.wrap{max-width:860px;margin:0 auto;display:grid;gap:24px}
h1{font:300 28px/1.2 var(--display);color:var(--accent);margin:0}
header p{margin:6px 0 0;color:var(--muted);max-width:62ch}
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);padding-block:10px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center;font-size:14px}
.bar b{color:var(--ink);font-variant-numeric:tabular-nums}
.bar label{display:flex;gap:6px;align-items:center;margin-left:auto}
.status{color:var(--muted)}
#list{display:grid;gap:28px}
.item{display:grid;gap:8px;min-width:0}
.item h2{font:700 15px/1.3 var(--body);color:var(--ink);margin:0;overflow-wrap:anywhere}
.meta{font-size:13px;color:var(--muted)}
.opts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.opt{display:grid;gap:4px;min-width:0}
.opt button{display:block;width:100%;aspect-ratio:1;padding:0;border:1px solid var(--line);border-radius:2px;background:#fff;cursor:pointer;overflow:hidden}
.opt button img{display:block;width:100%;height:100%;object-fit:contain}
.opt button[aria-pressed="true"]{outline:3px solid var(--accent);outline-offset:-3px}
.opt a{font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.none{justify-self:start;font:inherit;font-size:13px;padding:6px 12px;background:transparent;color:var(--text);border:1px solid var(--line);border-radius:2px;cursor:pointer}
.none[aria-pressed="true"]{background:var(--accent);color:var(--on-accent);border-color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
details{font-size:14px;color:var(--muted)}
details ul{margin:8px 0 0;padding-left:18px}
@media (max-width:480px){.opts{gap:4px}}
</style>
<div class="wrap">
<header><h1>Photo Picker</h1><p>Up to three photos found for each thing with no picture. Tap the one that matches what you own, or None of these. Each choice saves as you go.</p></header>
<div class="bar"><span><b id="todo">0</b> to choose</span><span><b id="picked">0</b> photos picked</span><span><b id="none">0</b> none</span><span class="status" id="status" role="status"></span><label><input type="checkbox" id="hide"> Hide finished</label></div>
<div id="list"></div>
<details id="missing"><summary></summary><ul></ul></details>
</div>
<script>
const ITEMS = __DATA__;
const MISSING = __MISSING__;
const picks = {};
let db = null;
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const list = document.getElementById("list");
function card(i) {
  const p = picks[i.key];
  const extra = [i.category, i.gifted ? "Given away" : "", i.count > 1 ? `Applies to ${i.count} entries` : ""].filter(Boolean).join(" · ");
  return `<article class="item" data-key="${i.key}"><h2>${esc(i.title)}</h2><div class="meta">${esc(extra)}</div>
  <div class="opts">${i.options.map((o, n) => `<div class="opt"><button type="button" data-pick="${n}" aria-pressed="${p === n}" aria-label="Option ${n + 1}: ${esc(o.title)}"><img alt="" loading="lazy" src="data:image/jpeg;base64,${o.thumb}"></button><a href="${esc(o.page)}" target="_blank" rel="noopener">${esc(o.host)}</a></div>`).join("")}</div>
  <button type="button" class="none" data-pick="none" aria-pressed="${p === "none"}">None of these</button></article>`;
}
function tally() {
  const vals = ITEMS.map(i => picks[i.key]);
  document.getElementById("todo").textContent = vals.filter(v => v === undefined).length;
  document.getElementById("picked").textContent = vals.filter(v => typeof v === "number").length;
  document.getElementById("none").textContent = vals.filter(v => v === "none").length;
}
function render() {
  const hide = document.getElementById("hide").checked;
  list.innerHTML = ITEMS.filter(i => !hide || picks[i.key] === undefined).map(card).join("");
  tally();
}
function status(t) { document.getElementById("status").textContent = t; }
async function save(key) {
  if (!db) { status("Not saving: this view has no storage."); return; }
  try { await db.collection("choices").doc(key).set({pick: picks[key]}); status(""); }
  catch (e) { status("That choice did not save. Tap it again."); }
}
list.addEventListener("click", e => {
  const b = e.target.closest("[data-pick]");
  if (!b) return;
  const art = b.closest(".item"), key = art.dataset.key;
  picks[key] = b.dataset.pick === "none" ? "none" : Number(b.dataset.pick);
  art.querySelectorAll("[data-pick]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  tally(); save(key);
});
document.getElementById("hide").addEventListener("change", render);
const m = document.getElementById("missing");
if (MISSING.length) { m.querySelector("summary").textContent = `${MISSING.length} things had no usable photo`; m.querySelector("ul").innerHTML = MISSING.map(t => `<li>${esc(t)}</li>`).join(""); } else m.hidden = true;
render();
status("Loading your choices…");
const timer = setTimeout(() => status("Could not load saved choices. Reload the page."), 10000);
window.claude.use("db").then(d => {
  if (!d) { clearTimeout(timer); status("Choices cannot be saved in this view."); return; }
  db = d;
  db.collection("choices").onSnapshot(snap => {
    clearTimeout(timer); status("");
    let changed = false;
    snap.docs.forEach(x => { const v = x.data().pick; if (picks[x.id] !== v) { picks[x.id] = v; changed = true; } });
    if (changed) render();
  }, () => { clearTimeout(timer); status("Could not load saved choices. Reload the page."); });
});
</script>
"""
html = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")).replace("__MISSING__", json.dumps(missing, ensure_ascii=False).replace("</", "<\\/"))
(HERE / "photo-picker.html").write_text(html)
counts = [len(p["options"]) for p in products]
print(len(products), "products;", {n: counts.count(n) for n in range(4)}, round(len(html) / 1e6, 2), "MB")
