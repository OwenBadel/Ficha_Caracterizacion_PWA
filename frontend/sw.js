// Service Worker para PWA Offline-First de Fichas de Caracterización — Owen Badel Hooker
const CACHE_NAME = 'ficha-caracterizacion-v21';
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.json',
  '/static/css/styles.css',
  '/static/js/db.js',
  '/static/js/app.js',
  '/static/img/icon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn('Algunos recursos no se pudieron precachear:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Las peticiones a la API siempre van directo a la red (no se precachean)
  if (event.request.url.includes('/api/')) {
    return;
  }

  // Estrategia Network-First con Timeout Estricto de 1500ms para mitigar Wi-Fi débil en campo
  event.respondWith(
    new Promise((resolve) => {
      let yaRespondio = false;

      // Temporizador de 1.5s: si la red local o Wi-Fi colapsa, responder inmediatamente con caché
      const timeoutId = setTimeout(async () => {
        if (!yaRespondio) {
          const cached = await caches.match(event.request, { ignoreSearch: true });
          if (cached) {
            yaRespondio = true;
            resolve(cached);
          } else if (event.request.mode === 'navigate') {
            const rootCached = await caches.match('/', { ignoreSearch: true });
            if (rootCached) {
              yaRespondio = true;
              resolve(rootCached);
            }
          }
        }
      }, 1500);

      fetch(event.request)
        .then((networkResponse) => {
          clearTimeout(timeoutId);
          if (networkResponse && networkResponse.status === 200 && event.request.method === 'GET') {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseToCache);
            });
          }
          if (!yaRespondio) {
            yaRespondio = true;
            resolve(networkResponse);
          }
        })
        .catch(async () => {
          clearTimeout(timeoutId);
          if (!yaRespondio) {
            yaRespondio = true;
            const cachedResponse = await caches.match(event.request, { ignoreSearch: true });
            if (cachedResponse) {
              return resolve(cachedResponse);
            }
            if (event.request.mode === 'navigate') {
              const rootCached = await caches.match('/', { ignoreSearch: true });
              if (rootCached) {
                return resolve(rootCached);
              }
            }
          }
        });
    })
  );
});
