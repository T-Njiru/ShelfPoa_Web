/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      // Tokens sampled from the ShelfPoa Figma web frames.
      colors: {
        bg: "#2b2a33",        // main background
        sidebar: "#23222a",
        card: "#38373f",
        field: "#414049",     // inputs / dividers inside cards
        line: "#414049",
        track: "#525259",     // ring + progress tracks
        ink: "#1c1b22",       // text on orange
        muted: "#a8a6ad",
        accent: { DEFAULT: "#f4784e", hover: "#e86a40", deep: "#d96138" },
        ok: "#5cc48a",
        warn: "#f2b84a",
        bad: "#e06159",
        info: "#6badeb",
        "ok-bg": "#1f3b2b",
        "bad-bg": "#3d1f1f",
        "warn-bg": "#3d3321",
        // kept so the existing index.html (<body class="bg-surface-dark">) still works
        surface: { dark: "#2b2a33", card: "#38373f" },
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      borderRadius: { card: "12px", control: "10px" },
    },
  },
  plugins: [],
};
