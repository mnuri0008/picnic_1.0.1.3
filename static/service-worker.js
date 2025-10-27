// simple cache
self.addEventListener('install', e=>{ e.waitUntil(caches.open('pv-v1').then(c=>c.addAll(['/','/static/app.css']))); });
self.addEventListener('fetch', e=>{ e.respondWith(caches.match(e.request).then(r=> r || fetch(e.request))); });
