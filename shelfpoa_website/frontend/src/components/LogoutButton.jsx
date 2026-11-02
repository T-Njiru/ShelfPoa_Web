import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../services/firebase";

// Ends the Firebase session, then goes to /login. `replace` so Back can't return to the dashboard.
export default function LogoutButton({ className = "" }) {
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function logout() {
    setBusy(true);
    try {
      if (auth) await signOut(auth);
    } finally {
      navigate("/login", { replace: true });
    }
  }

  return (
    <button
      type="button"
      onClick={logout}
      disabled={busy}
      title="Log out"
      className={`text-[10px] text-muted hover:text-white disabled:opacity-60 ${className}`}
    >
      {busy ? "Logging out…" : "Log out"}
    </button>
  );
}
