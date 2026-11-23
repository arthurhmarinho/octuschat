import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: { deep: "var(--bg-deep)", DEFAULT: "var(--bg)" },
        card: "var(--card)",
        raised: "var(--raised)",
        line: { DEFAULT: "var(--line)", strong: "var(--line-strong)" },
        fg: { DEFAULT: "var(--fg)", 2: "var(--fg-2)", 3: "var(--fg-3)" },
        "on-fg": "var(--on-fg)",
        positive: "var(--positive)",
        negative: "var(--negative)",
        warning: "var(--warning)",
      },
      borderRadius: {
        sm: "4px",
        control: "8px",
        card: "12px",
        panel: "16px",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      transitionDuration: {
        150: "150ms",
        200: "200ms",
      },
    },
  },
  plugins: [],
};

export default config;
