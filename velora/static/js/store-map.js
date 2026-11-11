/* "Visit our store" map: Leaflet + OpenStreetMap tiles (free, no API key).
   Starts only when the map scrolls into view, and falls back to a plain address card
   if Leaflet or the tiles can't load (for example with no internet). */
(function () {
  "use strict";
  var el = document.getElementById("store-map");
  if (!el) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function fallback() {
    var loading = el.querySelector(".store-ad__loading");
    if (loading) loading.hidden = true;
    var box = el.querySelector(".store-ad__fallback");
    if (box) box.hidden = false;
    el.classList.add("is-fallback");
  }

  function start() {
    var lat = parseFloat(el.dataset.lat), lng = parseFloat(el.dataset.lng);
    if (typeof window.L === "undefined" || !isFinite(lat) || !isFinite(lng)) { fallback(); return; }
    try {
      var L = window.L;
      L.Icon.Default.imagePath = el.dataset.icons;
      var map = L.map(el, { scrollWheelZoom: false, zoomAnimation: !reduce, fadeAnimation: !reduce, markerZoomAnimation: !reduce })
        .setView([lat, lng], 16);
      var loaded = 0, failed = 0;
      var tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
      }).addTo(map);
      tiles.on("tileload", function () { loaded++; var l = el.querySelector(".store-ad__loading"); if (l) l.hidden = true; });
      tiles.on("tileerror", function () {
        failed++;
        if (!loaded && failed >= 4) { map.remove(); fallback(); }  // no tile ever arrived: show the address card
      });
      // Build the popup with text nodes (never innerHTML) so settings text can't inject markup.
      var pop = document.createElement("div");
      var title = document.createElement("strong"); title.textContent = el.dataset.name;
      var addr = document.createElement("div"); addr.textContent = el.dataset.address;
      var hrs = document.createElement("div"); hrs.textContent = el.dataset.hours;
      pop.appendChild(title); pop.appendChild(addr); pop.appendChild(hrs);
      L.marker([lat, lng], { title: el.dataset.name, alt: el.dataset.name }).addTo(map).bindPopup(pop).openPopup();
      // Don't hijack page scrolling: wheel-zoom only after the user clicks the map
      map.on("click", function () { map.scrollWheelZoom.enable(); });
      map.on("mouseout", function () { map.scrollWheelZoom.disable(); });
    } catch (e) {
      fallback();
    }
  }

  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); start(); }
    }, { rootMargin: "200px" });
    io.observe(el);
  } else {
    start();
  }
})();
