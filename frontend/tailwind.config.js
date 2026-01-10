/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // NVIDIA Brand Colors
        nvidia: {
          green: '#76b900',
          'green-dark': '#5a8c00',
          'green-light': '#8ed100',
        },
        // Dark theme colors
        dark: {
          bg: '#0a0a0a',
          'bg-secondary': '#111111',
          'bg-tertiary': '#1a1a1a',
          'bg-card': '#141414',
          border: '#2a2a2a',
          'border-light': '#333333',
        },
        // Text colors for dark theme
        'text-primary': '#ffffff',
        'text-secondary': '#a0a0a0',
        'text-muted': '#666666',
        // Status colors
        status: {
          success: '#22c55e',
          warning: '#f59e0b',
          error: '#ef4444',
          info: '#3b82f6',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'nvidia': '0 0 20px rgba(118, 185, 0, 0.15)',
        'nvidia-lg': '0 0 40px rgba(118, 185, 0, 0.2)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 10px 25px -5px rgba(0, 0, 0, 0.4)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(118, 185, 0, 0.2)' },
          '100%': { boxShadow: '0 0 20px rgba(118, 185, 0, 0.4)' },
        }
      }
    },
  },
  plugins: [],
}
