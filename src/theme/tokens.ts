/**
 * Design Tokens for Zeno Desktop AI Assistant
 * Restrained dark theme: Neutral charcoal/slate base, single indigo accent, semantic status badges.
 * WCAG AA compliant contrast ratios. No neon glows or AI gradients.
 */

export const tokens = {
  colors: {
    bg: {
      canvas: '#0B0D13',
      surface: '#12151F',
      subtle: '#181D2B',
      card: '#151926',
      cardHover: '#1C2233',
      input: '#0F121B',
      overlay: 'rgba(5, 7, 12, 0.75)',
    },
    border: {
      subtle: '#1F2637',
      default: '#2B344B',
      active: '#404E6E',
      focus: '#6366F1',
    },
    text: {
      primary: '#F1F5F9',
      secondary: '#94A3B8',
      muted: '#64748B',
      disabled: '#475569',
      inverse: '#0B0D13',
    },
    accent: {
      primary: '#6366F1',       // Indigo
      primaryHover: '#4F46E5',
      primaryActive: '#4338CA',
      subtle: 'rgba(99, 102, 241, 0.12)',
      border: 'rgba(99, 102, 241, 0.3)',
    },
    status: {
      success: {
        text: '#34D399',
        bg: 'rgba(16, 185, 129, 0.12)',
        border: 'rgba(16, 185, 129, 0.3)',
      },
      warning: {
        text: '#FBBF24',
        bg: 'rgba(245, 158, 11, 0.12)',
        border: 'rgba(245, 158, 11, 0.3)',
      },
      error: {
        text: '#F87171',
        bg: 'rgba(239, 68, 68, 0.12)',
        border: 'rgba(239, 68, 68, 0.3)',
      },
      info: {
        text: '#60A5FA',
        bg: 'rgba(59, 130, 246, 0.12)',
        border: 'rgba(59, 130, 246, 0.3)',
      },
      pending: {
        text: '#94A3B8',
        bg: 'rgba(148, 163, 184, 0.1)',
        border: 'rgba(148, 163, 184, 0.25)',
      },
    },
  },
  typography: {
    fontFamily: {
      sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      mono: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    },
  },
  radius: {
    xs: '4px',
    sm: '6px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
};
