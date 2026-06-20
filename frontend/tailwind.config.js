/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
        extend: {
                fontFamily: {
                        heading: ['Space Grotesk', 'system-ui', 'sans-serif'],
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                        mono: ['Kode Mono', 'monospace'],
                },
                backgroundImage: {
                        'gradient-brand': 'linear-gradient(90deg, #C2185B 0%, #6A1B9A 50%, #1565C0 100%)',
                },
                borderRadius: {
                        lg: 'var(--radius)',
                        md: 'calc(var(--radius) - 2px)',
                        sm: 'calc(var(--radius) - 4px)'
                },
                colors: {
                        ink: '#000000',
                        'ink-2': '#121212',
                        electric: '#6A1B9A',
                        'electric-light': '#C2185B',
                        cyan: '#C2185B',
                        background: 'hsl(var(--background))',
                        foreground: 'hsl(var(--foreground))',
                        card: {
                                DEFAULT: 'hsl(var(--card))',
                                foreground: 'hsl(var(--card-foreground))'
                        },
                        popover: {
                                DEFAULT: 'hsl(var(--popover))',
                                foreground: 'hsl(var(--popover-foreground))'
                        },
                        primary: {
                                DEFAULT: 'hsl(var(--primary))',
                                foreground: 'hsl(var(--primary-foreground))'
                        },
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))'
                        },
                        muted: {
                                DEFAULT: 'hsl(var(--muted))',
                                foreground: 'hsl(var(--muted-foreground))'
                        },
                        accent: {
                                DEFAULT: 'hsl(var(--accent))',
                                foreground: 'hsl(var(--accent-foreground))'
                        },
                        destructive: {
                                DEFAULT: 'hsl(var(--destructive))',
                                foreground: 'hsl(var(--destructive-foreground))'
                        },
                        border: 'hsl(var(--border))',
                        input: 'hsl(var(--input))',
                        ring: 'hsl(var(--ring))'
                },
                keyframes: {
                        'accordion-down': {
                                from: { height: '0' },
                                to: { height: 'var(--radix-accordion-content-height)' }
                        },
                        'accordion-up': {
                                from: { height: 'var(--radix-accordion-content-height)' },
                                to: { height: '0' }
                        },
                        'pulse-glow': {
                                '0%, 100%': { opacity: '0.6' },
                                '50%': { opacity: '1' }
                        },
                        'marquee': {
                                '0%': { transform: 'translateX(0)' },
                                '100%': { transform: 'translateX(-50%)' }
                        }
                },
                animation: {
                        'accordion-down': 'accordion-down 0.2s ease-out',
                        'accordion-up': 'accordion-up 0.2s ease-out',
                        'pulse-glow': 'pulse-glow 3s ease-in-out infinite',
                        'marquee': 'marquee 30s linear infinite'
                }
        }
  },
  plugins: [require("tailwindcss-animate")],
};
