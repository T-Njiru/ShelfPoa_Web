// Recommendations sent to merchandisers.
//
// Sent:   Realtime Database  recommendations/{merchandiserUid}/{recId}
//         Keyed by the target's uid, so the DB rules let each merchandiser read only their own;
//         admins/managers can read all of them. The mobile app updates status as they act on it.
// Drafts: localStorage (this browser only). Drafts are never written to Firebase, so a
//         merchandiser can't see a half-written recommendation.
import { get, onValue, push, ref, serverTimestamp, set } from "firebase/database";
import { auth, db } from "./firebase";

// Must match OSA.EXPECTED_SKUS (mobile) and SKUS in backend/app/core/normalize.py
export const SKUS = [
  "BB ORI 100g", "BB ORI 250g", "BB ORI 500g", "BB ORI 1Kg",
  "BB S4B 100g", "BB S4B 250g", "BB S4B 500g", "BB S4B 1Kg",
  "BB CHOCO 100g", "BB CHOCO 250g", "BB CHOCO 500g",
  "BB VANILLA 500g", "BB VANILLA 1Kg",
];

// mobile status -> label shown on the web
export const STATUS_LABEL = { new: "Pending", seen: "Seen", done: "Done", dismissed: "Declined" };

/**
 * Accounts that can receive recommendations: merchandisers, plus admins
 * (so an admin who also does field audits, or is testing, can be targeted).
 */
export async function listMerchandisers() {
  const snap = await get(ref(db, "users"));
  return Object.entries(snap.val() ?? {})
    .filter(([, u]) => ["merchandiser", "admin"].includes(u?.role) && u.active !== false)
    .map(([uid, u]) => ({
      uid,
      name: `${u.display_name || u.email}${u.role === "admin" ? " (admin)" : ""}`,
      email: u.email,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** Outlets from outlets_universe: [{ id, name }]. ids match what the mobile app stores. */
export async function listOutlets() {
  const snap = await get(ref(db, "outlets_universe"));
  return Object.entries(snap.val() ?? {})
    .map(([id, o]) => ({ id, name: o?.outlet_name ?? id }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** Sends one recommendation to the target merchandiser. Returns the new id. */
export async function send(merchandiserUid, rec) {
  if (!merchandiserUid) throw new Error("Choose a merchandiser");
  const user = auth.currentUser;
  const node = push(ref(db, `recommendations/${merchandiserUid}`));
  await set(node, {
    title: rec.title,
    message: rec.message.trim(),
    type: rec.type,                 // sos | copromo | restock
    priority: rec.priority,         // high | medium | low
    due: rec.due ?? "",
    outletId: rec.outletId ?? "",
    outletName: rec.outletName ?? "",
    sku: rec.sku ?? "",
    basis: rec.basis ?? "",         // the model output it came from, shown to the merchandiser as "Why"
    source: rec.source,             // ml | manual
    createdAt: serverTimestamp(),
    createdBy: user?.uid ?? "",
    createdByName: user?.displayName || user?.email || "",
    status: "new",
  });
  return node.key;
}

/** Live feed of every sent recommendation, newest first. Returns an unsubscribe function. */
export function watchSent(callback, onError) {
  return onValue(
    ref(db, "recommendations"),
    (snap) => {
      const rows = [];
      Object.entries(snap.val() ?? {}).forEach(([merchandiserUid, recs]) => {
        Object.entries(recs ?? {}).forEach(([id, r]) => rows.push({ id, merchandiserUid, ...r }));
      });
      rows.sort((a, b) => (b.createdAt ?? 0) - (a.createdAt ?? 0));
      callback(rows);
    },
    (err) => onError?.(err)
  );
}

// ---- Drafts (localStorage) ----
const DRAFTS_KEY = "shelfpoa.recommendationDrafts";

export function listDrafts() {
  try {
    return JSON.parse(localStorage.getItem(DRAFTS_KEY)) || [];
  } catch {
    return [];
  }
}

export function saveDraft(item) {
  const entry = { ...item, id: item.id || String(Date.now()), savedAt: new Date().toISOString() };
  const others = listDrafts().filter((d) => d.id !== entry.id);
  try {
    localStorage.setItem(DRAFTS_KEY, JSON.stringify([entry, ...others].slice(0, 20)));
  } catch {
    /* storage unavailable: the draft just won't persist */
  }
  return entry;
}

export function removeDraft(id) {
  try {
    localStorage.setItem(DRAFTS_KEY, JSON.stringify(listDrafts().filter((d) => d.id !== id)));
  } catch {
    /* ignore */
  }
}
