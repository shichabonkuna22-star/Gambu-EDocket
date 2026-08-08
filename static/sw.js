// ============================================================
// SERVICE WORKER FOR SAPS eDocket PWA
// Caches all static assets and serves offline fallback
// ============================================================

const CACHE_NAME = 'saps-v1';
const urlsToCache = [
    '/',
    '/static/css/bootstrap.min.css',
    '/static/css/style.css',
    '/static/js/main.js',
    '/static/js/offline-sync.js',
    '/static/lib/wow/wow.min.js',
    '/static/lib/easing/easing.min.js',
    '/static/lib/waypoints/waypoints.min.js',
    '/static/lib/counterup/counterup.min.js',
    '/static/lib/owlcarousel/owl.carousel.min.js',
    '/static/lib/animate/animate.min.css',
    '/static/lib/owlcarousel/assets/owl.carousel.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.10.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.4.1/font/bootstrap-icons.css',
    'https://cdn.jsdelivr.net/npm/dexie@3.2.4/dist/dexie.min.js',
    '/static/img/favicon.ico',
    '/static/offline.html'  // fallback page
];

// Install event – cache core assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event – clean old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event – serve from cache, fallback to network, with offline page
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response; // cache hit
                }
                // Clone the request because it's a one-time use
                const fetchRequest = event.request.clone();
                return fetch(fetchRequest).then(
                    response => {
                        // Check if we received a valid response
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }
                        // IMPORTANT: Clone the response because it's a one-time use
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(event.request, responseToCache);
                            });
                        return response;
                    }
                ).catch(() => {
                    // If both cache and network fail, show offline page
                    return caches.match('/static/offline.html');
                });
            })
    );
});