/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      // Innóvate 4.0 brand palette (no other colors allowed).
      colors: {
        brand: {
          blue: "#1d254c",
          red: "#c50339",
        },
      },
      // Brand typography: Roboto Slab for headings, Inter for body and UI.
      fontFamily: {
        slab: ['"Roboto Slab"', "serif"],
        sans: ["Inter", "sans-serif"],
      },
      // Border-radius is 0px on every element per brand guidelines.
      borderRadius: {
        none: "0px",
      },
    },
  },
  plugins: [],
};
