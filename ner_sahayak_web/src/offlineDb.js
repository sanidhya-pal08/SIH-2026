/**
 * offlineDb.js — IndexedDB wrapper for NER Sahayak offline queue.
 *
 * Uses the native IndexedDB API (no third-party dependency).
 * Stores:
 *   action_queue     — pending offline actions
 *   operational_cache — last-synced operational snapshot (delivery/route data)
 */

const DB_NAME = 'ner_sahayak_offline';
const DB_VERSION = 1;

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (e) => {
      const db = e.target.result;

      // Action queue store
      if (!db.objectStoreNames.contains('action_queue')) {
        const store = db.createObjectStore('action_queue', { keyPath: 'client_action_id' });
        store.createIndex('by_status', 'status', { unique: false });
        store.createIndex('by_captured_at', 'captured_at', { unique: false });
      }

      // Operational cache store (key = cache key string, e.g. "my_deliveries")
      if (!db.objectStoreNames.contains('operational_cache')) {
        db.createObjectStore('operational_cache', { keyPath: 'cache_key' });
      }
    };

    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

/** Generate a UUID v4 */
export function generateUUID() {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
      });
}

/** Enqueue an offline action. Returns the persisted action object. */
export async function enqueueAction({ action_type, entity_type, payload }) {
  const db = await openDb();
  const action = {
    client_action_id: generateUUID(),
    action_type,
    entity_type,
    payload,
    captured_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    status: 'queued',           // queued | syncing | synced | sync_error
    retry_count: 0,
    last_error: null,
  };

  return new Promise((resolve, reject) => {
    const tx = db.transaction('action_queue', 'readwrite');
    tx.objectStore('action_queue').put(action);
    tx.oncomplete = () => resolve(action);
    tx.onerror = (e) => reject(e.target.error);
  });
}

/** Get all actions with a given status. */
export async function getActionsByStatus(status) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('action_queue', 'readonly');
    const index = tx.objectStore('action_queue').index('by_status');
    const req = index.getAll(IDBKeyRange.only(status));
    req.onsuccess = () => resolve(req.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

/** Count all queued (pending) actions. */
export async function countQueued() {
  const actions = await getActionsByStatus('queued');
  return actions.length;
}

/** Update the status (and optionally other fields) of an action by its client_action_id. */
export async function updateAction(client_action_id, updates) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('action_queue', 'readwrite');
    const store = tx.objectStore('action_queue');
    const getReq = store.get(client_action_id);
    getReq.onsuccess = () => {
      const record = getReq.result;
      if (!record) { resolve(null); return; }
      const updated = { ...record, ...updates };
      store.put(updated);
      tx.oncomplete = () => resolve(updated);
    };
    getReq.onerror = (e) => reject(e.target.error);
  });
}

/** Remove a successfully synced action from the queue. */
export async function removeAction(client_action_id) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('action_queue', 'readwrite');
    tx.objectStore('action_queue').delete(client_action_id);
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

/** Save a snapshot of operational data (e.g. deliveries) for offline use. */
export async function setCacheEntry(cache_key, data) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('operational_cache', 'readwrite');
    tx.objectStore('operational_cache').put({
      cache_key,
      data,
      synced_at: new Date().toISOString(),
    });
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

/** Retrieve a cached operational snapshot. Returns null if not found. */
export async function getCacheEntry(cache_key) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('operational_cache', 'readonly');
    const req = tx.objectStore('operational_cache').get(cache_key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = (e) => reject(e.target.error);
  });
}
