/** @type {import('tailwindcss').Config} */
module.exports = {
  // 콘텐츠 스캔 경로 설정 (Purge 대상)
  content: [
    "./web/templates/**/*.html",
    "./web/static/js/**/*.js",
    "./web/static/css/**/*.css",
    "./app/**/*.py", // Python 파일에서 CSS 클래스 사용 시
  ],
  
  // 다크 모드 설정 (기존 data-bs-theme 속성 활용)
  darkMode: ['class', '[data-bs-theme="dark"]'],
  
  theme: {
    extend: {
      // 기존 common.css 디자인 토큰과 호환되는 커스텀 테마
      colors: {
        // 기존 Bootstrap 색상과 호환
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#0d6efd', // 기존 --ui-primary
          600: '#0b5ed7',
          700: '#0a58ca',
          800: '#084298',
          900: '#052c65',
        },
        success: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#198754', // 기존 --ui-success
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        danger: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#dc3545', // 기존 --ui-danger
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#ffc107', // 기존 --ui-warning
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        info: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0dcaf0', // 기존 --ui-info
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        // 기존 회색 계열 확장
        gray: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#6c757d', // 기존 --ui-muted
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        }
      },
      
      // 기존 폰트 크기 시스템 확장
      fontSize: {
        'xs': '0.75rem',        // 12px
        'sm': '0.9375rem',      // 15px - 기존 --ui-font-size-sm
        'base': '1.0625rem',    // 17px - 기존 --ui-font-size-base
        'lg': '1.125rem',       // 18px - 기존 --ui-font-size-lg
        'xl': '1.25rem',        // 20px - 기존 --ui-font-size-title
        '2xl': '1.3125rem',     // 21px - 기존 --ui-font-size-kpi
        '3xl': '1.5rem',        // 24px
        '4xl': '2rem',          // 32px
        '5xl': '2.5rem',        // 40px
        '6xl': '3rem',          // 48px
      },
      
      // 기존 폰트 두께 시스템
      fontWeight: {
        'normal': '400',        // 기존 --ui-weight-base
        'medium': '500',
        'semibold': '600',      // 기존 --ui-weight-strong
        'bold': '700',          // 기존 --ui-weight-title
        'extrabold': '800',
        'black': '900',
      },
      
      // 한국어 최적화 폰트 패밀리
      fontFamily: {
        'sans': [
          'Simple',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Noto Sans KR',
          'Apple SD Gothic Neo',
          'Malgun Gothic',
          'Arial',
          'sans-serif'
        ],
        'korean': [
          'Simple',
          'Noto Sans KR',
          'Apple SD Gothic Neo',
          'Malgun Gothic',
          'sans-serif'
        ]
      },
      
      // 간격 시스템 (기존 common.css 호환)
      spacing: {
        '0.5': '0.125rem',      // 2px
        '1': '0.25rem',         // 4px
        '1.5': '0.375rem',      // 6px
        '2': '0.5rem',          // 8px
        '2.5': '0.625rem',      // 10px
        '3': '0.75rem',         // 12px
        '3.5': '0.875rem',      // 14px
        '4': '1rem',            // 16px - 기존 --ui-card-padding
        '5': '1.25rem',         // 20px
        '6': '1.5rem',          // 24px
        '7': '1.75rem',         // 28px
        '8': '2rem',            // 32px
        '9': '2.25rem',         // 36px
        '10': '2.5rem',         // 40px
        '11': '2.75rem',        // 44px
        '12': '3rem',           // 48px
        '14': '3.5rem',         // 56px
        '16': '4rem',           // 64px
        '20': '5rem',           // 80px
        '24': '6rem',           // 96px
        '28': '7rem',           // 112px
        '32': '8rem',           // 128px
      },
      
      // 라인 높이 (한국어 최적화)
      lineHeight: {
        'tight': '1.25',
        'snug': '1.375',
        'normal': '1.5',
        'relaxed': '1.6',       // 한국어 가독성 최적화
        'loose': '2',
      },
      
      // 그림자 시스템 확장
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'card-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'card-focus': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },
      
      // 테두리 반지름
      borderRadius: {
        'none': '0',
        'sm': '0.125rem',       // 2px
        'DEFAULT': '0.25rem',   // 4px
        'md': '0.375rem',       // 6px
        'lg': '0.5rem',         // 8px
        'xl': '0.75rem',        // 12px
        '2xl': '1rem',          // 16px
        '3xl': '1.5rem',        // 24px
        'full': '9999px',
      },
      
      // 애니메이션 및 전환 효과
      transitionDuration: {
        '75': '75ms',
        '100': '100ms',
        '150': '150ms',
        '200': '200ms',         // 기본 전환 시간
        '300': '300ms',
        '500': '500ms',
        '700': '700ms',
        '1000': '1000ms',
      },
      
      // 커스텀 애니메이션
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
      },
      
      // 키프레임 정의
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  
  plugins: [
    // 폼 스타일링 플러그인
    require('@tailwindcss/forms')({
      strategy: 'class', // .form-input 클래스 기반 적용
    }),
    
    // 타이포그래피 플러그인
    require('@tailwindcss/typography'),
    
    // 커스텀 컴포넌트 플러그인
    function({ addComponents, theme }) {
      addComponents({
        // 카드 컴포넌트
        '.tw-card': {
          backgroundColor: theme('colors.white'),
          borderRadius: theme('borderRadius.lg'),
          boxShadow: theme('boxShadow.card'),
          border: `1px solid ${theme('colors.gray.200')}`,
          transition: theme('transitionDuration.200'),
          
          '&:hover': {
            boxShadow: theme('boxShadow.card-hover'),
          },
          
          // 다크 모드
          '@media (prefers-color-scheme: dark)': {
            backgroundColor: theme('colors.gray.800'),
            borderColor: theme('colors.gray.700'),
          },
          
          '[data-bs-theme="dark"] &': {
            backgroundColor: theme('colors.gray.800'),
            borderColor: theme('colors.gray.700'),
          },
        },
        
        '.tw-card-header': {
          padding: `${theme('spacing.3')} ${theme('spacing.4')}`,
          borderBottom: `1px solid ${theme('colors.gray.200')}`,
          fontWeight: theme('fontWeight.semibold'),
          fontSize: theme('fontSize.sm'),
          backgroundColor: theme('colors.gray.50'),
          
          '[data-bs-theme="dark"] &': {
            backgroundColor: theme('colors.gray.700'),
            borderBottomColor: theme('colors.gray.600'),
          },
        },
        
        '.tw-card-body': {
          padding: theme('spacing.4'),
        },
        
        '.tw-card-title': {
          fontSize: theme('fontSize.lg'),
          fontWeight: theme('fontWeight.semibold'),
          marginBottom: theme('spacing.2'),
        },
        
        // 버튼 컴포넌트
        '.tw-btn': {
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: `${theme('spacing.2')} ${theme('spacing.4')}`,
          fontSize: theme('fontSize.sm'),
          fontWeight: theme('fontWeight.medium'),
          borderRadius: theme('borderRadius.md'),
          transition: `color ${theme('transitionDuration.200')}, background-color ${theme('transitionDuration.200')}, border-color ${theme('transitionDuration.200')}`,
          cursor: 'pointer',
          border: '1px solid transparent',
          
          '&:focus': {
            outline: 'none',
            boxShadow: `0 0 0 3px ${theme('colors.primary.500')}40`,
          },
          
          '&:disabled': {
            opacity: '0.5',
            cursor: 'not-allowed',
          },
        },
        
        '.tw-btn-primary': {
          backgroundColor: theme('colors.primary.600'),
          color: theme('colors.white'),
          
          '&:hover:not(:disabled)': {
            backgroundColor: theme('colors.primary.700'),
          },
        },
        
        '.tw-btn-secondary': {
          backgroundColor: theme('colors.gray.600'),
          color: theme('colors.white'),
          
          '&:hover:not(:disabled)': {
            backgroundColor: theme('colors.gray.700'),
          },
        },
        
        '.tw-btn-outline': {
          borderColor: theme('colors.gray.300'),
          backgroundColor: theme('colors.white'),
          color: theme('colors.gray.700'),
          
          '&:hover:not(:disabled)': {
            backgroundColor: theme('colors.gray.50'),
          },
          
          '[data-bs-theme="dark"] &': {
            borderColor: theme('colors.gray.600'),
            backgroundColor: theme('colors.gray.800'),
            color: theme('colors.gray.200'),
            
            '&:hover:not(:disabled)': {
              backgroundColor: theme('colors.gray.700'),
            },
          },
        },
        
        '.tw-btn-sm': {
          padding: `${theme('spacing.1.5')} ${theme('spacing.3')}`,
          fontSize: theme('fontSize.xs'),
        },
        
        '.tw-btn-lg': {
          padding: `${theme('spacing.3')} ${theme('spacing.6')}`,
          fontSize: theme('fontSize.base'),
        },
        
        // 배지 컴포넌트
        '.tw-badge': {
          display: 'inline-flex',
          alignItems: 'center',
          padding: `${theme('spacing.0.5')} ${theme('spacing.2.5')}`,
          borderRadius: theme('borderRadius.full'),
          fontSize: theme('fontSize.xs'),
          fontWeight: theme('fontWeight.semibold'),
        },
        
        '.tw-badge-success': {
          backgroundColor: theme('colors.success.100'),
          color: theme('colors.success.800'),
          
          '[data-bs-theme="dark"] &': {
            backgroundColor: theme('colors.success.900'),
            color: theme('colors.success.200'),
          },
        },
        
        '.tw-badge-danger': {
          backgroundColor: theme('colors.danger.100'),
          color: theme('colors.danger.800'),
          
          '[data-bs-theme="dark"] &': {
            backgroundColor: theme('colors.danger.900'),
            color: theme('colors.danger.200'),
          },
        },
        
        '.tw-badge-warning': {
          backgroundColor: theme('colors.warning.100'),
          color: theme('colors.warning.800'),
          
          '[data-bs-theme="dark"] &': {
            backgroundColor: theme('colors.warning.900'),
            color: theme('colors.warning.200'),
          },
        },
        
        '.tw-badge-info': {
          backgroundColor: theme('colors.info.100'),
          color: theme('colors.info.800'),
          
          '[data-bs-theme="dark"] &': {
            backgroundColor: theme('colors.info.900'),
            color: theme('colors.info.200'),
          },
        },
        
        '.tw-badge-secondary': {
          backgroundColor: theme('colors.gray.100'),
          color: theme('colors.gray.800'),
          
          '[data-bs-theme="dark"] &': {
            backgroundColor: theme('colors.gray.700'),
            color: theme('colors.gray.200'),
          },
        },
      });
    },
    
    // 유틸리티 클래스 추가
    function({ addUtilities, theme }) {
      addUtilities({
        // 한국어 폰트 최적화
        '.font-korean': {
          fontFamily: theme('fontFamily.korean').join(', '),
        },
        
        // 라인 높이 최적화
        '.leading-relaxed-ko': {
          lineHeight: '1.6',
        },
        
        // 전환 효과
        '.transition-all-200': {
          transition: `all ${theme('transitionDuration.200')} ease-in-out`,
        },
        
        '.transition-colors-200': {
          transition: `color ${theme('transitionDuration.200')} ease-in-out, background-color ${theme('transitionDuration.200')} ease-in-out, border-color ${theme('transitionDuration.200')} ease-in-out`,
        },
        
        // 그림자 유틸리티
        '.shadow-card': {
          boxShadow: theme('boxShadow.card'),
        },
        
        '.shadow-card-hover': {
          boxShadow: theme('boxShadow.card-hover'),
        },
        
        // 기존 common.css 호환 유틸리티
        '.tw-title': {
          fontSize: theme('fontSize.xl'),
          fontWeight: theme('fontWeight.bold'),
          color: theme('colors.gray.900'),
          
          '[data-bs-theme="dark"] &': {
            color: theme('colors.gray.100'),
          },
        },
        
        '.tw-strong': {
          fontWeight: theme('fontWeight.semibold'),
        },
        
        '.tw-muted': {
          color: theme('colors.gray.500'),
        },
        
        '.tw-kpi': {
          fontSize: theme('fontSize.2xl'),
          fontWeight: theme('fontWeight.semibold'),
        },
      });
    },
  ],
  
  // 중요도 설정 (Bootstrap과의 충돌 방지)
  important: false, // 필요 시 true로 변경
  
  // 접두사 설정 (Bootstrap과 공존 시)
  prefix: '', // 'tw-' 접두사 사용 시 'tw-'로 설정
  
  // 코어 플러그인 비활성화 (필요 시)
  corePlugins: {
    // container: false, // Bootstrap container 사용 시
    // preflight: false, // CSS 리셋 비활성화 시
  },
};
