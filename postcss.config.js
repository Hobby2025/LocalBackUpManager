module.exports = {
  plugins: {
    // Tailwind CSS 처리
    tailwindcss: {},
    
    // CSS 벤더 프리픽스 자동 추가
    autoprefixer: {},
    
    // 프로덕션 환경에서 CSS 최적화
    ...(process.env.NODE_ENV === 'production' ? {
      // CSS 압축 및 최적화
      cssnano: {
        preset: ['default', {
          // 주석 제거
          discardComments: {
            removeAll: true,
          },
          // 중복 규칙 제거
          discardDuplicates: true,
          // 빈 규칙 제거
          discardEmpty: true,
          // 사용하지 않는 CSS 제거
          discardUnused: true,
          // 색상 값 최적화
          colormin: true,
          // 폰트 패밀리 최적화
          minifyFontValues: true,
          // 그라데이션 최적화
          minifyGradients: true,
          // 선택자 최적화
          minifySelectors: true,
          // URL 최적화
          normalizeUrl: true,
          // 공백 제거
          normalizeWhitespace: true,
        }],
      },
      
      // PurgeCSS - 사용하지 않는 CSS 제거
      '@fullhuman/postcss-purgecss': {
        content: [
          './web/templates/**/*.html',
          './web/static/js/**/*.js',
          './app/**/*.py',
        ],
        
        // 제거하지 않을 클래스 패턴
        safelist: [
          // Bootstrap 동적 클래스
          /^btn-/,
          /^text-bg-/,
          /^badge-/,
          /^alert-/,
          /^bg-/,
          /^text-/,
          /^border-/,
          
          // Chart.js 클래스
          /^chart/,
          /^canvas/,
          
          // SweetAlert2 클래스
          /^swal/,
          
          // 동적으로 생성되는 클래스
          /^tw-/,
          /^hover:/,
          /^focus:/,
          /^active:/,
          /^disabled:/,
          /^dark:/,
          
          // 상태 기반 클래스
          'show',
          'hide',
          'active',
          'disabled',
          'loading',
          'error',
          'success',
          
          // Bootstrap JavaScript 컴포넌트
          'modal-open',
          'modal-backdrop',
          'fade',
          'show',
          'collapse',
          'collapsing',
          'dropdown-menu',
          'dropdown-item',
          'nav-link',
          'navbar-toggler',
          'navbar-collapse',
        ],
        
        // 기본 추출기 설정
        defaultExtractor: content => {
          // HTML 클래스 추출
          const htmlClasses = content.match(/class="[^"]*"/g) || [];
          const classes = htmlClasses.join(' ').match(/[A-Za-z0-9_-]+/g) || [];
          
          // Tailwind 클래스 패턴 추출
          const tailwindClasses = content.match(/[A-Za-z0-9_-]*[:]?[A-Za-z0-9_-]+/g) || [];
          
          return [...classes, ...tailwindClasses];
        },
        
        // 추출기 설정
        extractors: [
          {
            extractor: content => {
              // Python 파일에서 CSS 클래스 추출
              const pythonClasses = content.match(/class[=\s]*['"](.*?)['"]/g) || [];
              return pythonClasses.map(match => 
                match.replace(/class[=\s]*['"]/, '').replace(/['"]/, '')
              ).join(' ').split(/\s+/);
            },
            extensions: ['py'],
          },
          {
            extractor: content => {
              // JavaScript 파일에서 CSS 클래스 추출
              const jsClasses = content.match(/['"](.*?)['"]/g) || [];
              return jsClasses.map(match => 
                match.replace(/['"]/g, '')
              ).filter(cls => 
                cls.includes('-') || cls.includes('_') || /^[a-z]/i.test(cls)
              );
            },
            extensions: ['js'],
          },
        ],
        
        // 화이트리스트 패턴
        whitelistPatterns: [
          /^tw-/,
          /^hover:/,
          /^focus:/,
          /^active:/,
          /^disabled:/,
          /^dark:/,
          /^sm:/,
          /^md:/,
          /^lg:/,
          /^xl:/,
          /^2xl:/,
        ],
        
        // 화이트리스트 패턴 (children)
        whitelistPatternsChildren: [
          /^token/,
          /^pre/,
          /^code/,
          /^chart/,
          /^swal/,
        ],
      },
    } : {}),
  },
};
