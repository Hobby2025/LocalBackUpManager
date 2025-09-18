# Tailwind CSS 도입 및 점진 전환 계획

## 📋 개요

Bootstrap 5 기반 시스템에서 Tailwind CSS로 점진적 전환을 통해 더 유연하고 현대적인 UI 시스템을 구축합니다.

## 🎯 도입 전략

### 1. 도입 방식: CDN 시범 도입
- **선택 근거**: 빠른 실험, 위험도 최소화, 기존 시스템과 호환성 유지
- **장점**: 즉시 적용 가능, 빌드 설정 불필요, 롤백 용이
- **단점**: 번들 크기 최적화 제한, 커스터마이징 제한

### 2. 디자인 토큰 전략: 병행 운영
- **기존 common.css**: 유지하면서 점진적 축소
- **Tailwind 커스텀**: tailwind-config.css로 확장
- **호환성**: CSS 변수 기반으로 일관성 유지

## 🔧 구현 현황

### ✅ 완료된 작업

#### 1. 기본 설정
- [x] CDN 방식 도입 결정
- [x] tailwind-config.css 생성
- [x] 디자인 토큰 매핑 완료

#### 2. 템플릿 설정
- [x] dashboard.html에 Tailwind CDN 추가
- [x] 커스텀 설정 파일 연결

#### 3. 시범 컴포넌트 적용
- [x] **헤더**: 대시보드 제목에 `tw-title` 클래스 적용
- [x] **버튼**: 알림 이력, 보고서 목록 버튼에 Tailwind 스타일 적용
- [x] **카드**: 시스템 상태 카드에 `tw-card` 컴포넌트 적용
- [x] **내비게이션**: 브랜드 로고에 Tailwind 폰트 스타일 적용

### 🔄 진행 중인 작업

#### 4. 성능 최적화
- [ ] Purge 설정 (빌드 방식 전환 시)
- [ ] 번들 크기 측정 및 비교
- [ ] 로딩 성능 검증

#### 5. 전체 마이그레이션
- [ ] 나머지 카드 컴포넌트 전환
- [ ] 테이블 컴포넌트 전환
- [ ] 폼 컴포넌트 전환
- [ ] 모달 컴포넌트 전환

## 📊 Bootstrap 의존성 분석

### 현재 사용 중인 Bootstrap 컴포넌트

#### 1. 레이아웃 시스템
```html
<!-- 계속 사용 (Tailwind 대체 복잡) -->
<div class="container my-4">
<div class="row g-3">
<div class="col-12 col-md-3">
```

#### 2. 내비게이션
```html
<!-- 부분 전환 가능 -->
<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
<div class="navbar-collapse" id="navbarNav">
<ul class="navbar-nav ms-auto">
```

#### 3. 버튼
```html
<!-- ✅ 전환 완료 -->
<!-- 기존: <button class="btn btn-primary btn-sm"> -->
<!-- 신규: <button class="tw-btn tw-btn-primary tw-btn-sm"> -->
```

#### 4. 카드
```html
<!-- ✅ 부분 전환 완료 -->
<!-- 기존: <div class="card h-100"> -->
<!-- 신규: <div class="tw-card h-100"> -->
```

#### 5. 폼 컴포넌트
```html
<!-- 전환 예정 -->
<select class="form-select form-select-sm">
<input class="form-check-input" type="checkbox">
<label class="form-check-label">
```

#### 6. 모달 및 드롭다운
```html
<!-- JavaScript 의존성으로 유지 -->
<div class="modal" data-bs-toggle="modal">
<div class="dropdown-menu dropdown-menu-end">
```

#### 7. 유틸리티 클래스
```html
<!-- 점진적 전환 -->
<div class="d-flex justify-content-between align-items-center mb-3">
<!-- Tailwind: flex justify-between items-center mb-3 -->
```

### 전환 우선순위

#### 🟢 높은 우선순위 (전환 권장)
1. **버튼**: 완전 전환 가능, 스타일 일관성 향상
2. **카드**: 그림자, 호버 효과 등 향상된 UX
3. **타이포그래피**: 폰트 크기, 두께 세밀한 제어
4. **색상**: 더 풍부한 색상 팔레트
5. **간격**: 더 정교한 spacing 시스템

#### 🟡 중간 우선순위 (선택적 전환)
1. **폼 컴포넌트**: 커스텀 스타일링 필요 시
2. **테이블**: 복잡한 레이아웃이 아닌 경우
3. **배지**: 더 다양한 스타일 옵션

#### 🔴 낮은 우선순위 (유지 권장)
1. **그리드 시스템**: Bootstrap의 강력한 기능
2. **내비게이션**: JavaScript 의존성
3. **모달**: Bootstrap JavaScript 필요
4. **드롭다운**: Bootstrap JavaScript 필요

## 🎨 디자인 토큰 매핑

### 색상 시스템
```css
/* 기존 common.css */
--ui-primary: #0d6efd;
--ui-success: #198754;
--ui-danger: #dc3545;

/* Tailwind 확장 */
--color-primary-500: #0d6efd;
--color-success-500: #198754;
--color-danger-500: #dc3545;
```

### 폰트 시스템
```css
/* 기존 */
--ui-font-size-base: 1.0625rem;   /* 17px */
--ui-font-size-title: 1.25rem;    /* 20px */
--ui-weight-strong: 600;

/* Tailwind 호환 */
--font-size-base: 1.0625rem;
--font-size-xl: 1.25rem;
--font-weight-semibold: 600;
```

### 간격 시스템
```css
/* 기존 */
--ui-card-padding: 1rem;

/* Tailwind 호환 */
--spacing-4: 1rem;
```

## 📈 성능 측정 계획

### 1. 번들 크기 비교
```bash
# 현재 (Bootstrap 5 + common.css)
- bootstrap.min.css: ~160KB
- common.css: ~4KB
- 총합: ~164KB

# Tailwind CDN 추가 후
- bootstrap.min.css: ~160KB
- common.css: ~4KB
- tailwind CDN: ~300KB (전체 포함)
- tailwind-config.css: ~8KB
- 총합: ~472KB
```

### 2. 로딩 성능 측정
- **First Contentful Paint (FCP)**
- **Largest Contentful Paint (LCP)**
- **Cumulative Layout Shift (CLS)**

### 3. 런타임 성능
- **CSS 파싱 시간**
- **렌더링 성능**
- **메모리 사용량**

## 🧪 테스트 계획

### 1. 시각적 회귀 테스트
```javascript
// 기존 스타일과 새 스타일 비교
const components = [
  'dashboard-header',
  'system-status-card',
  'navigation-bar',
  'action-buttons'
];

components.forEach(component => {
  test(`${component} visual regression`, () => {
    // 스크린샷 비교 테스트
  });
});
```

### 2. 접근성 테스트
- **색상 대비**: WCAG 2.1 AA 기준
- **키보드 내비게이션**: Tab 순서 확인
- **스크린 리더**: aria-label 등 확인

### 3. 크로스 브라우저 테스트
- **Chrome**: 최신 버전
- **Firefox**: 최신 버전
- **Safari**: 최신 버전
- **Edge**: 최신 버전

## 🚀 다음 단계

### Phase 1: 기본 컴포넌트 전환 (1-2주)
- [ ] 모든 버튼 컴포넌트 전환
- [ ] 모든 카드 컴포넌트 전환
- [ ] 타이포그래피 시스템 통합

### Phase 2: 고급 컴포넌트 전환 (2-3주)
- [ ] 테이블 컴포넌트 전환
- [ ] 폼 컴포넌트 전환
- [ ] 배지 및 알림 컴포넌트 전환

### Phase 3: 최적화 및 정리 (1주)
- [ ] 빌드 시스템 전환 (CDN → PostCSS)
- [ ] Purge 설정으로 번들 크기 최적화
- [ ] 사용하지 않는 Bootstrap 컴포넌트 제거

### Phase 4: 문서화 및 가이드라인 (1주)
- [ ] 컴포넌트 스타일 가이드 작성
- [ ] 개발자 가이드라인 업데이트
- [ ] 성능 최적화 문서 작성

## 📝 마이그레이션 체크리스트

### 컴포넌트별 전환 상태

#### 버튼 컴포넌트
- [x] 기본 버튼 (primary, secondary, outline)
- [x] 크기 변형 (sm, base, lg)
- [ ] 아이콘 버튼
- [ ] 로딩 상태 버튼

#### 카드 컴포넌트
- [x] 기본 카드 (header, body, footer)
- [x] 호버 효과
- [ ] 이미지 카드
- [ ] 액션 카드

#### 내비게이션
- [x] 브랜드 로고
- [ ] 내비게이션 링크
- [ ] 드롭다운 메뉴
- [ ] 모바일 토글

#### 폼 컴포넌트
- [ ] 입력 필드
- [ ] 선택 박스
- [ ] 체크박스/라디오
- [ ] 폼 검증 스타일

#### 테이블
- [ ] 기본 테이블
- [ ] 정렬 가능 테이블
- [ ] 페이지네이션
- [ ] 필터링

### 성능 최적화
- [ ] CSS 번들 크기 측정
- [ ] 로딩 성능 측정
- [ ] Purge 설정 적용
- [ ] 미사용 CSS 제거

### 품질 보증
- [ ] 시각적 회귀 테스트
- [ ] 접근성 테스트
- [ ] 크로스 브라우저 테스트
- [ ] 모바일 반응형 테스트

## 🔍 문제 해결 가이드

### 1. 스타일 충돌 문제
```css
/* 해결책: CSS 우선순위 조정 */
.tw-btn {
  @apply !important; /* Tailwind important 사용 */
}

/* 또는 Bootstrap 스타일 오버라이드 */
.btn.tw-btn {
  /* Tailwind 스타일 */
}
```

### 2. JavaScript 의존성 문제
```javascript
// Bootstrap JavaScript 기능 유지
// 모달, 드롭다운, 툴팁 등은 Bootstrap JS 계속 사용
import 'bootstrap/js/dist/modal';
import 'bootstrap/js/dist/dropdown';
```

### 3. 다크 모드 호환성
```css
/* CSS 변수 기반 다크 모드 유지 */
:root[data-bs-theme="dark"] .tw-card {
  @apply bg-gray-800 border-gray-700;
}
```

이 계획에 따라 안전하고 체계적인 Tailwind CSS 전환을 진행할 수 있습니다.
