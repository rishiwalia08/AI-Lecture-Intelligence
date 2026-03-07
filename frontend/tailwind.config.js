/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#0f172a',
          card: '#1e293b',
          accent: '#6366f1',
        },
      },
      boxShadow: {
        glass: '0 8px 32px rgba(15, 23, 42, 0.35)',
      },
      keyframes: {
        pulseDot: {
          '0%, 100%': { opacity: '0.3' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        pulseDot: 'pulseDot 1.3s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
