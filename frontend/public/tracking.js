/*!
 * Donas Tracking — registra eventos do site no painel /donaspainel.
 * Auto-registra acesso ao carregar a página e expõe helpers globais:
 *   window.donasTrack.registration({ name, email, cpf, phone })
 *   window.donasTrack.pixGenerated({ candidate_name, pix_code, amount, registration_id })
 *   window.donasTrack.pixCopied({ candidate_name, amount, registration_id })
 *   window.donasTrack.pixDownloaded({ candidate_name, amount, registration_id })
 */
(function () {
  // Resolve base da API: usa REACT_APP_BACKEND_URL injetado no build, ou origem atual.
  var API_BASE = (function () {
    try {
      if (window.__DONAS_API_BASE__) return window.__DONAS_API_BASE__;
    } catch (e) {}
    return window.location.origin;
  })();

  function post(path, body) {
    try {
      return fetch(API_BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
        keepalive: true,
      }).catch(function () {});
    } catch (e) {}
  }

  // 1) Auto-track acesso da página
  function trackAccess() {
    post("/api/track/access", {
      page: location.pathname + location.search,
      referrer: document.referrer || "",
    });
  }

  // 2) API global pros HTML usarem
  window.donasTrack = {
    access: trackAccess,
    registration: function (data) { return post("/api/track/registration", data || {}); },
    pixGenerated: function (data) { return post("/api/track/pix-generated", data || {}); },
    pixCopied: function (data) { return post("/api/track/pix-copied", data || {}); },
    pixDownloaded: function (data) { return post("/api/track/pix-downloaded", data || {}); },
  };

  // 3) Auto-hook em botões marcados com data-donas-track
  function bindAuto() {
    document.querySelectorAll("[data-donas-track]").forEach(function (el) {
      var ev = el.getAttribute("data-donas-track");
      el.addEventListener("click", function () {
        var payload = {};
        try { payload = JSON.parse(el.getAttribute("data-donas-payload") || "{}"); } catch (e) {}
        if (ev && window.donasTrack[ev]) window.donasTrack[ev](payload);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      trackAccess();
      bindAuto();
    });
  } else {
    trackAccess();
    bindAuto();
  }
})();
