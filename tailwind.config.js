/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          tertiary: 'var(--bg-tertiary)',
        },
        amber: 'var(--accent-amber)',
        cyan: 'var(--accent-cyan)',
        success: 'var(--accent-emerald)',
        error: 'var(--accent-error)',
        border: {
          DEFAULT: 'var(--border)',
          accent: 'var(--border-accent)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        accent: {
          amber: 'var(--accent-amber)',
          'amber-soft': 'var(--accent-amber-soft)',
          cyan: 'var(--accent-cyan)',
          'cyan-soft': 'var(--accent-cyan-soft)',
          emerald: 'var(--accent-emerald)',
          violet: 'var(--accent-violet)',
        },
        discord: 'var(--discord)',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-subtle': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in': 'slideIn 240ms cubic-bezier(0.25, 0.8, 0.25, 1)',
        'fade-in': 'fadeIn 200ms ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(-100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
