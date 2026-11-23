import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: { deep: "rgb(var(--bg-deep-rgb) / <alpha-value>)", DEFAULT: "rgb(var(--bg-rgb) / <alpha-value>)" },
        card: "rgb(var(--card-rgb) / <alpha-value>)",
        raised: "rgb(var(--raised-rgb) / <alpha-value>)",
        line: { DEFAULT: "var(--line)", strong: "var(--line-strong)" },
        fg: { DEFAULT: "rgb(var(--fg-rgb) / <alpha-value>)", 2: "rgb(var(--fg-2-rgb) / <alpha-value>)", 3: "rgb(var(--fg-3-rgb) / <alpha-value>)" },
        "on-fg": "rgb(var(--on-fg-rgb) / <alpha-value>)",
        positive: "rgb(var(--positive-rgb) / <alpha-value>)",
        negative: "rgb(var(--negative-rgb) / <alpha-value>)",
        warning: "rgb(var(--warning-rgb) / <alpha-value>)",
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
