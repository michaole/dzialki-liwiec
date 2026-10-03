const DATA_URL = "listings.json";
const PORTALS = ["Otodom", "OLX", "Gratka", "Adresowo"];
const DAY = 86_400_000;

const $ = (sel, root = document) => root.querySelector(sel);
const fmt = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 });
const dateFmt = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "long" });
const shortDate = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "short", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat("pl-PL", { hour: "2-digit", minute: "2-digit" });

// ── browser storage (personal: stars, notes, last visit, filters) ────────
const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(`dl.${key}`); return v === null ? fallback : JSON.parse(v); }
    catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(`dl.${key}`, JSON.stringify(value)); } catch { /* private mode */ }
  },
};

const stars = new Set(store.get("stars", []));
const notes = store.get("notes", {});

function plural(n, one, few, many) {
  if (n === 1) return one;
  const d = n % 10, h = n % 100;
  return d >= 2 && d <= 4 && (h < 12 || h > 14) ? few : many;
}

// The baseline is the data snapshot the visitor saw on their previous visit;
// anything first seen after it is "new since last visit".
function visitBaseline(generated) {
  const visits = store.get("visits", {});
  if (visits.current !== generated) {
    visits.previous = visits.current ?? null;
    visits.current = generated;
    store.set("visits", visits);
  }
  return visits.previous ? visits.previous.slice(0, 10) : null;
}

// Adresowo titles start with the village name, which has its own column
function displayTitle(title, place) {
  const t = (title ?? "").trim();
  if (place && t.toLocaleLowerCase("pl").startsWith(place.toLocaleLowerCase("pl") + " ")) {
    const rest = t.slice(place.length).trim();
    return rest.charAt(0).toLocaleUpperCase("pl") + rest.slice(1);
  }
  return t;
}

function daysLabel(days) {
  return days === 0 ? "dziś" : `${days} ${plural(days, "dzień", "dni", "dni")}`;
}

function daysBetween(a, b) {
  return Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / DAY));
}

function enrich(raw, generatedDay, baseline) {
  // Without a previous visit, "new" means first seen in the latest scrape
  const since = baseline ?? new Date(Date.parse(generatedDay) - DAY).toISOString().slice(0, 10);
  return raw.map((r) => {
    const prices = r.prices ?? [];
    const last = prices.at(-1);
    const before = prices.at(-2);
    const listed = r.data_dodania && r.data_dodania <= r.first_seen ? r.data_dodania : r.first_seen;
    const end = r.active ? generatedDay : r.last_seen;
    const isNew = r.active && r.first_seen > since;
    const isCheaper = r.active && !isNew && last && before && last[0] > since && last[1] < before[1];
    const isGone = !r.active;
    return {
      ...r,
      listed,
      days: daysBetween(listed, end),
      state: isGone ? "gone" : isNew ? "new" : isCheaper ? "cheaper" : "",
      goneRecently: isGone && r.last_seen >= since,
      drop: isCheaper ? before[1] - last[1] : 0,
      wasPrice: isCheaper ? before[1] : null,
      title: displayTitle(r.tytul, r.miejscowosc),
      search: `${r.miejscowosc} ${r.tytul} ${r.odcinek} ${r.zrodlo}`.toLocaleLowerCase("pl"),
    };
  });
}

// ── rendering ──────────────────────────────────────────────────────────
const icon = (name) => $(`#icon-${name}`).content.firstElementChild.cloneNode(true);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

function stateTag(p, i) {
  if (p.state === "new") return el("span", { class: "tag tag--new tag--row", style: `--i:${i}` }, "Nowe");
  if (p.state === "cheaper") {
    return el("span", { class: "tag tag--cheaper tag--row", style: `--i:${i}`, title: `Było ${fmt.format(p.wasPrice)} zł` },
      `−${fmt.format(p.drop)}`, el("span", { class: "tag__was" }, fmt.format(p.wasPrice)));
  }
  if (p.state === "gone") return el("span", { class: "tag tag--gone tag--row" }, "Zniknęło");
  return null;
}

const AGE_RAMP = [[7, "#a9cc00"], [30, "#7d9a3a"], [90, "#b88a5a"], [Infinity, "#9aa0a6"]];
function ageCell(days) {
  const color = AGE_RAMP.find(([max]) => days <= max)[1];
  const w = `${Math.max(4, Math.min(100, (days / 90) * 100))}%`;
  return el("div", { class: "age", title: days === 0 ? "Pierwszy raz widziane dziś" : `${daysLabel(days)} na rynku` },
    el("div", { class: "age__bar" }, el("div", { class: "age__fill", style: `--age-w:${w};--age-color:${color}` })),
    el("span", { class: "age__days" }, daysLabel(days)));
}

function money(value, unit) {
  return value == null
    ? el("span", { class: "missing" }, "brak")
    : [fmt.format(value), el("small", {}, unit)];
}

function row(p, i, openId) {
  const starBtn = el("button", {
    type: "button", class: "icon-btn star", "data-star": p.id,
    "aria-pressed": String(stars.has(p.id)), "aria-label": `Ulubione: ${p.miejscowosc}`,
  }, icon("star"));
  const noteBtn = el("button", {
    type: "button", class: "icon-btn note-btn", "data-note": p.id,
    "aria-expanded": String(openId === p.id), "aria-controls": `detail-${p.id}`,
    "aria-label": `Notatka i historia ceny: ${p.miejscowosc}`,
  }, icon("note"));

  const tr = el("tr", { class: `row${p.state === "gone" ? " is-gone" : ""}`, "data-id": p.id },
    el("td", { class: "c-star" }, starBtn),
    el("td", { class: "c-state" }, stateTag(p, i)),
    el("td", { class: "c-place" }, el("span", { class: "place" }, p.miejscowosc), el("span", { class: "section" }, p.odcinek)),
    el("td", { class: "c-title" },
      el("span", { class: "title" }, el("a", { href: p.url, target: "_blank", rel: "noopener" }, p.title, icon("out"))),
      el("span", { class: "source" }, p.zrodlo)),
    el("td", { class: "c-num c-price" }, el("span", { class: "price" }, ...[money(p.cena_pln, "zł")].flat())),
    el("td", { class: "c-num" }, el("span", { class: "num" }, ...[money(p.cena_za_m2, "zł")].flat())),
    el("td", { class: "c-num" }, el("span", { class: "num" }, ...[money(p.powierzchnia_m2, "m²")].flat())),
    el("td", { class: "c-age" }, ageCell(p.days)),
    el("td", { class: "c-note" }, el("div", { class: "note-cell" }, el("span", { class: "note-text" }, notes[p.id] ?? ""), noteBtn)),
  );
  return openId === p.id ? [tr, detailRow(p)] : [tr];
}

function detailRow(p) {
  const textarea = el("textarea", { id: `note-${p.id}`, "data-note-input": p.id, placeholder: "np. dzwoniłem, właściciel zejdzie do 180 tys." });
  textarea.value = notes[p.id] ?? "";
  const history = el("ol", { class: "history" }, ...(p.prices ?? []).map(([d, price], idx, arr) => {
    const prev = idx ? arr[idx - 1][1] : null;
    const delta = prev == null ? null : price - prev;
    return el("li", {},
      el("time", { datetime: d }, shortDate.format(new Date(d))),
      el("b", {}, `${fmt.format(price)} zł`),
      delta ? el("span", { class: delta < 0 ? "down" : "up" }, `${delta < 0 ? "−" : "+"}${fmt.format(Math.abs(delta))}`) : null);
  }));
  const seen = p.active
    ? `Na rynku od ${shortDate.format(new Date(p.listed))}`
    : `Widziane ${shortDate.format(new Date(p.first_seen))} – ${shortDate.format(new Date(p.last_seen))}`;
  return el("tr", { class: "detail", id: `detail-${p.id}` },
    el("td", { colspan: "9" },
      el("div", { class: "detail__grid" },
        el("div", {},
          el("label", { for: `note-${p.id}` }, "Twoja notatka"),
          textarea,
          el("div", { class: "detail__saved", "data-saved": p.id, "aria-live": "polite" })),
        el("div", {},
          el("label", {}, "Historia ceny"),
          (p.prices ?? []).length ? history : el("p", { class: "missing" }, "Brak ceny w ogłoszeniu."),
          el("p", { class: "meta-line" }, `${seen} · ${p.zrodlo}`)))));
}

// ── filtering & sorting ──────────────────────────────────────────────────
const STATE_RANK = { new: 0, cheaper: 1, "": 2, gone: 3 };
const SORTS = {
  state: (a, b) => STATE_RANK[a.state] - STATE_RANK[b.state] || b.first_seen.localeCompare(a.first_seen),
  place: (a, b) => a.miejscowosc.localeCompare(b.miejscowosc, "pl"),
  price: (a, b) => a.cena_pln - b.cena_pln,
  ppm: (a, b) => a.cena_za_m2 - b.cena_za_m2,
  area: (a, b) => a.powierzchnia_m2 - b.powierzchnia_m2,
  age: (a, b) => a.days - b.days,
};
const NUMERIC = new Set(["price", "ppm", "area"]);

function readFilters(form) {
  const f = new FormData(form);
  return {
    q: (f.get("q") || "").trim().toLocaleLowerCase("pl"),
    sources: new Set(f.getAll("source")),
    odcinek: f.get("odcinek") || "",
    maxPrice: Number(f.get("maxPrice")) || 0,
    minArea: Number(f.get("minArea")) || 0,
    onlyStarred: f.has("onlyStarred"),
    showGone: f.has("showGone"),
  };
}

function applyFilters(plots, f, quick) {
  return plots.filter((p) => {
    if (quick === "new" && p.state !== "new") return false;
    if (quick === "cheaper" && p.state !== "cheaper") return false;
    if (quick === "gone" && !p.goneRecently) return false;
    if (!quick && p.state === "gone" && !f.showGone) return false;
    if (!f.sources.has(p.zrodlo)) return false;
    if (f.odcinek && p.odcinek !== f.odcinek) return false;
    if (f.maxPrice && p.cena_pln != null && p.cena_pln > f.maxPrice) return false;
    if (f.minArea && p.powierzchnia_m2 != null && p.powierzchnia_m2 < f.minArea) return false;
    if (f.onlyStarred && !stars.has(p.id)) return false;
    if (f.q && !p.search.includes(f.q) && !(notes[p.id] ?? "").toLocaleLowerCase("pl").includes(f.q)) return false;
    return true;
  });
}

function sortPlots(plots, { key, dir }) {
  const cmp = SORTS[key];
  const sign = dir === "desc" ? -1 : 1;
  return [...plots].sort((a, b) => {
    // missing numbers always sink to the bottom, whatever the direction
    if (NUMERIC.has(key)) {
      const field = { price: "cena_pln", ppm: "cena_za_m2", area: "powierzchnia_m2" }[key];
      if (a[field] == null || b[field] == null) return (a[field] == null) - (b[field] == null);
    }
    return sign * cmp(a, b) || SORTS.state(a, b);
  });
}

// ── app ──────────────────────────────────────────────────────────────────
async function main() {
  const form = $("#filters");
  const tbody = $("#rows");
  const table = $("#plots");

  let data;
  try {
    const res = await fetch(DATA_URL, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    $("#meta").textContent = "Nie udało się wczytać danych.";
    tbody.replaceChildren(el("tr", {}, el("td", { colspan: "9", class: "status" },
      `Nie udało się wczytać listy działek (${err.message}). Odśwież stronę za chwilę.`)));
    return;
  }

  const generated = new Date(data.generated);
  const generatedDay = data.generated.slice(0, 10);
  const baseline = visitBaseline(data.generated);
  const plots = enrich(data.listings, generatedDay, baseline);
  const active = plots.filter((p) => p.active);

  // header
  const goneCount = plots.length - active.length;
  $("#meta").textContent =
    `Dane z ${dateFmt.format(generated)}, ${timeFmt.format(generated)} · ${active.length} ${plural(active.length, "działka", "działki", "działek")} na rynku` +
    (goneCount ? ` · ${goneCount} ${plural(goneCount, "zniknęła", "zniknęły", "zniknęło")}` : "");
  $("#since-label").textContent = baseline ? `Od wizyty ${dateFmt.format(new Date(baseline))}` : "Z ostatniej nocy";
  const counts = {
    new: plots.filter((p) => p.state === "new").length,
    cheaper: plots.filter((p) => p.state === "cheaper").length,
    gone: plots.filter((p) => p.goneRecently).length,
  };
  for (const [k, n] of Object.entries(counts)) {
    $(`#count-${k}`).textContent = n;
    const btn = $(`[data-quick="${k}"]`);
    btn.disabled = n === 0;
    btn.setAttribute("aria-pressed", "false");
  }
  $("#since").hidden = false;

  // filter controls from data
  const bySource = Object.groupBy(active, (p) => p.zrodlo);
  $("#sources").replaceChildren(...PORTALS.map((name) =>
    el("label", {}, el("input", { type: "checkbox", name: "source", value: name, checked: true }),
      name, el("span", { class: "chip__count" }, String(bySource[name]?.length ?? 0)))));
  const sections = [...new Set(plots.map((p) => p.odcinek))].sort((a, b) => a.localeCompare(b, "pl"));
  $("#odcinek").append(...sections.map((s) => el("option", { value: s }, s)));

  // restore personal filter state
  const saved = store.get("filters", null);
  if (saved) {
    for (const [name, value] of Object.entries(saved)) {
      const field = form.elements[name];
      if (!field) continue;
      if (name === "source") form.querySelectorAll('input[name="source"]').forEach((i) => { i.checked = value.includes(i.value); });
      else if (field.type === "checkbox") field.checked = value;
      else field.value = value;
    }
  }

  let sort = store.get("sort", { key: "state", dir: "asc" });
  let quick = null;
  let openId = null;
  let firstRender = true;

  function persistFilters() {
    const f = new FormData(form);
    store.set("filters", {
      q: f.get("q"), source: f.getAll("source"), odcinek: f.get("odcinek"),
      maxPrice: f.get("maxPrice"), minArea: f.get("minArea"),
      onlyStarred: f.has("onlyStarred"), showGone: f.has("showGone"),
    });
  }

  function render() {
    const shown = sortPlots(applyFilters(plots, readFilters(form), quick), sort);
    tbody.replaceChildren(...shown.flatMap((p, i) => row(p, i, openId)));
    $("#empty").hidden = shown.length > 0;
    table.classList.toggle("is-fresh", firstRender);
    firstRender = false;

    document.querySelectorAll("th[data-sort], th").forEach((th) => th.removeAttribute("aria-sort"));
    const th = $(`button[data-sort="${sort.key}"]`)?.closest("th");
    th?.setAttribute("aria-sort", sort.dir === "asc" ? "ascending" : "descending");

    const label = quick ? { new: "nowe", cheaper: "tańsze", gone: "zniknięte od ostatniej wizyty" }[quick] : null;
    const shownGone = shown.filter((p) => !p.active).length;
    const shownActive = shown.length - shownGone;
    $("#summary").textContent = label
      ? `Pokazano tylko ${label}: ${shown.length}.`
      : `Pokazano ${shownActive} z ${active.length} ${plural(active.length, "działki", "działek", "działek")} na rynku` +
        (shownGone ? ` oraz ${shownGone} ${plural(shownGone, "zniknięta", "zniknięte", "zniknięte")}.` : ".");
  }

  form.addEventListener("input", () => { persistFilters(); render(); });
  form.addEventListener("submit", (e) => e.preventDefault());
  form.addEventListener("reset", () => {
    setTimeout(() => {
      form.querySelectorAll('input[name="source"]').forEach((i) => { i.checked = true; });
      quick = null;
      document.querySelectorAll("[data-quick]").forEach((b) => b.setAttribute("aria-pressed", "false"));
      persistFilters(); render();
    });
  });
  $("#empty-reset").addEventListener("click", () => form.reset());

  $("#since").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-quick]");
    if (!btn) return;
    quick = quick === btn.dataset.quick ? null : btn.dataset.quick;
    document.querySelectorAll("[data-quick]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.quick === quick)));
    render();
  });

  $("thead").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-sort]");
    if (!btn) return;
    const key = btn.dataset.sort;
    sort = sort.key === key ? { key, dir: sort.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" };
    store.set("sort", sort);
    render();
  });

  tbody.addEventListener("click", (e) => {
    const star = e.target.closest("[data-star]");
    if (star) {
      const id = star.dataset.star;
      stars.has(id) ? stars.delete(id) : stars.add(id);
      store.set("stars", [...stars]);
      star.setAttribute("aria-pressed", String(stars.has(id)));
      if (readFilters(form).onlyStarred) render();
      return;
    }
    const noteBtn = e.target.closest("[data-note]");
    if (noteBtn) {
      openId = openId === noteBtn.dataset.note ? null : noteBtn.dataset.note;
      render();
      if (openId) document.getElementById(`note-${openId}`)?.focus();
    }
  });

  let saveTimer;
  tbody.addEventListener("input", (e) => {
    const input = e.target.closest("[data-note-input]");
    if (!input) return;
    const id = input.dataset.noteInput;
    const text = input.value.trim();
    text ? (notes[id] = text) : delete notes[id];
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      store.set("notes", notes);
      const preview = tbody.querySelector(`tr[data-id="${CSS.escape(id)}"] .note-text`);
      if (preview) preview.textContent = notes[id] ?? "";
      const saved = tbody.querySelector(`[data-saved="${CSS.escape(id)}"]`);
      if (saved) saved.textContent = "Zapisano w tej przeglądarce.";
    }, 400);
  });

  render();
}

main();
