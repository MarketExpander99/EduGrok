self.addEventListener('install', e => {
  e.waitUntil(caches.open('edugrok-v1.2').then(cache => cache.addAll(['/', '/static/style.css'])));
});
self.addEventListener('fetch', e => {
  e.respondWith(caches.match(e.request).then(res => res || fetch(e.request)));
});