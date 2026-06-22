/* CODIR — Service Worker PWA + Web Push (Lot 6).
 *
 * Stratégie de cache minimaliste (App Shell uniquement) :
 *   - Précache : index.html, manifest, icons → installation
 *   - Runtime  : network-first pour HTML, cache-first pour assets statiques
 *   - Offline  : sert l'index en fallback pour permettre le routing SPA
 *
 * Push events :
 *   - Reçoit un payload JSON {title, body, url, icon, tag}
 *   - Affiche une notif native via registration.showNotification()
 *   - Au clic : focus la fenêtre existante ou ouvre une nouvelle sur `url`
 */

const VERSION = 'codir-v1';
const PRECACHE = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/kaydan-mark.svg',
];

// ─── Installation ────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(PRECACHE).catch(() => {}))
  );
  self.skipWaiting();
});

// ─── Activation : purge des anciens caches ───────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ─── Fetch handler ───────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Ne pas intercepter API ni MinIO ni same-origin streaming
  if (url.pathname.startsWith('/api/')) return;
  if (url.pathname.startsWith('/admin/')) return;

  // Navigation (HTML) : network-first, fallback cache → fallback index
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() =>
          caches.match(req).then((r) => r || caches.match('/index.html'))
        )
    );
    return;
  }

  // Assets statiques : cache-first
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req)
          .then((res) => {
            if (res.ok && res.status === 200) {
              const copy = res.clone();
              caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
            }
            return res;
          })
          .catch(() => cached);
      })
    );
  }
});

// ─── Push event ──────────────────────────────────────────────
self.addEventListener('push', (event) => {
  let payload = { title: 'CODIR', body: '', url: '/' };
  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch (e) {
    // Si pas du JSON, on prend le texte brut comme body
    try { payload.body = event.data.text() } catch {}
  }

  const options = {
    body:  payload.body || '',
    icon:  payload.icon  || '/icons/icon-192.png',
    badge: payload.badge || '/icons/badge-72.png',
    tag:   payload.tag   || 'codir-notif',
    data:  { url: payload.url || '/' },
    renotify: false,
    requireInteraction: false,
    lang: 'fr-FR',
  };

  event.waitUntil(
    self.registration.showNotification(payload.title || 'CODIR', options)
  );
});

// ─── Notification click ──────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((windowClients) => {
        // Réutilise une fenêtre déjà ouverte si possible
        for (const client of windowClients) {
          const url = new URL(client.url);
          if (url.origin === self.location.origin && 'focus' in client) {
            client.postMessage({ type: 'navigate', url: targetUrl });
            return client.focus();
          }
        }
        // Sinon en ouvrir une nouvelle
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }
      })
  );
});
