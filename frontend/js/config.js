// ===== NagrikSnap Global Runtime Configuration =====
(function () {
  'use strict';

  // Dynamic API Base Resolver:
  // 1. window.__NAGRIKSNAP_API_BASE__ (if set via HTML head)
  // 2. localStorage.getItem('nagriksnap_api_base') (for dynamic runtime configuration in settings)
  // 3. Dev server fallback to http://127.0.0.1:8000 if frontend is served on a different port (e.g. 5500)
  // 4. Same-origin relative path ('') when served by FastAPI or unified domain
  window.NAGRIKSNAP_API_BASE = (function resolveApiBase() {
    if (window.__NAGRIKSNAP_API_BASE__) {
      return window.__NAGRIKSNAP_API_BASE__.replace(/\/+$/, '');
    }
    try {
      const stored = localStorage.getItem('nagriksnap_api_base');
      if (stored) return stored.replace(/\/+$/, '');
    } catch (_) {}

    if ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && window.location.port !== '8000') {
      return 'http://127.0.0.1:8000';
    }
    return '';
  })();
})();
