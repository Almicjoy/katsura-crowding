/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,jsx,ts,tsx}",
    "./src/components/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        serif: ['Merriweather', 'serif'],
        body: ['Open Sans', 'sans-serif']
      },
      colors: {
        primary: {
          DEFAULT: "#00205B",
        },
      },
    },
  },
  plugins: [
  ],
}
