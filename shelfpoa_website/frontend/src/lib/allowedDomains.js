// "Continue with Google" is limited to Flora Food Group accounts.
// Set VITE_ALLOWED_EMAIL_DOMAINS (comma-separated) to change the list; keep it the same as the
// backend's ALLOWED_EMAIL_DOMAINS and the Android app's AllowedDomains.kt. The backend checks this
// again on every request, so editing it here alone can't let anyone in.
export const ALLOWED_DOMAINS = (import.meta.env.VITE_ALLOWED_EMAIL_DOMAINS || "upfield.com,florafoodgroup.com")
  .split(",")
  .map((d) => d.trim().toLowerCase().replace(/^@/, ""))
  .filter(Boolean);

export function emailAllowed(email) {
  const domain = (email || "").toLowerCase().split("@").pop();
  return Boolean(email?.includes("@")) && ALLOWED_DOMAINS.includes(domain);
}

export const domainList = () => ALLOWED_DOMAINS.map((d) => `@${d}`).join(" or ");
