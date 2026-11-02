// Runs before `npm run dev` / `npm run build`.
// If tailwind.config.js is an older copy, new colour classes (bg-card, text-ink, …) compile to
// nothing and the UI silently loses its backgrounds and text colours. Fail loudly instead.
import config from "../tailwind.config.js";

const required = [
  "bg", "sidebar", "card", "field", "line", "track", "ink", "muted",
  "accent", "ok", "warn", "bad", "info", "ok-bg", "bad-bg", "warn-bg",
];
const have = Object.keys(config?.theme?.extend?.colors ?? {});
const missing = required.filter((k) => !have.includes(k));

if (missing.length) {
  console.error(
    `\n[ShelfPoa] tailwind.config.js is out of date — missing colour tokens: ${missing.join(", ")}\n` +
      `Replace it with the tailwind.config.js from the latest frontend update, then run the command again.\n`
  );
  process.exit(1);
}
