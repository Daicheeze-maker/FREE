/* Velora Market — progressive enhancement. Every feature here also works without JS
   (forms post normally); scripts only add speed, feedback and motion. */
(function () {
  "use strict";

  const doc = document.documentElement;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hasGsap = typeof window.gsap !== "undefined" && !reduce;
  if (reduce) doc.classList.add("reduced-motion");
  if (!hasGsap) doc.classList.add("no-gsap");
  if (hasGsap && window.ScrollTrigger) gsap.registerPlugin(ScrollTrigger);

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const icons = (root) => { if (window.lucide) lucide.createIcons({ attrs: { "aria-hidden": "true" }, nameAttr: "data-lucide", root }); };

  async function post(url, data) {
    const res = await fetch(url, {
      method: "POST", body: data, credentials: "same-origin",
      headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    });
    let json = {};
    try { json = await res.json(); } catch (e) { json = { ok: false, error: "Something went wrong. Please try again." }; }
    json.status = res.status;
    return json;
  }

  /* ---------------------------------------------------------- icons */
  icons();

  /* ---------------------------------------------- image fallback */
  const placeholder = document.body.dataset.placeholder;
  document.addEventListener("error", (e) => {
    const img = e.target;
    if (img.tagName === "IMG" && placeholder && !img.dataset.fallback) {
      img.dataset.fallback = "1";
      img.src = placeholder;
    }
  }, true);

  /* -------------------------------------------------------- theme */
  $$("[data-theme-toggle]").forEach((btn) => btn.addEventListener("click", () => {
    const next = doc.getAttribute("data-theme") === "dark" ? "light" : "dark";
    doc.classList.add("theme-anim");
    doc.setAttribute("data-theme", next);
    try { localStorage.setItem("velora-theme", next); } catch (e) {}
    setTimeout(() => doc.classList.remove("theme-anim"), 500);
  }));

  /* ------------------------------------------------------- header */
  const header = $("[data-header]");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* ---------------------------------------------------- dropdowns */
  const closeDropdowns = (except) => $$("[data-dropdown].is-open").forEach((d) => {
    if (d !== except) { d.classList.remove("is-open"); const b = d.querySelector("button[aria-expanded]"); if (b) b.setAttribute("aria-expanded", "false"); }
  });
  $$("[data-dropdown]").forEach((dd) => {
    const btn = dd.querySelector("button[aria-expanded]");
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !dd.classList.contains("is-open");
      closeDropdowns(dd);
      dd.classList.toggle("is-open", open);
      btn.setAttribute("aria-expanded", String(open));
      if (open && hasGsap) {
        const items = dd.querySelectorAll(".mega-item, .account-panel a, .currency-opt");
        gsap.fromTo(items, { y: 6, opacity: 0 }, { y: 0, opacity: 1, duration: .3, stagger: .025, ease: "power2.out" });
      }
    });
  });
  document.addEventListener("click", (e) => { if (!e.target.closest("[data-dropdown]")) closeDropdowns(); });

  /* ------------------------------------------------------ drawers */
  const scrim = $("[data-scrim]");
  let openDrawerEl = null, lastFocus = null;
  function openDrawer(el) {
    if (!el) return;
    if (openDrawerEl && openDrawerEl !== el) closeDrawer(true);
    lastFocus = document.activeElement;
    openDrawerEl = el;
    el.classList.add("is-open");
    el.setAttribute("aria-hidden", "false");
    scrim.hidden = false;
    requestAnimationFrame(() => scrim.classList.add("is-visible"));
    document.body.style.overflow = "hidden";
    $$(`[aria-controls="${el.id}"]`).forEach((b) => b.setAttribute("aria-expanded", "true"));
    const focusable = el.querySelector("button, a, input");
    if (focusable) setTimeout(() => focusable.focus({ preventScroll: true }), 60);
  }
  function closeDrawer(silent) {
    if (!openDrawerEl) return;
    const el = openDrawerEl;
    el.classList.remove("is-open");
    el.setAttribute("aria-hidden", "true");
    $$(`[aria-controls="${el.id}"]`).forEach((b) => b.setAttribute("aria-expanded", "false"));
    openDrawerEl = null;
    scrim.classList.remove("is-visible");
    setTimeout(() => { if (!openDrawerEl) scrim.hidden = true; }, 350);
    document.body.style.overflow = "";
    if (!silent && lastFocus) lastFocus.focus({ preventScroll: true });
  }
  $$("[data-open-drawer]").forEach((b) => b.addEventListener("click", () => openDrawer(document.getElementById(b.dataset.openDrawer))));
  document.addEventListener("click", (e) => { if (e.target.closest("[data-close-drawer]")) closeDrawer(); });
  if (scrim) scrim.addEventListener("click", () => closeDrawer());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeDrawer(); closeDropdowns(); closeModal(false); }
  });

  /* ------------------------------------------------------- toasts */
  const toastBox = $("[data-toasts]");
  function dismissToast(t) {
    if (!t.isConnected) return;
    if (hasGsap) gsap.to(t, { x: 40, opacity: 0, height: 0, marginTop: -10, paddingTop: 0, paddingBottom: 0, duration: .35, ease: "power2.in", onComplete: () => t.remove() });
    else t.remove();
  }
  function showToast(t) {
    t.querySelector(".toast__x")?.addEventListener("click", () => dismissToast(t));
    if (hasGsap) gsap.fromTo(t, { y: 24, opacity: 0, scale: .96 }, { y: 0, opacity: 1, scale: 1, duration: .5, ease: "back.out(1.6)" });
    setTimeout(() => dismissToast(t), t.classList.contains("toast--error") ? 7000 : 4500);
  }
  function toast(message, type = "success") {
    const t = document.createElement("div");
    t.className = `toast toast--${type}`;
    t.setAttribute("role", "status");
    const ic = type === "error" ? "circle-alert" : type === "info" ? "info" : "circle-check";
    t.innerHTML = `<i data-lucide="${ic}" class="ic"></i><span></span><button type="button" class="toast__x" aria-label="Dismiss">×</button>`;
    t.querySelector("span").textContent = message;
    toastBox.appendChild(t);
    icons(t);
    showToast(t);
  }
  $$("[data-flash]").forEach(showToast);
  window.veloraToast = toast;

  /* -------------------------------------------- confirm dialogs */
  const modal = $("#confirm-modal");
  let pendingForm = null;
  function closeModal(ok) {
    if (!modal || modal.hidden) return;
    const form = pendingForm;
    pendingForm = null;
    const done = () => { modal.hidden = true; if (ok && form) { form.dataset.confirmed = "1"; form.requestSubmit ? form.requestSubmit() : form.submit(); } };
    if (hasGsap) gsap.to(modal.firstElementChild, { scale: .95, opacity: 0, duration: .18, onComplete: done });
    else done();
  }
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form.matches("[data-confirm]") && !form.dataset.confirmed && modal) {
      e.preventDefault();
      pendingForm = form;
      $("#confirm-title").textContent = form.dataset.confirmTitle || "Are you sure?";
      $("#confirm-text").textContent = form.dataset.confirm;
      const ok = modal.querySelector("[data-modal-ok]");
      ok.className = "btn " + (form.hasAttribute("data-confirm-danger") ? "btn--danger" : "btn--dark");
      modal.hidden = false;
      if (hasGsap) gsap.fromTo(modal.firstElementChild, { y: 16, scale: .96, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: .35, ease: "back.out(1.7)" });
      ok.focus();
    }
  }, true);
  if (modal) {
    modal.querySelector("[data-modal-ok]").addEventListener("click", () => closeModal(true));
    modal.querySelector("[data-modal-cancel]").addEventListener("click", () => closeModal(false));
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(false); });
  }

  /* ------------------------- loading buttons / double-submit guard */
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (e.defaultPrevented || form.matches("[data-add-to-cart], [data-wishlist], [data-cart-ajax], [data-filters], [data-newsletter], [data-off-search]")) return;
    if (form.method.toLowerCase() !== "post") return;
    if (form.dataset.submitting) { e.preventDefault(); return; }
    form.dataset.submitting = "1";
    const btn = e.submitter || form.querySelector("button[type=submit], button:not([type])");
    if (btn) {
      btn.classList.add("is-loading");
      if (btn.dataset.loadingText) btn.textContent = btn.dataset.loadingText;
      // keep submitter's name/value (disabled buttons aren't submitted, so delay disabling)
      setTimeout(() => { btn.disabled = true; }, 0);
    }
  });
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) $$("form[data-submitting]").forEach((f) => { delete f.dataset.submitting; $$(".is-loading", f).forEach((b) => { b.classList.remove("is-loading"); b.disabled = false; }); });
  });

  /* ------------------------------------------------------------ cart */
  const cartDrawer = $("[data-cart-drawer]");
  const countEls = $$("[data-cart-count]");
  function setCount(n) {
    countEls.forEach((el) => {
      el.textContent = n;
      el.classList.toggle("is-empty", !n);
      if (hasGsap && n) gsap.fromTo(el, { scale: 1.6 }, { scale: 1, duration: .55, ease: "elastic.out(1, .45)" });
    });
    $$("[data-open-cart]").forEach((b) => b.setAttribute("aria-label", `Bag, ${n} items`));
  }
  function renderDrawer(html) {
    const body = $("[data-cart-drawer-body]");
    if (!body) return;
    body.innerHTML = html;
    icons(body);
    if (hasGsap) gsap.from(body.querySelectorAll(".cart-line"), { x: 24, opacity: 0, duration: .45, stagger: .05, ease: "power3.out" });
    const meter = body.querySelector(".ship-meter__fill");
    if (meter && hasGsap) gsap.from(meter, { width: 0, duration: .9, ease: "power3.out" });
  }
  async function loadDrawer() {
    try {
      const res = await fetch(cartDrawer.dataset.src, { headers: { "X-Requested-With": "fetch", "Accept": "application/json" }, credentials: "same-origin" });
      const json = await res.json();
      renderDrawer(json.drawer);
      setCount(json.count);
    } catch (e) {
      $("[data-cart-drawer-body]").innerHTML = '<p class="drawer__loading">Couldn\'t load your bag. <a href="/cart">Open the bag page</a>.</p>';
    }
  }
  $$("[data-open-cart]").forEach((a) => a.addEventListener("click", (e) => {
    if (!cartDrawer || e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    openDrawer(cartDrawer);
    loadDrawer();
  }));

  function flyToCart(fromImg) {
    const target = $("[data-open-cart]");
    if (!hasGsap || !fromImg || !target) return;
    const a = fromImg.getBoundingClientRect(), b = target.getBoundingClientRect();
    const ghost = fromImg.cloneNode();
    Object.assign(ghost.style, { position: "fixed", left: a.left + "px", top: a.top + "px", width: a.width + "px", height: a.height + "px", objectFit: "cover", borderRadius: "14px", zIndex: 150, pointerEvents: "none" });
    document.body.appendChild(ghost);
    gsap.to(ghost, {
      left: b.left + b.width / 2 - 12, top: b.top + b.height / 2 - 12, width: 24, height: 24, borderRadius: "50%", opacity: .4,
      duration: .75, ease: "power3.in", onComplete: () => ghost.remove(),
    });
  }

  document.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-add-to-cart]");
    if (!form) return;
    e.preventDefault();
    const btn = form.querySelector("button[type=submit]");
    if (btn.classList.contains("is-loading")) return;
    btn.classList.add("is-loading");
    const json = await post(form.action, new FormData(form)).catch(() => ({ ok: false, error: "Network error — please try again." }));
    btn.classList.remove("is-loading");
    if (json.ok) {
      const card = form.closest(".pcard, .pdp");
      flyToCart(card && card.querySelector("img"));
      setCount(json.count);
      renderDrawer(json.drawer);
      setTimeout(() => openDrawer(cartDrawer), hasGsap ? 520 : 0);
      if (hasGsap) gsap.fromTo(btn, { scale: .94 }, { scale: 1, duration: .4, ease: "back.out(2)" });
    } else {
      toast(json.error || "Couldn't add that item.", "error");
    }
  });

  // Drawer quantity & remove (delegated, forms rendered by server)
  document.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-cart-ajax]");
    if (!form) return;
    e.preventDefault();
    const fd = new FormData(form);
    if (e.submitter && e.submitter.name) fd.set(e.submitter.name, e.submitter.value);
    form.closest(".cart-line")?.style.setProperty("opacity", ".5");
    const json = await post(form.action, fd).catch(() => ({ ok: false }));
    if (json.drawer !== undefined) { renderDrawer(json.drawer); setCount(json.count); }
    if (json.message && json.ok) toast(json.message, "info");
    if (!json.ok) toast(json.error || "Couldn't update your bag.", "error");
  });

  /* --------------------------------------------------------- wishlist */
  document.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-wishlist]");
    if (!form) return;
    e.preventDefault();
    const btn = e.submitter || form.querySelector("button");
    const json = await post(form.action, new FormData(form)).catch(() => ({ ok: false, error: "Network error." }));
    if (json.status === 401 && json.login) { toast(json.error, "info"); setTimeout(() => { window.location = json.login; }, 900); return; }
    if (!json.ok) { toast(json.error || "Couldn't update wishlist.", "error"); return; }
    const linked = form.id ? $$(`.wish-btn[form="${form.id}"]`) : [];
    $$(`form[action="${form.getAttribute("action")}"] .wish-btn`).concat(linked).forEach((b) => {
      b.classList.toggle("is-saved", json.saved);
      b.setAttribute("aria-pressed", String(json.saved));
    });
    if (hasGsap) {
      gsap.fromTo(btn, { scale: .7 }, { scale: 1, duration: .6, ease: "elastic.out(1.1, .4)" });
      if (json.saved) burst(btn);
    }
    toast(json.message, "success");
    if (!json.saved && form.closest("[data-wishlist-page]")) {
      const card = form.closest(".pcard");
      if (hasGsap) gsap.to(card, { opacity: 0, scale: .9, duration: .35, onComplete: () => card.remove() }); else card.remove();
    }
  });
  function burst(el) {
    const r = el.getBoundingClientRect();
    for (let i = 0; i < 8; i++) {
      const p = document.createElement("span");
      Object.assign(p.style, { position: "fixed", left: r.left + r.width / 2 + "px", top: r.top + r.height / 2 + "px", width: "6px", height: "6px", borderRadius: "50%", background: i % 2 ? "#D9544A" : "#E39A35", zIndex: 150, pointerEvents: "none" });
      document.body.appendChild(p);
      const ang = (Math.PI * 2 * i) / 8;
      gsap.to(p, { x: Math.cos(ang) * 26, y: Math.sin(ang) * 26, opacity: 0, scale: .4, duration: .6, ease: "power2.out", onComplete: () => p.remove() });
    }
  }

  /* --------------------------------------------------- qty steppers */
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-qty-step]");
    if (!b) return;
    const wrap = b.closest(".qty");
    const input = wrap.querySelector("input");
    const min = parseInt(input.min || "0", 10), max = parseInt(input.max || "99", 10);
    const v = Math.min(max, Math.max(min, (parseInt(input.value, 10) || 0) + parseInt(b.dataset.qtyStep, 10)));
    if (b.type !== "submit") { e.preventDefault(); input.value = v; input.dispatchEvent(new Event("change", { bubbles: true })); }
  });
  $$("[data-autosubmit]").forEach((form) => form.addEventListener("change", () => {
    clearTimeout(form._t);
    form._t = setTimeout(() => form.requestSubmit ? form.requestSubmit() : form.submit(), 350);
  }));

  /* ------------------------------------------------------------- tabs */
  $$("[data-tabs]").forEach((tabs) => {
    const list = tabs.querySelector("[role=tablist]");
    const btns = $$("[role=tab]", tabs);
    const ink = tabs.querySelector(".tabs__ink");
    const moveInk = (b) => { if (ink) { ink.style.width = b.offsetWidth + "px"; ink.style.transform = `translateX(${b.offsetLeft}px)`; } };
    function select(b, focus) {
      btns.forEach((x) => {
        const on = x === b;
        x.setAttribute("aria-selected", String(on));
        x.tabIndex = on ? 0 : -1;
        const panel = document.getElementById(x.getAttribute("aria-controls"));
        panel.hidden = !on;
        if (on && hasGsap) gsap.fromTo(panel, { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: .4, ease: "power2.out" });
      });
      moveInk(b);
      if (focus) b.focus();
    }
    btns.forEach((b, i) => {
      b.addEventListener("click", () => select(b));
      b.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          select(btns[(i + (e.key === "ArrowRight" ? 1 : -1) + btns.length) % btns.length], true);
        }
      });
    });
    const current = btns.find((b) => b.getAttribute("aria-selected") === "true") || btns[0];
    requestAnimationFrame(() => moveInk(current));
    window.addEventListener("resize", () => moveInk(btns.find((b) => b.getAttribute("aria-selected") === "true")));
    if (list) list.addEventListener("scroll", () => moveInk(btns.find((b) => b.getAttribute("aria-selected") === "true")));
  });

  /* ---------------------------------------------------------- gallery */
  $$("[data-gallery]").forEach((g) => {
    const main = g.querySelector("[data-gallery-main]");
    $$("[data-gallery-thumb]", g).forEach((t) => t.addEventListener("click", () => {
      $$("[data-gallery-thumb]", g).forEach((x) => { x.classList.remove("is-active"); x.setAttribute("aria-pressed", "false"); });
      t.classList.add("is-active");
      t.setAttribute("aria-pressed", "true");
      const swap = () => { main.src = t.dataset.src; main.alt = t.dataset.alt; delete main.dataset.fallback; };
      if (hasGsap) gsap.to(main, { opacity: 0, scale: 1.02, duration: .18, onComplete: () => { swap(); gsap.to(main, { opacity: 1, scale: 1, duration: .35 }); } });
      else swap();
    }));
  });

  /* ------------------------------------------------- scroller arrows */
  $$("[data-scroller-prev], [data-scroller-next]").forEach((b) => b.addEventListener("click", () => {
    const s = document.getElementById(b.getAttribute("aria-controls"));
    const dir = b.hasAttribute("data-scroller-next") ? 1 : -1;
    s.scrollBy({ left: dir * (s.clientWidth * .8), behavior: reduce ? "auto" : "smooth" });
  }));

  /* ------------------------------------------ catalog AJAX filtering */
  const filterForm = $("[data-filters]");
  const results = $("[data-results]");
  async function loadResults(url, push) {
    if (!results) { window.location = url; return; }
    results.classList.add("is-loading");
    results.setAttribute("aria-busy", "true");
    try {
      const res = await fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
      if (!res.ok) throw new Error(res.status);
      const html = await res.text();
      results.querySelector("[data-results-body]").innerHTML = html;
      icons(results);
      if (push) history.pushState({ catalog: true }, "", url);
      revealCards(results);
      const count = results.querySelector("[data-result-count]");
      const live = $("[data-results-live]");
      if (count && live) live.textContent = count.textContent;
    } catch (e) {
      toast("Couldn't load products. Showing the full page instead.", "error");
      window.location = url;
    } finally {
      results.classList.remove("is-loading");
      results.removeAttribute("aria-busy");
    }
  }
  if (filterForm) {
    const go = () => {
      const params = new URLSearchParams(new FormData(filterForm));
      for (const [k, v] of Array.from(params.entries())) if (!v) params.delete(k);
      loadResults(filterForm.action + (params.toString() ? "?" + params : ""), true);
    };
    filterForm.addEventListener("change", (e) => { if (e.target.type !== "number") go(); });
    filterForm.addEventListener("submit", (e) => { e.preventDefault(); go(); if (window.innerWidth < 960) closeFilters(); });
    $$("[data-sort]").forEach((s) => s.addEventListener("change", () => { filterForm.querySelector("[name=sort]").value = s.value; go(); }));
    window.addEventListener("popstate", () => loadResults(location.href, false));
  }
  if (results) {
    results.addEventListener("click", (e) => {
      const a = e.target.closest(".pager a, [data-results-link]");
      if (!a) return;
      e.preventDefault();
      loadResults(a.href, true);
      window.scrollTo({ top: results.getBoundingClientRect().top + window.scrollY - 120, behavior: reduce ? "auto" : "smooth" });
    });
  }
  const filtersPanel = $("[data-filters-panel]");
  function closeFilters() { if (filtersPanel) { filtersPanel.classList.remove("is-open"); scrim.classList.remove("is-visible"); setTimeout(() => (scrim.hidden = true), 300); document.body.style.overflow = ""; } }
  $$("[data-open-filters]").forEach((b) => b.addEventListener("click", () => {
    filtersPanel.classList.add("is-open"); scrim.hidden = false; requestAnimationFrame(() => scrim.classList.add("is-visible")); document.body.style.overflow = "hidden";
  }));
  $$("[data-close-filters]").forEach((b) => b.addEventListener("click", closeFilters));
  if (scrim) scrim.addEventListener("click", closeFilters);

  /* ------------------------------------------- Open Food Facts search */
  const offForm = $("[data-off-search]");
  if (offForm) {
    const box = $("[data-off-results]");
    offForm.addEventListener("submit", async (e) => {
      const q = offForm.querySelector("[name=q]").value.trim();
      if (q.length < 2) return;
      e.preventDefault();
      const url = offForm.action + "?q=" + encodeURIComponent(q);
      box.innerHTML = $("#off-skeleton").innerHTML;
      box.setAttribute("aria-busy", "true");
      const btn = offForm.querySelector("button");
      btn.classList.add("is-loading");
      try {
        const res = await fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
        box.innerHTML = await res.text();
        icons(box);
        history.replaceState(null, "", url);
        if (hasGsap) gsap.from(box.querySelectorAll(".off-card"), { y: 18, opacity: 0, duration: .5, stagger: .04, ease: "power3.out" });
      } catch (err) {
        box.innerHTML = '<div class="alert alert--error">Search failed — check your connection and try again.</div>';
      } finally {
        btn.classList.remove("is-loading");
        box.removeAttribute("aria-busy");
      }
    });
  }

  /* -------------------------------------------------------- newsletter */
  $$("[data-newsletter]").forEach((form) => form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = form.querySelector(".newsletter__msg");
    const btn = form.querySelector("button");
    const email = form.querySelector("[name=email]");
    msg.classList.remove("is-error");
    if (!email.checkValidity()) { msg.textContent = "Enter a valid email address."; msg.classList.add("is-error"); email.focus(); return; }
    btn.classList.add("is-loading");
    const json = await post(form.action, new FormData(form)).catch(() => ({ ok: false, error: "Network error — please try again." }));
    btn.classList.remove("is-loading");
    msg.textContent = json.ok ? json.message : json.error;
    msg.classList.toggle("is-error", !json.ok);
    if (json.ok) { form.reset(); if (hasGsap) gsap.fromTo(msg, { y: 6, opacity: 0 }, { y: 0, opacity: 1, duration: .4 }); }
  }));

  /* --------------------------------------------- demo login quick-fill */
  $$("[data-demo-login]").forEach((b) => b.addEventListener("click", () => {
    const f = b.closest("main").querySelector("form");
    f.querySelector("[name=email]").value = b.dataset.email;
    f.querySelector("[name=password]").value = b.dataset.password;
    f.querySelector("[name=password]").focus();
    if (hasGsap) gsap.fromTo(f.querySelectorAll(".input"), { backgroundColor: "rgba(227,154,53,.25)" }, { backgroundColor: "rgba(0,0,0,0)", duration: 1, clearProps: "backgroundColor" });
  }));

  /* ================================================== ANIMATIONS */
  function revealCards(root) {
    const cards = $$("[data-reveal-item]", root || document);
    if (!hasGsap || !cards.length) return;
    gsap.set(cards, { y: 26, opacity: 0 });
    if (window.ScrollTrigger) {
      ScrollTrigger.batch(cards, {
        start: "top 92%", once: true,
        onEnter: (batch) => gsap.to(batch, { y: 0, opacity: 1, duration: .7, stagger: .07, ease: "power3.out", overwrite: true }),
      });
    } else gsap.to(cards, { y: 0, opacity: 1, stagger: .05 });
  }

  if (hasGsap) {
    // Hero entrance
    const hero = $("[data-hero]");
    if (hero) {
      const tl = gsap.timeline({ defaults: { ease: "power4.out" } });
      tl.from(hero.querySelectorAll(".hero__title .line > span"), { yPercent: 110, duration: 1.05, stagger: .1 })
        .from(hero.querySelectorAll("[data-hero-fade]"), { y: 18, opacity: 0, duration: .8, stagger: .08 }, "-=.7")
        .from(hero.querySelector(".hero__photo"), { clipPath: "inset(100% 0 0 0 round 20px)", duration: 1.1, ease: "power3.inOut" }, .1)
        .from(hero.querySelector(".hero__block"), { scale: .6, rotate: -8, opacity: 0, duration: 1 }, .35)
        .from(hero.querySelectorAll(".hero__card, .hero__chip"), { y: 30, opacity: 0, scale: .9, duration: .8, stagger: .12, ease: "back.out(1.6)" }, .7)
        .from(hero.querySelectorAll(".hero__dots, .hero__ring"), { opacity: 0, scale: .4, duration: .6, stagger: .08 }, .9);
      gsap.to(hero.querySelector(".hero__card"), { y: -12, duration: 3.2, ease: "sine.inOut", yoyo: true, repeat: -1, delay: 1.6 });
      gsap.to(hero.querySelector(".hero__chip--rating"), { y: 10, duration: 2.8, ease: "sine.inOut", yoyo: true, repeat: -1, delay: 1.8 });
      gsap.to(hero.querySelector(".hero__chip--ship"), { y: -8, x: 4, duration: 3.6, ease: "sine.inOut", yoyo: true, repeat: -1, delay: 2 });
      if (window.ScrollTrigger) gsap.to(hero.querySelector(".hero__photo img"), { yPercent: 8, scale: 1.08, ease: "none", scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true } });
    } else {
      gsap.from("main > *:first-child", { y: 14, opacity: 0, duration: .6, ease: "power2.out" });
    }

    // Section reveals
    $$("[data-reveal]").forEach((el) => {
      gsap.fromTo(el, { y: 36, opacity: 0 }, { y: 0, opacity: 1, duration: .9, ease: "power3.out", scrollTrigger: window.ScrollTrigger ? { trigger: el, start: "top 88%", once: true } : undefined });
    });

    // Dashboard bars / trackers / meters
    $$(".chart").forEach((c) => gsap.from(c.querySelectorAll("[data-chart-bar]"), { scaleY: 0, duration: .9, stagger: .025, ease: "power3.out", scrollTrigger: window.ScrollTrigger ? { trigger: c, start: "top 92%", once: true } : undefined }));
    $$(".meter span, .dist__bar span").forEach((m) => gsap.from(m, { width: 0, duration: 1, ease: "power3.out", scrollTrigger: window.ScrollTrigger ? { trigger: m, start: "top 95%", once: true } : undefined }));
    $$("[data-tracker]").forEach((t) => {
      const tl = gsap.timeline({ scrollTrigger: window.ScrollTrigger ? { trigger: t, start: "top 90%", once: true } : undefined });
      tl.from(t.querySelector(".tracker__fill"), { scaleX: 0, duration: 1.2, ease: "power3.inOut" })
        .from(t.querySelectorAll(".tracker__dot"), { scale: .4, opacity: 0, duration: .45, stagger: .14, ease: "back.out(2)" }, 0)
        .from(t.querySelectorAll(".tracker__label, .tracker__time"), { y: 6, opacity: 0, duration: .4, stagger: .05 }, .2);
    });
    $$("[data-steps]").forEach((s) => gsap.from(s.querySelector(".steps__fill"), { scaleX: 0, duration: 1.1, ease: "power3.inOut", delay: .2 }));
    $$("[data-count]").forEach((el) => {
      const end = parseFloat(el.dataset.count);
      if (!isFinite(end)) return;
      const prefix = el.dataset.prefix || "", decimals = parseInt(el.dataset.decimals || "0", 10);
      const obj = { v: 0 };
      gsap.to(obj, { v: end, duration: 1.4, ease: "power2.out", scrollTrigger: window.ScrollTrigger ? { trigger: el, start: "top 95%", once: true } : undefined,
        onUpdate: () => { el.textContent = prefix + obj.v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }); } });
    });
    $$("[data-empty] .empty__art").forEach((a) => gsap.fromTo(a, { scale: .6, opacity: 0, rotate: -10 }, { scale: 1, opacity: 1, rotate: 0, duration: .9, ease: "elastic.out(1, .5)" }));
    $$("[data-empty] .empty__art .ic").forEach((i) => gsap.to(i, { y: -6, duration: 1.6, ease: "sine.inOut", yoyo: true, repeat: -1 }));
  }
  revealCards();
})();
