/* Address suggestions (Mapbox, through this server). Works on any [data-address-search="<url>"] container:
   typing in the street field shows matches; picking one fills street, city, province, postal code and country.
   Without suggestions (no token, offline) the fields are plain inputs, exactly as before. */
(() => {
  "use strict";
  document.querySelectorAll("[data-address-search]").forEach((box) => {
    const url = box.dataset.addressSearch;
    const input = box.querySelector('input[name$="line1"]');
    if (!url || !input) return;
    const pick = (suffix) => box.querySelector(`[name$="${suffix}"]`);
    const field = input.closest(".field") || input.parentElement;
    field.style.position = "relative";
    input.setAttribute("autocomplete", "off");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");

    const list = document.createElement("ul");
    list.className = "addr-suggest";
    list.id = "addr-suggest-" + Math.random().toString(36).slice(2, 8);
    list.setAttribute("role", "listbox");
    list.hidden = true;
    input.setAttribute("aria-controls", list.id);
    field.appendChild(list);

    let results = [], active = -1, timer = null, ctl = null;
    const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; };
    const mark = (i) => {
      active = i;
      [...list.children].forEach((li, n) => li.setAttribute("aria-selected", n === i ? "true" : "false"));
    };
    const choose = (r) => {
      input.value = r.line1;
      for (const [name, val] of [["city", r.city], ["region", r.region], ["postal_code", r.postal_code], ["country", r.country]]) {
        const el = pick(name);
        if (el && val) { el.value = val; el.dispatchEvent(new Event("input", { bubbles: true })); }
      }
      close();
      const next = pick("line2") || pick("phone");
      if (next) next.focus();
    };
    const render = () => {
      list.textContent = "";
      results.forEach((r, i) => {
        const li = document.createElement("li");
        li.setAttribute("role", "option");
        li.textContent = r.label;
        li.addEventListener("mousedown", (e) => { e.preventDefault(); choose(r); });
        li.addEventListener("mousemove", () => mark(i));
        list.appendChild(li);
      });
      const credit = document.createElement("li");
      credit.className = "addr-suggest__credit";
      credit.setAttribute("aria-hidden", "true");
      credit.textContent = "Suggestions by Mapbox";
      list.appendChild(credit);
      list.hidden = !results.length;
      input.setAttribute("aria-expanded", results.length ? "true" : "false");
    };
    const search = async () => {
      const q = input.value.trim();
      if (q.length < 3) { results = []; close(); return; }
      if (ctl) ctl.abort();
      ctl = new AbortController();
      try {
        const res = await fetch(url + "?q=" + encodeURIComponent(q), { signal: ctl.signal, headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
        const data = await res.json();
        results = Array.isArray(data.results) ? data.results : [];
        render();
      } catch (e) { if (e.name !== "AbortError") { results = []; close(); } }
    };
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(search, 300); });
    input.addEventListener("keydown", (e) => {
      if (list.hidden) return;
      if (e.key === "ArrowDown") { e.preventDefault(); mark((active + 1) % results.length); }
      else if (e.key === "ArrowUp") { e.preventDefault(); mark((active - 1 + results.length) % results.length); }
      else if (e.key === "Enter" && active >= 0) { e.preventDefault(); choose(results[active]); }
      else if (e.key === "Escape") close();
    });
    input.addEventListener("blur", () => setTimeout(close, 120));
  });
})();
