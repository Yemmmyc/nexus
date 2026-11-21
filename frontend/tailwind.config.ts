import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: "#070b11",
          900: "#0c121b",
          850: "#111926",
          800: "#162030",
          700: "#223047",
        },
        nexus: {
          cyan: "#22d3ee",
          teal: "#14b8a6",
          emerald: "#10b981",
          amber: "#f59e0b",
          crimson: "#f43f5e",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        "cyan-subtle": "0 0 24px -8px rgba(34, 211, 238, 0.25)",
        "panel": "0 8px 30px -12px rgba(0, 0, 0, 0.65)",
      },
    },
  },
  plugins: [],
} satisfies Config;

