/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Modern Light Fintech Palette (Paytm-inspired)
        bg: '#f8fafc',
        surface: '#ffffff',
        surface2: '#f1f5f9',
        surface3: '#e2e8f0',
        border: '#e2e8f0',
        border2: '#cbd5e1',
        textPrimary: '#0f172a',    // Dark navy / slate-900
        textSecondary: '#475569',  // Slate-600
        textMuted: '#64748b',      // Slate-500
        accent: '#0052cc',         // Fintech Royal Blue
        accent2: '#4338ca',        // Indigo
        accent3: '#6366f1',        // Soft AI Indigo
        paytm: '#00baf2',          // Paytm Cyan Blue
        paytmNavy: '#002970',      // Paytm Deep Corporate Navy
        paytmLight: '#f0f9ff',     // Paytm Tinted Background
        success: '#16a34a',        // Fresh Fintech Green
        warning: '#d97706',        // Amber Alert
        danger: '#dc2626',         // Red Alert
        orange: '#ea580c',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      borderRadius: {
        card: '14px',
        sm: '8px',
        full: '9999px',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.06)',
        'card-hover': '0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)',
        subtle: '0 1px 2px 0 rgba(0, 0, 0, 0.04)',
      },
      width: {
        sidebar: '260px',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.35s ease-out both',
        'pulse-slow': 'pulse 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
