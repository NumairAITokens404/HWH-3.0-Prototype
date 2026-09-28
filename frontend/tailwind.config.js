/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: { 950: '#101828', 900: '#172033', 800: '#1D2939', 700: '#344054' },
        ink: '#172033',
        canvas: '#F6F7F9',
        muted: '#667085',
        faint: '#98A2B3',
        line: '#E4E7EC',
        memory: '#6941C6',
      },
      boxShadow: { card: '0 1px 2px rgba(16, 24, 40, 0.04)' },
    },
  },
  plugins: [],
}
