/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    // Override (not extend) borderRadius so ALL rounded-* utilities produce 0px.
    // Exception: rounded-full stays at 9999px for circular elements (spinners, etc.).
    borderRadius: {
      DEFAULT: "0px",
      none:    "0px",
      sm:      "0px",
      md:      "0px",
      lg:      "0px",
      xl:      "0px",
      "2xl":   "0px",
      "3xl":   "0px",
      full:    "9999px",
    },
    extend: {
      // Innóvate 4.0 brand palette — no other colors allowed.
      colors: {
        brand: {
          blue: "#1d254c",
          red:  "#c50339",
        },
      },
      // Brand typography.
      fontFamily: {
        slab: ['"Roboto Slab"', "serif"],
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
