/* 360° view: drag the watch left or right to turn it all the way around.
   Frames come from data-spin-data (one list per colour). Between two frames the next one fades in, so the turn looks
   smooth even with only a few frames. Picking a colour (or a colour thumbnail) switches the photo and the 360° view.
   Works with mouse, touch and pen; arrow keys turn it too. Without this script the page simply shows the photos. */
(() => {
  "use strict";
  const spin = document.querySelector("[data-spin]");
  if (!spin) return;
  let data;
  try { data = JSON.parse(spin.dataset.spinData); } catch (_) { return; }
  if (!data || !data.order || !data.order.length) return;

  const gallery = spin.closest("[data-gallery]");
  const main = gallery.querySelector("[data-gallery-main]");
  const toggle = gallery.querySelector("[data-spin-toggle]");
  const label = toggle && toggle.querySelector("[data-spin-label]");
  const imgA = spin.querySelector("[data-spin-a]");
  const imgB = spin.querySelector("[data-spin-b]");
  const needle = spin.querySelector("[data-spin-needle]");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const DEG_PER_PX = 0.55;
  const SIDES = ["Front", "Front right", "Right side", "Back", "Left side", "Front left"];

  let colour = data.order[0];
  let angle = 0;           // 0..360, 0 = front
  let velocity = 0;        // degrees per frame, for the glide after letting go
  let raf = 0;
  let intro = null;        // the automatic half-turn shown when the view opens
  const cache = {};

  const frames = () => data.colours[colour].frames;
  function preload(name) {
    if (cache[name]) return;
    cache[name] = data.colours[name].frames.map((src) => { const i = new Image(); i.decoding = "async"; i.src = src; return i; });
  }

  function render() {
    const list = frames();
    const n = list.length;
    const a = ((angle % 360) + 360) % 360;
    const pos = (a / 360) * n;
    const i = Math.floor(pos) % n;
    const j = (i + 1) % n;
    const t = pos - Math.floor(pos);
    if (imgA.getAttribute("src") !== list[i]) imgA.src = list[i];
    if (imgB.getAttribute("src") !== list[j]) imgB.src = list[j];
    // quick fade around the middle of each step: mostly one clean angle on screen, never a long see-through double image
    const fade = Math.min(1, Math.max(0, (t - 0.38) / 0.24));
    imgB.style.opacity = (fade * fade * (3 - 2 * fade)).toFixed(3);
    if (needle) needle.style.transform = `rotate(${a}deg)`;
    spin.setAttribute("aria-valuenow", String(Math.round(a)));
    spin.setAttribute("aria-valuetext", SIDES[Math.round((a / 360) * SIDES.length) % SIDES.length]);
  }

  function setColour(name, { keepAngle = true } = {}) {
    if (!data.colours[name]) return;
    colour = name;
    preload(name);
    const c = data.colours[name];
    if (c.main && main) {
      main.src = c.main;
      main.alt = `${main.alt.split(" — ")[0]} — ${name} edition`;
    }
    gallery.querySelectorAll("[data-gallery-thumb]").forEach((t) => {
      const on = t.dataset.color === name;
      if (t.dataset.color) { t.classList.toggle("is-active", on); t.setAttribute("aria-pressed", on ? "true" : "false"); }
    });
    if (!keepAngle) angle = 0;
    render();
  }

  // ---- open / close the 360° view
  function open(show) {
    spin.hidden = !show;
    if (toggle) {
      toggle.setAttribute("aria-pressed", show ? "true" : "false");
      if (label) label.textContent = show ? "Back to photos" : "360° View";
    }
    if (!show) return;
    preload(colour);
    render();
    spin.focus({ preventScroll: true });
    // a small automatic half-turn shows that it can be turned
    if (!reduce && !spin.classList.contains("has-turned") && window.gsap) {
      const s = { a: angle };
      intro = window.gsap.to(s, { a: angle + 120, duration: 1.1, ease: "power2.inOut", yoyo: true, repeat: 1, onUpdate: () => { angle = s.a; render(); } });
    }
  }
  if (toggle) toggle.addEventListener("click", () => open(spin.hidden));

  // ---- drag (mouse, touch, pen) with a short glide after letting go
  let dragging = false, lastX = 0, lastT = 0;
  spin.addEventListener("pointerdown", (e) => {
    if (e.button !== undefined && e.button !== 0) return;
    dragging = true; lastX = e.clientX; lastT = performance.now(); velocity = 0;
    cancelAnimationFrame(raf);
    if (intro) { intro.kill(); intro = null; }
    spin.setPointerCapture(e.pointerId);
    spin.classList.add("is-dragging", "has-turned");
  });
  spin.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const now = performance.now();
    const dx = e.clientX - lastX;
    angle -= dx * DEG_PER_PX;                  // drag right = the watch turns to show its right side
    velocity = (-dx * DEG_PER_PX) / Math.max(1, now - lastT) * 16;
    lastX = e.clientX; lastT = now;
    render();
  });
  const release = () => {
    if (!dragging) return;
    dragging = false;
    spin.classList.remove("is-dragging");
    if (reduce) return;
    const glide = () => {
      velocity *= 0.92;
      if (Math.abs(velocity) < 0.05) return;
      angle += velocity; render();
      raf = requestAnimationFrame(glide);
    };
    raf = requestAnimationFrame(glide);
  };
  spin.addEventListener("pointerup", release);
  spin.addEventListener("pointercancel", release);

  // ---- keyboard: arrows turn, Home faces the front, Escape closes
  spin.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 45 : 15;
    if (e.key === "ArrowLeft") angle -= step;
    else if (e.key === "ArrowRight") angle += step;
    else if (e.key === "Home") angle = 0;
    else if (e.key === "Escape") { open(false); if (toggle) toggle.focus(); return; }
    else return;
    e.preventDefault();
    spin.classList.add("has-turned");
    render();
  });

  // ---- colours: the colour buttons and the colour thumbnails both switch the watch
  document.addEventListener("change", (e) => {
    if (e.target.matches('input[name="color"]')) setColour(e.target.value);
  });
  gallery.querySelectorAll("[data-gallery-thumb][data-color]").forEach((t) => t.addEventListener("click", () => {
    const radio = document.querySelector(`input[name="color"][value="${CSS.escape(t.dataset.color)}"]`);
    if (radio && !radio.checked) { radio.checked = true; radio.dispatchEvent(new Event("change", { bubbles: true })); }
    else setColour(t.dataset.color);
  }));

  setColour(colour);
})();
