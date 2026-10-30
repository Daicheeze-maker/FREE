// Runs before first paint to avoid a theme flash. Kept tiny and external (CSP: script-src 'self').
(function () {
  var t = null;
  try { t = localStorage.getItem("velora-theme"); } catch (e) {}
  if (!t) t = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", t);
  document.documentElement.classList.add("js");
})();
