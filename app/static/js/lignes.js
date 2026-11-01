// Lignes dynamiques (ventes / commandes): produit + quantité + prix, total en direct.
(function () {
  var conteneur = document.getElementById("lignes");
  if (!conteneur) return;
  var produits = window.PRODUITS || [];
  var initiales = window.LIGNES_INIT || [];

  function fmt(n) { return (Math.round(n * 100) / 100).toFixed(2); }

  function recalculer() {
    var total = 0;
    conteneur.querySelectorAll(".ligne-row").forEach(function (row) {
      var q = parseFloat(row.querySelector("[name=quantite]").value) || 0;
      var p = parseFloat(row.querySelector("[name=prix]").value) || 0;
      var st = q * p;
      row.querySelector(".sous-total").textContent = fmt(st) + " DT";
      total += st;
    });
    var t = document.getElementById("total");
    if (t) t.textContent = fmt(total) + " DT";
  }

  function ajouter(valeurs) {
    valeurs = valeurs || {};
    var row = document.createElement("div");
    row.className = "ligne-row";
    var options = '<option value="">-- Produit --</option>' + produits.map(function (p) {
      return '<option value="' + p.id + '">' + p.nom.replace(/</g, "&lt;") + " (stock: " + p.stock + ")</option>";
    }).join("");
    row.innerHTML =
      '<select name="produit_id" required>' + options + "</select>" +
      '<input name="quantite" type="number" min="1" value="' + (valeurs.quantite || 1) + '" required>' +
      '<input name="prix" type="number" min="0" step="0.01" value="' + (valeurs.prix || 0) + '" required>' +
      '<div class="sous-total">0.00 DT</div>' +
      '<button type="button" class="btn btn-sm btn-danger" title="Supprimer la ligne">✕</button>';
    var select = row.querySelector("select");
    if (valeurs.produit_id) select.value = String(valeurs.produit_id);
    select.addEventListener("change", function () {
      var p = produits.filter(function (x) { return String(x.id) === select.value; })[0];
      if (p) row.querySelector("[name=prix]").value = p.prix;
      recalculer();
    });
    row.addEventListener("input", recalculer);
    row.querySelector("button").addEventListener("click", function () {
      if (conteneur.querySelectorAll(".ligne-row").length > 1) { row.remove(); recalculer(); }
    });
    conteneur.appendChild(row);
    recalculer();
  }

  document.getElementById("ajouter-ligne").addEventListener("click", function () { ajouter(); });
  if (initiales.length) initiales.forEach(ajouter); else ajouter();
})();
