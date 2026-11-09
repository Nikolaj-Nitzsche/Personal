"""Builds a self-contained interactive periodic-table HTML page from the
superconductors.json dataset. Standalone script (Python stdlib only) — run it,
it writes the final .html file."""
import json
import io

SRC_JSON = r"C:\Users\nkn4000\Heriot-Watt University Team Dropbox\Nikolaj Nitzsche\Qmag\01 GroupFolder\PhD_Nikolaj\06 Data\Modeling\SC\SC_HTML_Periodic_table\superconductors_v3.json"
OUT_HTML = r"C:\Users\nkn4000\Documents\Code\Repositories\Personal\superconductor_periodic_table.html"

# Standard 118-element periodic table layout: (symbol, name, atomic number, grid row, grid col).
# Rows 1-7 are the main body; row 8 is a blank spacer; rows 9-10 are the lanthanide/actinide series.
LAYOUT = [
    ("H", "Hydrogen", 1, 1, 1), ("He", "Helium", 2, 1, 18),
    ("Li", "Lithium", 3, 2, 1), ("Be", "Beryllium", 4, 2, 2),
    ("B", "Boron", 5, 2, 13), ("C", "Carbon", 6, 2, 14), ("N", "Nitrogen", 7, 2, 15),
    ("O", "Oxygen", 8, 2, 16), ("F", "Fluorine", 9, 2, 17), ("Ne", "Neon", 10, 2, 18),
    ("Na", "Sodium", 11, 3, 1), ("Mg", "Magnesium", 12, 3, 2),
    ("Al", "Aluminium", 13, 3, 13), ("Si", "Silicon", 14, 3, 14), ("P", "Phosphorus", 15, 3, 15),
    ("S", "Sulfur", 16, 3, 16), ("Cl", "Chlorine", 17, 3, 17), ("Ar", "Argon", 18, 3, 18),
    ("K", "Potassium", 19, 4, 1), ("Ca", "Calcium", 20, 4, 2), ("Sc", "Scandium", 21, 4, 3),
    ("Ti", "Titanium", 22, 4, 4), ("V", "Vanadium", 23, 4, 5), ("Cr", "Chromium", 24, 4, 6),
    ("Mn", "Manganese", 25, 4, 7), ("Fe", "Iron", 26, 4, 8), ("Co", "Cobalt", 27, 4, 9),
    ("Ni", "Nickel", 28, 4, 10), ("Cu", "Copper", 29, 4, 11), ("Zn", "Zinc", 30, 4, 12),
    ("Ga", "Gallium", 31, 4, 13), ("Ge", "Germanium", 32, 4, 14), ("As", "Arsenic", 33, 4, 15),
    ("Se", "Selenium", 34, 4, 16), ("Br", "Bromine", 35, 4, 17), ("Kr", "Krypton", 36, 4, 18),
    ("Rb", "Rubidium", 37, 5, 1), ("Sr", "Strontium", 38, 5, 2), ("Y", "Yttrium", 39, 5, 3),
    ("Zr", "Zirconium", 40, 5, 4), ("Nb", "Niobium", 41, 5, 5), ("Mo", "Molybdenum", 42, 5, 6),
    ("Tc", "Technetium", 43, 5, 7), ("Ru", "Ruthenium", 44, 5, 8), ("Rh", "Rhodium", 45, 5, 9),
    ("Pd", "Palladium", 46, 5, 10), ("Ag", "Silver", 47, 5, 11), ("Cd", "Cadmium", 48, 5, 12),
    ("In", "Indium", 49, 5, 13), ("Sn", "Tin", 50, 5, 14), ("Sb", "Antimony", 51, 5, 15),
    ("Te", "Tellurium", 52, 5, 16), ("I", "Iodine", 53, 5, 17), ("Xe", "Xenon", 54, 5, 18),
    ("Cs", "Cesium", 55, 6, 1), ("Ba", "Barium", 56, 6, 2),
    ("Hf", "Hafnium", 72, 6, 4), ("Ta", "Tantalum", 73, 6, 5), ("W", "Tungsten", 74, 6, 6),
    ("Re", "Rhenium", 75, 6, 7), ("Os", "Osmium", 76, 6, 8), ("Ir", "Iridium", 77, 6, 9),
    ("Pt", "Platinum", 78, 6, 10), ("Au", "Gold", 79, 6, 11), ("Hg", "Mercury", 80, 6, 12),
    ("Tl", "Thallium", 81, 6, 13), ("Pb", "Lead", 82, 6, 14), ("Bi", "Bismuth", 83, 6, 15),
    ("Po", "Polonium", 84, 6, 16), ("At", "Astatine", 85, 6, 17), ("Rn", "Radon", 86, 6, 18),
    ("Fr", "Francium", 87, 7, 1), ("Ra", "Radium", 88, 7, 2),
    ("Rf", "Rutherfordium", 104, 7, 4), ("Db", "Dubnium", 105, 7, 5), ("Sg", "Seaborgium", 106, 7, 6),
    ("Bh", "Bohrium", 107, 7, 7), ("Hs", "Hassium", 108, 7, 8), ("Mt", "Meitnerium", 109, 7, 9),
    ("Ds", "Darmstadtium", 110, 7, 10), ("Rg", "Roentgenium", 111, 7, 11), ("Cn", "Copernicium", 112, 7, 12),
    ("Nh", "Nihonium", 113, 7, 13), ("Fl", "Flerovium", 114, 7, 14), ("Mc", "Moscovium", 115, 7, 15),
    ("Lv", "Livermorium", 116, 7, 16), ("Ts", "Tennessine", 117, 7, 17), ("Og", "Oganesson", 118, 7, 18),
    ("La", "Lanthanum", 57, 9, 3), ("Ce", "Cerium", 58, 9, 4), ("Pr", "Praseodymium", 59, 9, 5),
    ("Nd", "Neodymium", 60, 9, 6), ("Pm", "Promethium", 61, 9, 7), ("Sm", "Samarium", 62, 9, 8),
    ("Eu", "Europium", 63, 9, 9), ("Gd", "Gadolinium", 64, 9, 10), ("Tb", "Terbium", 65, 9, 11),
    ("Dy", "Dysprosium", 66, 9, 12), ("Ho", "Holmium", 67, 9, 13), ("Er", "Erbium", 68, 9, 14),
    ("Tm", "Thulium", 69, 9, 15), ("Yb", "Ytterbium", 70, 9, 16), ("Lu", "Lutetium", 71, 9, 17),
    ("Ac", "Actinium", 89, 10, 3), ("Th", "Thorium", 90, 10, 4), ("Pa", "Protactinium", 91, 10, 5),
    ("U", "Uranium", 92, 10, 6), ("Np", "Neptunium", 93, 10, 7), ("Pu", "Plutonium", 94, 10, 8),
    ("Am", "Americium", 95, 10, 9), ("Cm", "Curium", 96, 10, 10), ("Bk", "Berkelium", 97, 10, 11),
    ("Cf", "Californium", 98, 10, 12), ("Es", "Einsteinium", 99, 10, 13), ("Fm", "Fermium", 100, 10, 14),
    ("Md", "Mendelevium", 101, 10, 15), ("No", "Nobelium", 102, 10, 16), ("Lr", "Lawrencium", 103, 10, 17),
]
assert len(LAYOUT) == 118, len(LAYOUT)

with io.open(SRC_JSON, encoding="utf-8") as f:
    sc_data = json.load(f)

layout_js = [{"sym": s, "name": n, "num": num, "row": r, "col": c} for s, n, num, r, c in LAYOUT]

DATA = {"meta": sc_data["meta"], "elements": sc_data["elements"], "compounds": sc_data["compounds"],
        "layout": layout_js}

DATA_JSON = json.dumps(DATA, ensure_ascii=False)

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Superconductor Periodic Table</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    color-scheme: light;
    --surface-1:      #fcfcfb;
    --surface-2:      #f9f9f7;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --gridline:       #e1e0d9;
    --border:         rgba(11,11,11,0.10);

    --blue:    #2a78d6;   /* selected */
    --blue-bg: #cde2fb;
    --orange:    #eb6834; /* related (co-occurring) */
    --orange-bg: #fbdccb;
    --aqua:    #1baf7a;   /* ambient elemental superconductor */
    --aqua-bg: #c9f0e1;
    --yellow:    #eda100; /* high-pressure-only elemental superconductor */
    --yellow-bg: #fbe6bf;
    --compound-bg: #e7e6f5; /* compound-only element, no ambient elemental data */

    --status-good:     #0ca30c;
    --status-warning:  #fab219;
    --status-serious:  #ec835a;
    --status-critical: #d03b3b;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --surface-1:      #1a1a19;
      --surface-2:      #0d0d0d;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --gridline:       #2c2c2a;
      --border:         rgba(255,255,255,0.10);

      --blue:    #3987e5;
      --blue-bg: #184f95;
      --orange:    #d95926;
      --orange-bg: #7a3313;
      --aqua:    #199e70;
      --aqua-bg: #0e4a35;
      --yellow:    #c98500;
      --yellow-bg: #5c3d00;
      --compound-bg: #2c2a45;

      --status-good:     #0ca30c;
      --status-warning:  #fab219;
      --status-serious:  #ec835a;
      --status-critical: #d03b3b;
    }
  }

  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0;
    background: var(--surface-2);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  body { padding: 20px 20px 48px; }

  h1 { font-size: 1.35rem; margin: 0 0 4px; }
  .subtitle { color: var(--text-secondary); font-size: 0.9rem; margin: 0 0 14px; max-width: 900px; }

  details.about {
    max-width: 900px; margin: 0 0 18px; font-size: 0.83rem; color: var(--text-secondary);
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px;
  }
  details.about summary { cursor: pointer; font-weight: 600; color: var(--text-primary); }
  details.about p { margin: 8px 0 0; line-height: 1.5; }

  .layout { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }

  .table-scroll { overflow-x: auto; padding-bottom: 8px; }
  .ptable {
    display: grid;
    grid-template-columns: repeat(18, 44px);
    grid-template-rows: repeat(10, 44px);
    gap: 3px;
    width: max-content;
  }
  .cell {
    grid-column: var(--c); grid-row: var(--r);
    border-radius: 5px;
    border: 1px solid var(--border);
    background: var(--surface-1);
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    cursor: default;
    position: relative;
    padding: 2px;
    transition: opacity 120ms ease, transform 80ms ease, background-color 120ms ease;
  }
  .cell .num { font-size: 0.5rem; color: var(--text-muted); position: absolute; top: 2px; left: 3px; }
  .cell .sym { font-size: 0.92rem; font-weight: 700; line-height: 1; }
  .cell.clickable { cursor: pointer; }
  .cell.clickable:hover { transform: scale(1.08); z-index: 5; box-shadow: 0 2px 8px var(--border); }

  .cell.state-ambient   { background: var(--aqua-bg); }
  .cell.state-highp     { background: var(--yellow-bg); }
  .cell.state-compound  { background: var(--compound-bg); }
  .cell.state-none      { opacity: 0.45; }

  .cell.sel-selected { background: var(--blue); border-color: var(--blue); }
  .cell.sel-selected .sym, .cell.sel-selected .num { color: #fff; }
  .cell.sel-related  { background: var(--orange-bg); border-color: var(--orange); border-width: 2px; }
  .cell.sel-faded     { opacity: 0.25; }

  .legend { display: flex; flex-wrap: wrap; gap: 14px; margin: 12px 0 0; font-size: 0.78rem; color: var(--text-secondary); max-width: 820px; }
  .legend .item { display: flex; align-items: center; gap: 6px; }
  .swatch { width: 14px; height: 14px; border-radius: 4px; border: 1px solid var(--border); flex: none; }

  .panel {
    flex: 1 1 340px; min-width: 320px; max-width: 480px;
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px 18px; font-size: 0.87rem; line-height: 1.5;
  }
  .panel h2 { margin: 0 0 2px; font-size: 1.15rem; }
  .panel .el-name { color: var(--text-secondary); font-size: 0.85rem; margin: 0 0 12px; }
  .panel .empty { color: var(--text-muted); }
  .badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 999px;
    color: #fff; margin: 0 6px 6px 0;
  }
  .badge.good     { background: var(--status-good); }
  .badge.warning  { background: var(--status-warning); color: #1a1a19; }
  .badge.serious  { background: var(--status-serious); }
  .badge.critical { background: var(--status-critical); }
  .badge.info     { background: var(--text-muted); }

  .section-title { font-weight: 700; margin: 16px 0 6px; font-size: 0.85rem; }
  .compound {
    border-top: 1px solid var(--gridline); padding: 8px 0;
  }
  .compound:first-child { border-top: none; }
  .compound .name { font-weight: 700; }
  .compound .meta { color: var(--text-secondary); font-size: 0.8rem; }
  .compound .notes { font-size: 0.8rem; margin-top: 3px; }
  .compound .ref { font-size: 0.75rem; color: var(--text-muted); margin-top: 3px; }
  .chip-row { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
  .chip {
    font-size: 0.75rem; padding: 1px 7px; border-radius: 999px;
    background: var(--surface-2); border: 1px solid var(--border); cursor: pointer;
  }
  .chip:hover { border-color: var(--blue); color: var(--blue); }
  .clear-btn {
    font-size: 0.78rem; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--border);
    background: var(--surface-2); color: var(--text-primary); cursor: pointer; margin-top: 4px;
  }
  .clear-btn:hover { border-color: var(--blue); }

  .tooltip {
    position: fixed; pointer-events: none; z-index: 50;
    background: var(--text-primary); color: var(--surface-1);
    font-size: 0.75rem; padding: 5px 9px; border-radius: 6px;
    max-width: 220px; line-height: 1.4; display: none;
  }
</style>
</head>
<body>
<div class="viz-root">

  <h1>Superconductor Periodic Table</h1>
  <p class="subtitle">Click an element to see which other elements it has been combined with in known superconductors, plus its own superconducting properties if any.</p>

  <details class="about">
    <summary>About this dataset</summary>
    <p><strong>Scope:</strong> <span id="about-scope"></span></p>
    <p><strong>Disputed / retracted claims policy:</strong> <span id="about-disputed"></span></p>
    <p><strong>Compiled:</strong> <span id="about-compiled"></span></p>
  </details>

  <div class="layout">
    <div>
      <div class="table-scroll">
        <div class="ptable" id="ptable"></div>
      </div>
      <div class="legend" id="legend"></div>
    </div>
    <div class="panel" id="panel"></div>
  </div>

</div>
<div class="tooltip" id="tooltip"></div>

<script>
const DATA = __DATA_JSON__;

const els = DATA.elements;       // symbol -> elemental SC info
const compounds = DATA.compounds; // list
const layout = DATA.layout;       // grid positions

function compoundsFor(sym) {
  return compounds.filter(c => c.elements.includes(sym));
}
function partnersFor(sym) {
  const set = new Set();
  compoundsFor(sym).forEach(c => c.elements.forEach(e => { if (e !== sym) set.add(e); }));
  return set;
}
function membershipState(sym) {
  const info = els[sym];
  const nCompounds = compoundsFor(sym).length;
  if (info) return info.elemental_sc ? "ambient" : "highp";
  if (nCompounds > 0) return "compound";
  return "none";
}

let selected = null;

function statusBadge(notes) {
  if (!notes) return "";
  const n = notes.toUpperCase();
  if (n.includes("RETRACTED")) return '<span class="badge critical">&#10007; RETRACTED</span>';
  if (n.includes("UNCONFIRMED")) return '<span class="badge warning">&#9888; UNCONFIRMED</span>';
  if (n.includes("THEORETICAL PREDICTION")) return '<span class="badge serious">&#9671; PREDICTED, NOT CONFIRMED</span>';
  return "";
}

function renderTable() {
  const table = document.getElementById("ptable");
  table.innerHTML = "";
  const partners = selected ? partnersFor(selected) : null;

  layout.forEach(({sym, name, num, row, col}) => {
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.style.setProperty("--r", row);
    cell.style.setProperty("--c", col);

    const state = membershipState(sym);
    const interactive = state !== "none";
    if (interactive) cell.classList.add("clickable");

    if (!selected) {
      cell.classList.add("state-" + state);
    } else {
      if (sym === selected) cell.classList.add("sel-selected");
      else if (partners.has(sym)) cell.classList.add("sel-related");
      else cell.classList.add("sel-faded");
    }

    cell.innerHTML = `<span class="num">${num}</span><span class="sym">${sym}</span>`;

    if (interactive) {
      cell.addEventListener("click", () => {
        selected = (selected === sym) ? null : sym;
        renderTable();
        renderPanel();
      });
      cell.addEventListener("mouseenter", (e) => showTooltip(e, sym, name, state));
      cell.addEventListener("mousemove", moveTooltip);
      cell.addEventListener("mouseleave", hideTooltip);
    }

    table.appendChild(cell);
  });
}

function showTooltip(e, sym, name, state) {
  const tip = document.getElementById("tooltip");
  let line = name + " (" + sym + ")";
  if (state === "ambient") line += " \u2014 ambient-pressure elemental superconductor";
  else if (state === "highp") line += " \u2014 elemental superconductor under pressure only";
  else if (state === "compound") line += " \u2014 appears in " + compoundsFor(sym).length + " compound(s) here";
  tip.textContent = line;
  tip.style.display = "block";
  moveTooltip(e);
}
function moveTooltip(e) {
  const tip = document.getElementById("tooltip");
  tip.style.left = (e.clientX + 14) + "px";
  tip.style.top = (e.clientY + 14) + "px";
}
function hideTooltip() {
  document.getElementById("tooltip").style.display = "none";
}

function elementName(sym) {
  const l = layout.find(l => l.sym === sym);
  return l ? l.name : sym;
}

function chipRow(symbols) {
  return '<div class="chip-row">' + symbols.map(s =>
    `<span class="chip" data-sym="${s}">${s} \u2014 ${elementName(s)}</span>`
  ).join("") + "</div>";
}

function renderPanel() {
  const panel = document.getElementById("panel");
  if (!selected) {
    panel.innerHTML = `<p class="empty">Select an element in the table to see its superconducting data and which elements it has been combined with.</p>` + renderLegendNote();
    return;
  }

  const sym = selected;
  const name = elementName(sym);
  const info = els[sym];
  const comps = compoundsFor(sym);
  const partners = Array.from(partnersFor(sym)).sort();

  let html = `<h2>${name}</h2><p class="el-name">${sym}</p>`;
  html += `<button class="clear-btn" id="clear-btn">Clear selection</button>`;

  if (info) {
    if (info.elemental_sc) {
      html += `<div class="section-title">Elemental superconductor (ambient pressure)</div>`;
      html += `<p>T<sub>c</sub> = ${info.tc_ambient_K} K`;
      if (info.tc_highP_K) html += `, rising to ${info.tc_highP_K} K at ${info.pressure_GPa} GPa`;
      html += `</p>`;
    } else {
      html += `<div class="section-title">Elemental superconductor (high pressure only)</div>`;
      html += `<p>T<sub>c</sub> = ${info.tc_highP_K} K at ${info.pressure_GPa} GPa (does not superconduct at ambient pressure)</p>`;
    }
    if (info.notes) html += `<p class="compound notes" style="border:none;padding:0;">${info.notes}</p>`;
    html += `<p class="ref">${info.ref}</p>`;
  }

  if (comps.length > 0) {
    html += `<div class="section-title">Compounds containing ${sym} (${comps.length})</div>`;
    comps.forEach(c => {
      const others = c.elements.filter(e => e !== sym);
      html += `<div class="compound">
        <div class="name">${c.name}${c.common_name ? " (" + c.common_name + ")" : ""}</div>
        <div class="meta">${c.family} &middot; ${c.tc_K !== null ? "T<sub>c</sub> = " + c.tc_K + " K" : "T<sub>c</sub> not established"} &middot; ${c.pressure} &middot; ${c.discovery_year}</div>
        ${statusBadge(c.notes)}
        ${c.notes ? `<div class="notes">${c.notes}</div>` : ""}
        <div class="ref">${c.ref}</div>
        ${chipRow(others)}
      </div>`;
    });
  }

  if (partners.length > 0) {
    html += `<div class="section-title">All elements combined with ${sym} (${partners.length})</div>`;
    html += chipRow(partners);
  }

  if (!info && comps.length === 0) {
    html += `<p class="empty">No superconductivity data for ${name} in this dataset.</p>`;
  }

  panel.innerHTML = html;

  document.getElementById("clear-btn").addEventListener("click", () => {
    selected = null; renderTable(); renderPanel();
  });
  panel.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      selected = chip.dataset.sym; renderTable(); renderPanel();
      panel.scrollIntoView({behavior: "smooth", block: "nearest"});
    });
  });
}

function renderLegendNote() {
  return "";
}

function renderLegend() {
  const legend = document.getElementById("legend");
  const items = [
    ["--aqua-bg", "Elemental superconductor (ambient pressure)"],
    ["--yellow-bg", "Elemental superconductor (high pressure only)"],
    ["--compound-bg", "Appears only in compounds below"],
    [null, "Selection: selected = blue, combined-with = orange outline, unrelated = faded"],
  ];
  legend.innerHTML = items.map(([varName, label]) => {
    const swatch = varName ? `<span class="swatch" style="background:var(${varName})"></span>` : `<span class="swatch" style="background:var(--blue)"></span>`;
    return `<span class="item">${swatch}${label}</span>`;
  }).join("");
}

document.getElementById("about-scope").textContent = DATA.meta.scope_note;
document.getElementById("about-disputed").textContent = DATA.meta.disputed_claims_policy;
document.getElementById("about-compiled").textContent = DATA.meta.compiled;

renderTable();
renderPanel();
renderLegend();
</script>
</body>
</html>
"""

html_out = HTML_TEMPLATE.replace("__DATA_JSON__", DATA_JSON)

with io.open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_out)

print(f"Wrote {len(html_out):,} bytes to {OUT_HTML}")
print(f"Elements in layout: {len(layout_js)}, elemental SC entries: {len(sc_data['elements'])}, compounds: {len(sc_data['compounds'])}")
