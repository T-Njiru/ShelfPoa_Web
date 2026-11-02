// Firebase WEB config (public-safe; not the admin service-account key).
// Each service is initialised separately and guarded, so a missing/invalid
// key only disables auth/database features instead of blanking the whole app.
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getDatabase } from "firebase/database";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let app = null;
let auth = null;
let db = null;

try {
  app = initializeApp(firebaseConfig);
} catch (e) {
  console.warn("Firebase app init failed:", e.message);
}
try {
  if (app) auth = getAuth(app);
} catch (e) {
  console.warn("Firebase auth unavailable:", e.message);
}
try {
  if (app) db = getDatabase(app);
} catch (e) {
  console.warn("Firebase database unavailable:", e.message);
}

export { app, auth, db };
