/* Velora Market — motion layer. Decoration only: the site works the same if this never runs. */
(function () {
  "use strict";

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || typeof window.gsap === "undefined") return;

  // Keep real time on slow machines: an entrance may drop frames, but content never waits behind it.
  gsap.ticker.lagSmoothing(0);

  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const onView = (trigger, start = "top 92%") => (window.ScrollTrigger ? { scrollTrigger: { trigger, start, once: true } } : {});
  const LIST_LIMIT = 14;  // long tables shouldn't take seconds to appear

  /* --------------------------------------------- navigation progress bar */
  const bar = document.createElement("div");
  bar.className = "route-bar";
  bar.setAttribute("aria-hidden", "true");
  document.body.appendChild(bar);
  let barTimer = null;

  function startBar() {
    clearTimeout(barTimer);
    gsap.killTweensOf(bar);
    gsap.fromTo(bar, { scaleX: 0, opacity: 1 }, { scaleX: .85, duration: 2.4, delay: .08, ease: "power2.out" });
    barTimer = setTimeout(resetBar, 8000);  // e.g. a link that turned out to be a file download
  }
  function resetBar() {
    clearTimeout(barTimer);
    gsap.killTweensOf(bar);
    gsap.to(bar, { opacity: 0, duration: .2 });
  }
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target === "_blank" || a.hasAttribute("download") || a.origin !== location.origin) return;
    if (a.pathname === location.pathname && a.search === location.search) return;  // same page or #anchor
    if (a.pathname.includes("/export")) return;
    startBar();
  });
  document.addEventListener("submit", (e) => { if (!e.defaultPrevented) startBar(); });
  window.addEventListener("pageshow", (e) => { if (e.persisted) resetBar(); });

  /* ------------------------------------------------------ headline reveal */
  $$(".page-head h1, .console-top h1, .auth__form h1, .confirm-hero h1").forEach((h) => {
    if (h.children.length || !h.textContent.trim()) return;
    const original = h.textContent;
    h.textContent = "";
    original.trim().split(/\s+/).forEach((word, i) => {
      if (i) h.append(" ");
      const outer = document.createElement("span"), inner = document.createElement("span");
      outer.className = "word";
      inner.textContent = word;
      outer.append(inner);
      h.append(outer);
    });
    gsap.from($$(".word > span", h), {
      yPercent: 115, duration: .75, stagger: .05, ease: "power4.out",
      onComplete: () => { h.textContent = original; },
    });
  });

  /* ------------------------------------------------- list and grid entrances */
  const GROUPS = [
    [".table tbody", "tr"], [".form-grid", "*"], [".choice-grid", "*"], [".kv", "*"],
    [".mini-lines", "li"], [".ranked", "*"], [".dash-grid", "*"], [".auth__form", "*"],
    [".footer__grid", "*"], [".pager", "*"],
  ];
  GROUPS.forEach(([parentSel, childSel]) => $$(`main ${parentSel}, .site-footer ${parentSel}`).forEach((parent) => {
    const kids = $$(`:scope > ${childSel}`, parent)
      .filter((el) => !el.matches("[data-reveal], [data-reveal-item], input[type=hidden]"))
      .slice(0, LIST_LIMIT);
    if (!kids.length) return;
    gsap.from(kids, { y: 14, opacity: 0, duration: .55, stagger: .04, ease: "power3.out", clearProps: "transform,opacity", ...onView(parent) });
  }));

  // Cards and tables the templates don't already animate
  $$("main .card, main .table-wrap, main .alert--info")
    .filter((el) => !el.closest("[data-reveal], .dash-grid, [data-reveal-item]") && !el.matches("[data-reveal]"))
    .forEach((el) => gsap.from(el, { y: 18, opacity: 0, duration: .6, ease: "power3.out", clearProps: "transform,opacity", ...onView(el) }));

  /* ---------------------------------------------------------- number count-up */
  $$(".stat__value").forEach((el) => {
    const parts = !el.children.length && el.textContent.trim().match(/^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$/s);
    if (!parts) return;
    const [, prefix, number, suffix] = parts;
    const original = el.textContent;
    const end = parseFloat(number.replace(/,/g, ""));
    const decimals = (number.split(".")[1] || "").length;
    const value = { n: 0 };
    el.textContent = prefix + (0).toFixed(decimals) + suffix;
    gsap.to(value, {
      n: end, duration: 1.2, ease: "power2.out", ...onView(el, "top 96%"),
      onUpdate: () => { el.textContent = prefix + value.n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix; },
      onComplete: () => { el.textContent = original; },
    });
  });

  /* ------------------------------------------------------------ image fade-in */
  $$("main img").forEach((img) => {
    if (img.complete || img.closest("[data-hero]")) return;
    img.classList.add("img-wait");
    const show = () => { img.classList.remove("img-wait"); img.classList.add("img-in"); };
    img.addEventListener("load", show, { once: true });
    img.addEventListener("error", show, { once: true });
  });

  /* -------------------------------------------------------------- mobile menu */
  $$("[data-open-drawer=mobile-nav]").forEach((btn) => btn.addEventListener("click", () => {
    const drawer = document.getElementById("mobile-nav");
    if (drawer) gsap.fromTo($$("a, .mobile-nav__label", drawer), { x: -14, opacity: 0 }, { x: 0, opacity: 1, duration: .4, stagger: .025, delay: .12, ease: "power3.out", clearProps: "transform,opacity" });
  }));

  /* ------------------------------------------------- order confirmed moment */
  const check = document.querySelector(".confirm-hero .check-anim");
  if (check) {
    const box = check.getBoundingClientRect();
    const style = getComputedStyle(document.documentElement);
    const colors = [style.getPropertyValue("--accent"), style.getPropertyValue("--saffron"), style.getPropertyValue("--line-2")];
    for (let i = 0; i < 28; i++) {
      const piece = document.createElement("span");
      piece.className = "confetti";
      piece.setAttribute("aria-hidden", "true");
      piece.style.background = colors[i % colors.length];
      piece.style.left = box.left + box.width / 2 + "px";
      piece.style.top = box.top + box.height / 2 + "px";
      document.body.appendChild(piece);
      const angle = gsap.utils.random(0, Math.PI * 2), reach = gsap.utils.random(90, 220);
      gsap.to(piece, {
        x: Math.cos(angle) * reach, y: Math.sin(angle) * reach + 90, rotation: gsap.utils.random(-260, 260), opacity: 0,
        duration: gsap.utils.random(.9, 1.5), delay: .35, ease: "power3.out", onComplete: () => piece.remove(),
      });
    }
  }
})();
