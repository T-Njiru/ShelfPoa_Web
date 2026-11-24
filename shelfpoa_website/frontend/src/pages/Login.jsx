import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import {
  GoogleAuthProvider,
  browserSessionPersistence,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from "firebase/auth";
import { auth } from "../services/firebase";
import { api } from "../services/api";
import { ALLOWED_ROLES, fetchRole, useSession } from "../services/session";
import { ALLOWED_DOMAINS, domainList, emailAllowed } from "../lib/allowedDomains";
import { Logo } from "../components/Logo";

const fmt = (n) => Number(n).toLocaleString("en-KE");

// Live, aggregate figures from GET /api/public/stats (last 30 days). While the free-tier server
// wakes up they show "…"; if it can't be reached they are hidden rather than faked.
function LiveStats() {
  const [stats, setStats] = useState(null); // null = loading, false = unavailable
  useEffect(() => {
    let alive = true;
    api.getPublicStats().then((s) => alive && setStats(s)).catch(() => alive && setStats(false));
    return () => {
      alive = false;
    };
  }, []);
  if (stats === false) return null;
  const cards = [
    [stats?.active_merchandisers, "Active merchandisers"],
    [stats?.outlets_audited, stats ? `Outlets audited (of ${fmt(stats.outlets_total)})` : "Outlets audited"],
    [stats?.store_visits, "Store visits"],
  ];
  return (
    <div className="mt-[100px]">
      <div className="grid grid-cols-3 gap-3 max-w-[460px]">
        {cards.map(([value, label]) => (
          <div key={label} className="rounded-card bg-white/15 px-4 py-4 min-h-[90px]">
            <div className="text-2xl font-bold">{value == null ? "…" : fmt(value)}</div>
            <div className="text-[11px] text-white/80">{label}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-white/70">
        {stats ? `Last ${stats.window_days} days, live from the audit database` : "Loading live figures…"}
      </p>
    </div>
  );
}

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
  const [loading, setLoading] = useState(false); // false | "password" | "google"
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
    setLoading("password");
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

  // Flora Food Group Google accounts, or any account an admin has already set up (e.g. an existing
  // admin's own Gmail). Either way it needs an admin/manager role; the API checks this again.
  async function googleSignIn() {
    setError("");
    setInfo("");
    if (!auth) return setError("Sign-in isn't configured. Check the VITE_FIREBASE_* values in .env.local.");
    setLoading("google");
    try {
      await setPersistence(auth, browserSessionPersistence);
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });
      const { user } = await signInWithPopup(auth, provider);
      if (!ALLOWED_ROLES.includes(await fetchRole(user.uid))) {
        await signOut(auth);
        setError(
          user.emailVerified && emailAllowed(user.email)
            ? `${user.email} isn't activated for the admin console yet. Ask a ShelfPoa admin to give it access.`
            : `Google sign-in is for Flora Food Group accounts (${domainList()}) and accounts an admin has already set up.`
        );
        return;
      }
      navigate(location.state?.from ?? "/", { replace: true });
    } catch (e) {
      if (e?.code === "auth/popup-closed-by-user" || e?.code === "auth/cancelled-popup-request") return;
      setError(
        e?.code === "auth/popup-blocked"
          ? "Your browser blocked the Google window. Allow pop-ups for this site and try again."
          : e?.code === "auth/account-exists-with-different-credential"
            ? "This email already has a password account. Sign in with your password instead."
            : "Couldn't sign in with Google. Try again."
      );
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

        <LiveStats />
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
            // Admin accounts are invite-only, so self-registration is intentionally not wired to Firebase.
            <p className="text-[13px] text-muted leading-relaxed">
              Accounts are created by your Flora Food Group admin. Contact them to get access. If you
              have a Flora Food Group Google account, use "Continue with Google" and ask them to activate it.
            </p>
          ) : (
            <>
              <label className={labelCls}>Work email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={`you@${ALLOWED_DOMAINS[0] ?? "upfield.com"}`}
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
                disabled={Boolean(loading)}
                className="mt-6 w-full h-12 rounded-control bg-accent hover:bg-accent-hover text-ink text-[13px] font-semibold text-left px-3 disabled:opacity-60"
              >
                {loading === "password" ? "Signing in…" : "Log in to dashboard"}
              </button>

              <div className="flex items-center gap-3 my-5 text-[11px] text-muted">
                <span className="h-px flex-1 bg-white/10" />
                or
                <span className="h-px flex-1 bg-white/10" />
              </div>
              <button
                type="button"
                onClick={googleSignIn}
                disabled={Boolean(loading)}
                className="w-full h-12 rounded-control bg-white hover:bg-white/90 text-ink text-[13px] font-semibold disabled:opacity-60"
              >
                {loading === "google" ? "Waiting for Google…" : "Continue with Google"}
              </button>
              <p className="mt-2 text-[11px] text-muted">
                For Flora Food Group Google accounts ({domainList()}) and accounts your admin has set up.
              </p>
              <p className="mt-5 text-xs text-muted">Don't have an account? Contact your Flora Food Group admin</p>
            </>
          )}
        </form>
      </div>
    </div>
  );
}
