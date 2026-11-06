// Header search box -> pages. AppShell keeps the query and passes it through <Outlet context>;
// each page filters its own rows with matches(). Case- and spacing-insensitive, every word must match
// somewhere ("naivas ori" finds BB ORI rows at any Naivas branch).
import { useOutletContext } from "react-router-dom";

export function useSearch() {
  return useOutletContext()?.query ?? "";
}

export function matches(query, ...fields) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const hay = fields.flat().filter((f) => f != null).join(" ").toLowerCase();
  return words.every((w) => hay.includes(w));
}
