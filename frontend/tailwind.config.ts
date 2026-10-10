import type { Config } from "tailwindcss";

/**
 * Aarogya Bindu design system.
 * Clean medical-technology aesthetic: teal primary, blue accents,
 * white surfaces, slate neutrals.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
          800: "#115e59",
          900: "#134e4a",
          950: "#042f2e",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(2 32 30 / 0.06), 0 8px 24px -8px rgb(2 32 30 / 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
