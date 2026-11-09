// Thème clair / sombre
(function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  function maj() {
    btn.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "☀️" : "🌙";
  }
  btn.addEventListener("click", function () {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
    maj();
    if (window.rafraichirCharts) window.rafraichirCharts();
  });
  maj();
})();

// Menu mobile
(function () {
  var b = document.getElementById("menu-btn"), s = document.getElementById("sidebar");
  if (b && s) b.addEventListener("click", function () { s.classList.toggle("open"); });
})();

// Toasts: disparaissent toutes seules
document.querySelectorAll(".toast").forEach(function (t) {
  var fermer = function () { t.remove(); };
  var x = t.querySelector(".x");
  if (x) x.addEventListener("click", fermer);
  setTimeout(fermer, 5500);
});

// Confirmation avant suppression: <form data-confirm="Message">
document.querySelectorAll("form[data-confirm]").forEach(function (f) {
  f.addEventListener("submit", function (e) {
    if (!confirm(f.getAttribute("data-confirm"))) e.preventDefault();
  });
});
