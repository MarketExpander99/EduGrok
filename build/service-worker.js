// Basic Workbox service worker for offline caching
importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.1.5/workbox-sw.js');

workbox.routing.registerRoute(
  ({request}) => request.destination === 'script' ||
                 request.destination === 'style' ||
                 request.destination === 'image',
  new workbox.strategies.CacheFirst()
);

workbox.precaching.precacheAndRoute(self.__WB_MANIFEST || []);