/* Pin-your-location map for address forms: Leaflet + OpenStreetMap tiles.
   Click the map / drag the pin / "Use my current location" -> the server (Mapbox) turns the spot into an address
   and the form fields are filled in. Picking a search suggestion moves the pin. Works without any of it:
   if the map can't load, the form is just the normal fields. */
(() => {
  "use strict";
  const box = document.querySelector("[data-pin-map]");
  if (!box) return;
  const form = box.closest("[data-address-form]") || document;
  const canvas = box.querySelector("[data-pin-canvas]");
  const hint = box.querySelector("[data-pin-hint]");
  const say = (t) => { hint.textContent = t; };
  const field = (suffix) => form.querySelector(`[name$="${suffix}"]`);
  const hide = () => { box.hidden = true; };
  if (typeof window.L === "undefined") { hide(); return; }

  const L = window.L;
  L.Icon.Default.imagePath = box.dataset.icons;
  const start = [parseFloat(box.dataset.lat), parseFloat(box.dataset.lng)];
  let map, marker, tiles, loaded = 0, failed = 0, seq = 0;
  try {
    map = L.map(canvas, { scrollWheelZoom: false }).setView(start, 12);
  } catch (e) { hide(); return; }
  tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
  }).addTo(map);
  tiles.on("tileload", () => { loaded++; });
  tiles.on("tileerror", () => { failed++; if (!loaded && failed >= 4) { map.remove(); hide(); } });
  map.on("click", () => map.scrollWheelZoom.enable());
  map.on("mouseout", () => map.scrollWheelZoom.disable());

  const fill = (r) => {
    for (const [name, val] of [["line1", r.line1], ["city", r.city], ["region", r.region], ["postal_code", r.postal_code], ["country", r.country]]) {
      const el = field(name);
      if (el && val) { el.value = val; el.dispatchEvent(new Event("input", { bubbles: true })); }
    }
  };

  async function lookup(lat, lng) {
    const mine = ++seq;
    say("Finding the address at this spot…");
    try {
      const res = await fetch(`${box.dataset.reverse}?lat=${lat.toFixed(6)}&lng=${lng.toFixed(6)}`, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
      const data = await res.json();
      if (mine !== seq) return;
      if (data.ok && data.result) { fill(data.result); say("Address filled in from your pin: " + data.result.label + ". Check it, then add your unit or building."); }
      else if (data.ok) say("Pinned. We couldn't find a street address here, so please type it in.");
      else if (data.error === "no_token") say("Pinned. Address lookup isn't switched on yet (the store needs its Mapbox token), so please type the address.");
      else say("Pinned. Address lookup is unavailable right now, so please type the address.");
    } catch (e) { if (mine === seq) say("Pinned. Address lookup is unavailable right now, so please type the address."); }
  }

  function place(lat, lng, look) {
    if (!marker) {
      marker = L.marker([lat, lng], { draggable: true, title: "Your delivery spot", alt: "Delivery pin" }).addTo(map);
      marker.on("dragend", () => { const p = marker.getLatLng(); lookup(p.lat, p.lng); });
    } else marker.setLatLng([lat, lng]);
    if (look) lookup(lat, lng);
  }

  map.on("click", (e) => { place(e.latlng.lat, e.latlng.lng, true); });

  const locate = box.querySelector("[data-pin-locate]");
  if (locate) locate.addEventListener("click", () => {
    if (!navigator.geolocation) { say("Your browser can't share its location. Click the map instead."); return; }
    say("Asking your device for your location…");
    navigator.geolocation.getCurrentPosition((pos) => {
      const { latitude: la, longitude: lo } = pos.coords;
      map.setView([la, lo], 17);
      place(la, lo, true);
    }, () => say("We couldn't get your location (permission was declined?). Click the map instead."), { enableHighAccuracy: true, timeout: 10000 });
  });

  // A suggestion picked in the search box moves the pin to that address
  form.addEventListener("address:picked", (e) => {
    const { lat, lng } = e.detail || {};
    if (typeof lat === "number" && typeof lng === "number") { map.setView([lat, lng], 17); place(lat, lng, false); say("Pin moved to the address you chose."); }
  });
  // The map sits in a form that can be hidden at first: fix its size when it appears
  new ResizeObserver(() => map.invalidateSize()).observe(canvas);
})();
