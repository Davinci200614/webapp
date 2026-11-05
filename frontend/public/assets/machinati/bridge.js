/* Same-origin integration for the original MACHINATI pages. No credentials in URLs. */
(() => {
  const privatePage = document.documentElement.dataset.operator === 'true';
  const loginPath = document.documentElement.dataset.loginPath || '/operations';
  const nativeFetch = window.fetch.bind(window);
  const expire = () => {
    sessionStorage.removeItem('webapp_api_token');
    window.top.location.assign(loginPath);
  };
  window.fetch = async (input, init = {}) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) return nativeFetch(input, init);
    const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
    const token = sessionStorage.getItem('webapp_api_token');
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await nativeFetch(input, {...init, headers});
    if (response.status === 401 && privatePage) expire();
    return response;
  };
  window.machinatiWhatsApp = '';
  window.machinatiReady = (async () => {
    if (privatePage) {
      if (!sessionStorage.getItem('webapp_api_token')) { expire(); return false; }
      const response = await window.fetch('/api/auth/me');
      if (!response.ok) { document.body.textContent = 'Connexion impossible. Rechargez la page pour réessayer.'; return false; }
      document.documentElement.classList.remove('awaiting-auth');
    } else {
      try {
        const response = await window.fetch('/api/public/config');
        if (response.ok) window.machinatiWhatsApp = String((await response.json()).whatsapp_number || '').replace(/\D/g, '');
      } catch { /* Catalogue remains usable; WhatsApp reports missing contact on click. */ }
    }
    return true;
  })().catch(() => {
    if (privatePage) {
      document.documentElement.classList.remove('awaiting-auth');
      document.body.textContent = 'Connexion impossible. Rechargez la page pour réessayer.';
    }
    return false;
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin && !link.getAttribute('href').startsWith('#')) link.target = '_top';
    if (url.hostname === 'wa.me' && !window.machinatiWhatsApp) {
      event.preventDefault();
      if (typeof window.machinatiNotice === 'function') window.machinatiNotice('Le numéro WhatsApp du service n’est pas encore configuré.');
    }
  });
})();
