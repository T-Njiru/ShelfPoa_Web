import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import {
  browserSessionPersistence,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import { auth } from "../services/firebase";
import { ALLOWED_ROLES, fetchRole, useSession } from "../services/session";
import { Logo } from "../components/Logo";

const inputCls =
  "w-full h-12 rounded-control bg-card px-4 text-[13px] text-white placeholder:text-muted outline-none focus:ring-1 focus:ring-accent";
const labelCls = "block mb-2 text-xs font-semibold text-muted";

export default function Login() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const location = useLocation();
  const [error, setError] = useState(location.state?.reason ?? ""); // e.g. idle sign-out, no access
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { status } = useSession();

  // Already signed in as an admin -> skip the form
  if (status === "ok" && !loading) return <Navigate to={location.state?.from ?? "/"} replace />;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (!auth) {
      setError("Sign-in isn't configured. Check the VITE_FIREBASE_* values in .env.local.");
      return;
    }
    setLoading(true);
    try {
      // The session ends when the browser is closed (default would keep it signed in indefinitely)
      await setPersistence(auth, browserSessionPersistence);
      const { user } = await signInWithEmailAndPassword(auth, email, password);
      if (!ALLOWED_ROLES.includes(await fetchRole(user.uid))) {
        await signOut(auth);
        setError("This account doesn't have access to the admin console.");
        return;
      }
      navigate(location.state?.from ?? "/", { replace: true });
    } catch {
      setError("Couldn't sign in. Check your email and password.");
    } finally {
      setLoading(false);
    }
  }

  async function forgotPassword() {
    setError("");
    setInfo("");
    if (!email) return setError("Enter your work email first.");
    if (!auth) return setError("Sign-in isn't configured.");
    try {
      await sendPasswordResetEmail(auth, email);
      setInfo("Password reset email sent.");
    } catch {
      setError("Couldn't send a reset email to that address.");
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-[minmax(360px,560px)_minmax(0,1fr)] bg-bg text-white">
      <div className="bg-accent-deep p-10 xl:p-16 flex flex-col">
        <Logo className="h-11" />

        <div className="mt-[272px]">
          <h2 className="text-[34px] leading-[1.2] font-bold max-w-[400px]">Retail intelligence for every Blueband shelf.</h2>
          <p className="mt-3 text-[13px] text-white/80 max-w-[390px] leading-snug">
            Track SOS, OSA and planogram compliance, and turn basket and demand data into action across your merchandiser network.
          </p>
        </div>

        {/* Marketing figures from the Figma design — placeholders, not live data. */}
        <div className="flex flex-wrap gap-5 mt-[100px]">
          <div className="rounded-card bg-white/15 px-5 py-4 w-[200px] h-[90px]">
            <div className="text-2xl font-bold">128</div>
            <div className="text-[11px] text-white/80">Active merchandisers</div>
          </div>
          <div className="rounded-card bg-white/15 px-5 py-4 w-[212px] h-[90px]">
            <div className="text-2xl font-bold">3,400+</div>
            <div className="text-[11px] text-white/80">Outlets tracked weekly</div>
          </div>
        </div>
      </div>

      <div className="flex items-start pt-[158px] px-10 xl:px-24">
        <form onSubmit={handleSubmit} className="w-full max-w-[400px]">
          <h1 className="text-[28px] font-bold">Admin sign in</h1>
          <p className="text-[13px] text-muted mt-2 mb-9">Access the ShelfPoa control center</p>

          <div className="inline-flex gap-1 p-1 rounded-control bg-card mb-5">
            {[["login", "Log in"], ["signup", "Sign up"]].map(([v, l]) => (
              <button
                type="button"
                key={v}
                onClick={() => setMode(v)}
                className={`h-9 w-[165px] rounded-lg text-xs font-semibold text-left px-3 ${
                  mode === v ? "bg-accent text-ink" : "text-muted hover:text-white"
                }`}
              >
                {l}
              </button>
            ))}
          </div>

          {mode === "signup" ? (
            // Admin accounts are invite-only (the Figma footer says to contact the Flora Foods admin),
            // so self-registration is intentionally not wired to Firebase.
            <p className="text-[13px] text-muted leading-relaxed">
              Accounts are created by your Flora Foods admin. Contact them to get access.
            </p>
          ) : (
            <>
              <label className={labelCls}>Work email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@floragroup.co.ke"
                className={`${inputCls} mb-4`}
              />

              <label className={labelCls}>Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={inputCls}
              />
              <button type="button" onClick={forgotPassword} className="mt-2 text-xs font-semibold text-accent hover:underline">
                Forgot password?
              </button>

              {error && <p className="text-bad text-xs mt-4">{error}</p>}
              {info && <p className="text-ok text-xs mt-4">{info}</p>}

              <button
                type="submit"
                disabled={loading}
                className="mt-6 w-full h-12 rounded-control bg-accent hover:bg-accent-hover text-ink text-[13px] font-semibold text-left px-3 disabled:opacity-60"
              >
                {loading ? "Signing in…" : "Log in to dashboard"}
              </button>
              <p className="mt-5 text-xs text-muted">Don't have an account? Contact your Flora Foods admin</p>
            </>
          )}
        </form>
      </div>
    </div>
  );
}
