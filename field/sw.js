/* MovelAgro Field Registration — Service Worker
 * Caches the registration shell for full offline use.
 * Registration data is stored in IndexedDB (register.html)
 * and synced via /api/v1/nodes when connectivity returns.
 */

const CACHE = 'movelagro-field-v1';
const SHELL = ['/field/register.html'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  /* Pass API calls straight through — never cache node POST requests */
  if (url.pathname.startsWith('/api/')) return;

  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(res => {
        /* Cache successful GET responses for shell assets */
        if (e.request.method === 'GET' && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => caches.match('/field/register.html'));
    })
  );
});

/* Background sync — fires when connectivity restored */
self.addEventListener('sync', e => {
  if (e.tag === 'sync-registrations') {
    e.waitUntil(syncPendingRegistrations());
  }
});

async function syncPendingRegistrations() {
  const db = await openDB();
  const pending = await getPending(db);

  for (const record of pending) {
    try {
      const res = await fetch('/api/v1/nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(record)
      });
      if (res.ok) await markSynced(db, record.nodeId);
    } catch (_) {
      /* Will retry on next sync event */
    }
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('movelagro_field', 1);
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

function getPending(db) {
  return new Promise((resolve) => {
    const tx = db.transaction('registrations', 'readonly');
    const idx = tx.objectStore('registrations').index('syncStatus');
    const req = idx.getAll(IDBKeyRange.only('pending'));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve([]);
  });
}

function markSynced(db, nodeId) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('registrations', 'readwrite');
    const store = tx.objectStore('registrations');
    const get = store.get(nodeId);
    get.onsuccess = () => {
      const rec = get.result;
      if (rec) { rec.syncStatus = 'synced'; store.put(rec); }
    };
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}
