/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['DM Sans', 'sans-serif'] },
      colors: {
        navy: { 950: '#1c1a26', 900: '#252131', 800: '#302940', 700: '#493c61' },
        ink: 'var(--ink)',
        canvas: 'var(--canvas)',
        muted: 'var(--muted)',
        faint: 'var(--faint)',
        line: 'var(--line)',
        memory: '#6941C6',
      },
      boxShadow: { card: '0 1px 2px rgba(16, 24, 40, 0.04)' },
    },
  },
  plugins: [],
}
