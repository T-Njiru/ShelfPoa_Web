// Admin-console session: who is signed in, and are they allowed in?
//
// * Signed-in state comes from Firebase Auth. Login.jsx sets browserSessionPersistence, so the
//   session ends when the browser/tab is closed instead of lasting forever.
// * Access needs users/{uid}.role in ALLOWED_ROLES. A merchandiser account can sign in to the
//   mobile app but not the admin console, even by typing a page URL.
// * AppShell signs the user out after IDLE_MINUTES without activity.
//
// This guards the UI only. The data itself must be protected by Realtime Database rules
// (only admins can read audits / osa_reports / users etc.), since anyone can call Firebase directly.
import { useEffect, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { get, ref } from "firebase/database";
import { auth, db } from "./firebase";

export const ALLOWED_ROLES = ["admin", "manager"];
export const IDLE_MINUTES = 30;

/** The user's role from users/{uid}, or "" if there is no record / it can't be read. */
export async function fetchRole(uid) {
  try {
    const snap = await get(ref(db, `users/${uid}`));
    const u = snap.val() ?? {};
    return u.active === false ? "" : u.role ?? "";
  } catch {
    return "";
  }
}

/**
 * { status, user, role }
 *   status: "loading" | "signed-out" | "forbidden" (signed in, wrong role) | "ok"
 */
export function useSession() {
  const [state, setState] = useState({ status: auth ? "loading" : "signed-out", user: null, role: "" });

  useEffect(() => {
    if (!auth) return;
    return onAuthStateChanged(auth, async (user) => {
      if (!user) return setState({ status: "signed-out", user: null, role: "" });
      const role = await fetchRole(user.uid);
      setState({ status: ALLOWED_ROLES.includes(role) ? "ok" : "forbidden", user, role });
    });
  }, []);

  return state;
}
