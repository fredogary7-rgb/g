/* FANTA — interactions légères (vanilla JS) */
(function () {
  "use strict";

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback navigateurs anciens / non sécurisés
    return new Promise(function (resolve) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e) { /* noop */ }
      document.body.removeChild(ta);
      resolve();
    });
  }

  function share(data) {
    if (navigator.share) {
      navigator.share(data).catch(function () { /* annulé */ });
    } else {
      copyText(data.url).then(function () {
        flash("Lien copié dans le presse-papiers.");
      });
    }
  }

  function flash(message) {
    var stack = document.querySelector(".flash-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "flash-stack";
      document.querySelector(".app")?.prepend(stack);
    }
    var el = document.createElement("div");
    el.className = "flash flash-info";
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(function () { el.remove(); }, 2400);
  }

  // Copie déclenchée par [data-copy]
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    var text = btn.getAttribute("data-copy") || "";
    copyText(text).then(function () {
      var label = btn.dataset.label || btn.textContent.trim();
      btn.textContent = "Copié ✓";
      btn.classList.add("loading");
      setTimeout(function () {
        btn.textContent = label;
        btn.classList.remove("loading");
      }, 1500);
    });
  });

  // Partage via [data-share]
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-share]");
    if (!btn) return;
    share({
      title: btn.getAttribute("data-share-title") || "FANTA",
      text: btn.getAttribute("data-share-text") || "Rejoignez-moi sur FANTA !",
      url: btn.getAttribute("data-share") || location.href,
    });
  });

  // États de chargement des formulaires (sauf GET)
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || (form.method || "get").toLowerCase() === "get") return;
    var submit = form.querySelector('button[type="submit"]');
    if (submit && !submit.disabled) {
      if (!submit.dataset.label) submit.dataset.label = submit.textContent.trim();
      submit.textContent = "Chargement…";
      submit.classList.add("loading");
      submit.disabled = true;
    }
  });

  // Toggle mot de passe
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-toggle-password]");
    if (!btn) return;
    var input = document.getElementById(btn.getAttribute("data-toggle-password"));
    if (!input) return;
    input.type = input.type === "password" ? "text" : "password";
  });

  // Sélection rapide de montant (page dépôt)
  document.addEventListener("click", function (e) {
    var chip = e.target.closest(".amt-chip");
    if (!chip) return;
    var input = document.getElementById("amount");
    if (input) input.value = chip.getAttribute("data-amount");
    document.querySelectorAll(".amt-chip").forEach(function (c) { c.classList.remove("active"); });
    chip.classList.add("active");
  });
})();
