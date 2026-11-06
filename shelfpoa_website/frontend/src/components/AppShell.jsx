import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "../services/firebase";
import { IDLE_MINUTES, useSession } from "../services/session";
import { initials } from "../lib/format";
import { Logo } from "./Logo";
import LogoutButton from "./LogoutButton";

// Pages with a working header search, and what it searches there
const SEARCH_HINT = {
  "/": "Search merchandisers, outlets, sub-counties…",
  "/recommendations": "Search outlets, SKUs, products…",
  "/stockouts": "Search SKUs, outlets, reporters…",
};

const NAV = [
  { to: "/", label: "Merchandiser performance" },
  { to: "/recommendations", label: "Recommendations" },
  { to: "/recommendation-maker", label: "Recommendation maker" },
  { to: "/stockouts", label: "Stock-out alerts" },
  { to: "/new-outlet", label: "New outlet planner" },
];

// Sign out after IDLE_MINUTES without mouse / keyboard / touch activity.
function useIdleLogout(enabled) {
  const navigate = useNavigate();
  useEffect(() => {
    if (!enabled || !auth) return;
    let timer;
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        await signOut(auth);
        navigate("/login", { replace: true, state: { reason: `Signed out after ${IDLE_MINUTES} minutes of inactivity.` } });
      }, IDLE_MINUTES * 60 * 1000);
    };
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"];
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [enabled, navigate]);
}

export default function AppShell() {
  const { pathname } = useLocation();
  const { status, user } = useSession();
  const [query, setQuery] = useState("");
  useEffect(() => setQuery(""), [pathname]); // each page starts unfiltered
  useIdleLogout(status === "ok");
  useEffect(() => {
    if (status === "forbidden" && auth) signOut(auth); // e.g. a merchandiser account: end its web session
  }, [status]);
  const title = NAV.find((n) => n.to === pathname)?.label ?? "ShelfPoa";

  // Every page inside the shell needs a signed-in admin/manager -- typing a URL doesn't bypass this.
  if (status === "loading") return <div className="min-h-screen bg-bg" />;
  if (status === "signed-out") return <Navigate to="/login" replace state={{ from: pathname }} />;
  if (status === "forbidden")
    return <Navigate to="/login" replace state={{ reason: "This account doesn't have access to the admin console." }} />;

  const name = user.displayName || user.email?.split("@")[0] || "Admin";

  return (
    <div className="flex min-h-screen bg-bg text-white">
      <aside className="w-60 shrink-0 bg-sidebar px-2.5 pt-[26px] pb-4 flex flex-col">
        <div className="px-4 mb-9">
          <Logo className="h-8" />
          <div className="text-[10px] text-muted mt-1.5">Admin console</div>
        </div>

        <nav className="flex flex-col gap-3">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end
              className={({ isActive }) =>
                `flex items-center gap-2.5 h-10 pl-4 pr-2 rounded-control text-[13px] font-semibold whitespace-nowrap transition-colors ${
                  isActive ? "bg-accent text-ink" : "text-white/90 hover:bg-white/5"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`w-2.5 h-2.5 shrink-0 rounded-[3px] ${isActive ? "bg-ink" : "bg-muted/70"}`} />
                  {n.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto mx-1 flex items-center gap-3 rounded-control bg-card px-3 h-[54px]">
          <div className="w-8 h-8 rounded-full bg-accent shrink-0 grid place-items-center text-[11px] font-bold text-ink">
            {initials(name) || "A"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold truncate">{name}</div>
            <div className="text-[10px] text-muted">Flora Food Group</div>
          </div>
          <LogoutButton />
        </div>
      </aside>

      <div className="flex-1 min-w-0 px-8 pt-[14px] pb-10">
        <header className="flex items-center h-[44px] mb-[38px] pr-3">
          <h1 className="text-[22px] font-semibold">{title}</h1>
          {SEARCH_HINT[pathname] && (
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={SEARCH_HINT[pathname]}
              aria-label="Search this page"
              className="ml-auto w-[300px] h-9 rounded-control bg-card px-4 text-xs text-white placeholder:text-muted outline-none focus:ring-1 focus:ring-accent"
            />
          )}
        </header>
        <Outlet context={{ query }} />
      </div>
    </div>
  );
}
