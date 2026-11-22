/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Water category — teal
        water: {
          DEFAULT: "#0d9488",
          light: "#ccfbf1",
          dark: "#0f766e",
        },
        // Severity scale
        severity: {
          info: "#6b7280",
          low: "#16a34a",
          moderate: "#ca8a04",
          high: "#ea580c",
          critical: "#dc2626",
        },
        // Surfaces
        surface: "#f7f8fa",
        border: "#e5e7eb",
        muted: "#57606a",
        accent: "#3b82d4",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "-apple-system",
          "Segoe UI",
          "system-ui",
          "sans-serif",
        ],
        mono: ["ui-monospace", "JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        "2xs": ["12px", { lineHeight: "1.6" }],
        xs: ["12px", { lineHeight: "1.6" }],
        sm: ["14px", { lineHeight: "1.6" }],
        base: ["16px", { lineHeight: "1.6" }],
        lg: ["20px", { lineHeight: "1.4" }],
        xl: ["28px", { lineHeight: "1.3" }],
      },
      borderRadius: {
        control: "6px",
        panel: "10px",
      },
      spacing: {
        // 4px grid
        0.5: "2px",
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        5: "20px",
        6: "24px",
        8: "32px",
      },
    },
  },
  plugins: [],
};
