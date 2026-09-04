/**
 * syncWorker.js — Connectivity detection and idempotent batch sync.
 *
 * Responsibilities:
 *  1. Detect CONNECTED / OFFLINE / SERVER_UNAVAILABLE states.
 *  2. When connectivity returns, read queued actions from IndexedDB.
 *  3. POST them as a batch to POST /api/v1/sync.
 *  4. Apply per-action results (remove accepted/duplicate, retain errors).
 *  5. Emit DOM events for the UI to reflect current sync state.
 *  6. Retry with bounded exponential backoff on transient failure.
 *
 * Connectivity states emitted via CustomEvent 'ner:connectivity':
 *   { state: 'CONNECTED' | 'OFFLINE' | 'SERVER_UNAVAILABLE' | 'SYNCING', queuedCount: number }
 *
 * Sync result emitted via CustomEvent 'ner:sync-result':
 *   { accepted, duplicates, errors, conflicts }
 */

import {
  getActionsByStatus,
  updateAction,
  removeAction,
  countQueued,
  generateUUID,
} from './offlineDb.js';

const API_BASE = 'http://localhost:8000/api/v1';
const HEALTH_URL = `${API_BASE}/health`;
const SYNC_URL = `${API_BASE}/sync`;

// Stable browser client ID — persisted in localStorage
function getClientId() {
  let id = localStorage.getItem('ner_client_id');
  if (!id) {
    id = generateUUID();
    localStorage.setItem('ner_client_id', id);
  }
  return id;
}

// ── State ────────────────────────────────────────────────────────────────────
let currentState = 'CONNECTED';
let syncInProgress = false;
let retryAttempt = 0;
const MAX_RETRIES = 3;
const RETRY_DELAYS_MS = [5000, 15000, 30000]; // exponential-ish backoff

// ── Event emitters ───────────────────────────────────────────────────────────
async function emitConnectivity(state) {
  currentState = state;
  const queuedCount = await countQueued().catch(() => 0);
  window.dispatchEvent(
    new CustomEvent('ner:connectivity', { detail: { state, queuedCount } })
  );
}

function emitSyncResult(stats) {
  window.dispatchEvent(
    new CustomEvent('ner:sync-result', { detail: stats })
  );
}

// ── Health probe ─────────────────────────────────────────────────────────────
/**
 * True = backend reachable.
 * We prefer this over navigator.onLine which can lie (captive portal, etc.)
 */
async function isBackendReachable() {
  try {
    const res = await fetch(HEALTH_URL, { method: 'GET', cache: 'no-store', signal: AbortSignal.timeout(4000) });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Core sync logic ──────────────────────────────────────────────────────────
async function runSync() {
  if (syncInProgress) return;

  const reachable = await isBackendReachable();
  if (!reachable) {
    await emitConnectivity(navigator.onLine ? 'SERVER_UNAVAILABLE' : 'OFFLINE');
    return;
  }

  const queued = await getActionsByStatus('queued');
  if (queued.length === 0) {
    await emitConnectivity('CONNECTED');
    retryAttempt = 0;
    return;
  }

  syncInProgress = true;
  await emitConnectivity('SYNCING');

  // Mark all as syncing so UI can reflect state
  for (const a of queued) {
    await updateAction(a.client_action_id, { status: 'syncing' });
  }

  const token = localStorage.getItem('token');
  if (!token) {
    // Session expired while offline — requeue everything and notify
    for (const a of queued) {
      await updateAction(a.client_action_id, { status: 'queued', last_error: 'No auth token — please log in.' });
    }
    syncInProgress = false;
    await emitConnectivity('OFFLINE');
    return;
  }

  // Build batch payload sorted by captured_at (preserve causal order)
  const sorted = [...queued].sort(
    (a, b) => new Date(a.captured_at) - new Date(b.captured_at)
  );

  const batchPayload = {
    client_id: getClientId(),
    sync_batch_id: generateUUID(),
    actions: sorted.map((a) => ({
      client_action_id: a.client_action_id,
      action_type: a.action_type,
      entity_type: a.entity_type,
      payload: a.payload,
      occurred_at: a.captured_at,
    })),
  };

  let stats = { accepted: 0, duplicates: 0, errors: 0, conflicts: 0 };

  try {
    const res = await fetch(SYNC_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(batchPayload),
      signal: AbortSignal.timeout(15000),
    });

    if (res.status === 401) {
      // Auth failure — keep actions queued, warn user
      for (const a of queued) {
        await updateAction(a.client_action_id, { status: 'queued', last_error: 'Authentication failed. Please log in again.' });
      }
      syncInProgress = false;
      await emitConnectivity('SERVER_UNAVAILABLE');
      return;
    }

    if (!res.ok) {
      throw new Error(`Sync endpoint returned ${res.status}`);
    }

    const data = await res.json();
    const resultMap = {};
    for (const r of data.results) {
      resultMap[r.client_action_id] = r;
    }

    // Process per-action outcomes
    for (const a of sorted) {
      const result = resultMap[a.client_action_id];
      if (!result) {
        // Server didn't return a result — keep queued
        await updateAction(a.client_action_id, { status: 'queued', last_error: 'No response from server' });
        stats.errors++;
        continue;
      }

      if (result.status === 'accepted') {
        await removeAction(a.client_action_id);
        stats.accepted++;
      } else if (result.status === 'duplicate') {
        // Server already has this — safe to remove locally
        await removeAction(a.client_action_id);
        stats.duplicates++;
      } else if (result.status === 'conflict') {
        // Conflict went through EPIC-05 dispute logic — remove from queue, user sees it in CR
        await removeAction(a.client_action_id);
        stats.conflicts++;
      } else {
        // rejected | validation_failed | authorization_failed — retain with error detail
        await updateAction(a.client_action_id, {
          status: 'sync_error',
          last_error: result.detail || result.status,
          retry_count: (a.retry_count || 0) + 1,
        });
        stats.errors++;
      }
    }

    retryAttempt = 0;
    await emitConnectivity('CONNECTED');
    emitSyncResult(stats);

  } catch (err) {
    // Network-level failure during sync
    console.warn('[syncWorker] Sync failed:', err.message);
    for (const a of queued) {
      await updateAction(a.client_action_id, {
        status: 'queued',
        last_error: err.message,
        retry_count: (a.retry_count || 0) + 1,
      });
    }
    stats.errors = queued.length;

    // Exponential backoff retry
    if (retryAttempt < MAX_RETRIES) {
      const delay = RETRY_DELAYS_MS[retryAttempt] ?? 30000;
      retryAttempt++;
      console.info(`[syncWorker] Retrying in ${delay}ms (attempt ${retryAttempt})`);
      setTimeout(runSync, delay);
    } else {
      console.warn('[syncWorker] Max retries reached. Actions remain queued.');
      await emitConnectivity('SERVER_UNAVAILABLE');
    }

    emitSyncResult(stats);
  } finally {
    syncInProgress = false;
  }
}

// ── Online/offline event listeners ───────────────────────────────────────────
window.addEventListener('online', async () => {
  console.info('[syncWorker] Browser online event received');
  retryAttempt = 0;
  await runSync();
});

window.addEventListener('offline', async () => {
  console.info('[syncWorker] Browser offline event received');
  await emitConnectivity('OFFLINE');
});

// ── Public API ───────────────────────────────────────────────────────────────

/** Call this once on app mount to check current connectivity and trigger initial sync. */
export async function initSync() {
  const reachable = await isBackendReachable();
  if (!reachable) {
    await emitConnectivity(navigator.onLine ? 'SERVER_UNAVAILABLE' : 'OFFLINE');
  } else {
    await runSync();
  }
}

/** Manually trigger a sync attempt (e.g., after user action). */
export async function triggerSync() {
  retryAttempt = 0;
  await runSync();
}

/** Get the current connectivity state string. */
export function getConnectivityState() {
  return currentState;
}
