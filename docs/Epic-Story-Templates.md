# 에픽 및 스토리 템플릿 가이드

## 📋 개요

이 문서는 LocalBackUpManager 프로젝트의 에픽(Epic)과 스토리(Story) 작성을 위한 표준 템플릿과 가이드라인을 제공합니다.

## 🎯 에픽 템플릿

### Epic Template

```markdown
# Epic: [Epic 제목]

## 📊 기본 정보
- **Epic ID**: EPIC-{YYYY}-{MM}-{순번} (예: EPIC-2025-01-001)
- **Phase**: Phase X.Y
- **우선순위**: Critical/High/Medium/Low
- **담당자**: @username
- **예상 기간**: X주
- **상태**: Planning/In Progress/Review/Done

## 🎯 비즈니스 목표
> 이 에픽을 통해 달성하고자 하는 비즈니스 가치와 목표를 명확히 기술

### 문제 정의
- 현재 상황에서 해결해야 할 문제점
- 사용자/시스템에 미치는 영향

### 기대 효과
- 구체적이고 측정 가능한 성과 지표
- 사용자 경험 개선 사항
- 시스템 성능/보안 향상

## 📋 수용 기준 (Acceptance Criteria)
- [ ] 기준 1: 구체적이고 테스트 가능한 조건
- [ ] 기준 2: 성능/품질 요구사항
- [ ] 기준 3: 보안/컴플라이언스 요구사항

## 🔗 관련 스토리
- [ ] Story 1: [스토리 제목] - 예상 SP: X
- [ ] Story 2: [스토리 제목] - 예상 SP: X
- [ ] Story 3: [스토리 제목] - 예상 SP: X

**총 예상 Story Points**: XX SP

## 🏗️ 기술적 고려사항
### 아키텍처 영향도
- 기존 시스템에 미치는 영향
- 새로운 의존성 또는 기술 스택

### 위험 요소
- 기술적 리스크와 완화 방안
- 일정 지연 가능성과 대응책

## 📈 성공 메트릭
- 정량적 지표 (성능, 사용률 등)
- 정성적 지표 (사용자 만족도 등)

## 🔄 의존성
### 선행 조건
- 이 에픽 시작 전 완료되어야 할 작업

### 후속 작업
- 이 에픽 완료 후 가능해지는 작업

## 📝 참고 자료
- 관련 문서 링크
- 설계 문서
- 외부 참조 자료
```

## 📝 스토리 템플릿

### User Story Template

```markdown
# Story: [스토리 제목]

## 📊 기본 정보
- **Story ID**: STORY-{YYYY}-{MM}-{순번} (예: STORY-2025-01-001)
- **Epic**: EPIC-{YYYY}-{MM}-{순번}
- **Story Points**: X SP (1, 2, 3, 5, 8, 13, 21)
- **우선순위**: Critical/High/Medium/Low
- **담당자**: @username
- **예상 시간**: X일
- **상태**: Backlog/Ready/In Progress/Review/Done

## 👤 사용자 스토리
**As a** [사용자 역할]  
**I want** [원하는 기능]  
**So that** [기대하는 가치/이유]

### 예시
**As a** 백업 관리자  
**I want** 다중 데이터베이스의 백업 상태를 한 화면에서 모니터링하고 싶다  
**So that** 시스템 전체의 백업 상태를 효율적으로 파악하고 문제 상황에 빠르게 대응할 수 있다

## ✅ 수용 기준 (Acceptance Criteria)
### Given-When-Then 형식
```gherkin
Given [전제 조건]
When [사용자 행동]
Then [예상 결과]

And [추가 조건]
```

### 상세 기준
- [ ] 기능적 요구사항 1
- [ ] 기능적 요구사항 2
- [ ] 비기능적 요구사항 (성능, 보안 등)
- [ ] UI/UX 요구사항
- [ ] 테스트 요구사항

## 🔧 기술적 구현 사항
### 영향 받는 컴포넌트
- [ ] Frontend: `web/templates/`, `web/static/`
- [ ] Backend: `app/api/`, `app/core/`
- [ ] Database: 스키마 변경사항
- [ ] Configuration: 설정 파일 변경

### 구현 접근법
1. **단계 1**: 상세 구현 계획
2. **단계 2**: 테스트 계획
3. **단계 3**: 배포 계획

## 🧪 테스트 계획
### 단위 테스트
- [ ] 테스트 케이스 1
- [ ] 테스트 케이스 2

### 통합 테스트
- [ ] API 엔드포인트 테스트
- [ ] 데이터베이스 연동 테스트

### E2E 테스트
- [ ] 사용자 시나리오 테스트

## 📋 완료 정의 (Definition of Done)
- [ ] 코드 구현 완료
- [ ] 단위 테스트 작성 및 통과 (커버리지 90% 이상)
- [ ] 통합 테스트 통과
- [ ] 코드 리뷰 완료
- [ ] 문서 업데이트 (API 문서, 사용자 가이드)
- [ ] 보안 검토 완료
- [ ] 성능 테스트 통과
- [ ] 배포 가능 상태

## 🔗 관련 링크
- Epic: [Epic 링크]
- 관련 Issue: [GitHub Issue 링크]
- 설계 문서: [문서 링크]
- API 문서: [Swagger 링크]

## 📝 노트
- 구현 중 발견된 이슈나 변경사항
- 추가 고려사항
```

## 🏷️ 라벨링 시스템

### Epic 라벨
- `type/epic` - 에픽 식별
- `phase/X` - Phase 번호 (예: phase/1, phase/2)
- `priority/critical|high|medium|low` - 우선순위
- `component/frontend|backend|database|infrastructure` - 영향 컴포넌트

### Story 라벨
- `type/story` - 스토리 식별
- `type/feature|bug|improvement|task` - 작업 유형
- `component/frontend|backend|database|infrastructure` - 영향 컴포넌트
- `priority/critical|high|medium|low` - 우선순위
- `size/XS|S|M|L|XL` - 작업 크기 (Story Points와 연동)

### 상태 라벨
- `status/backlog` - 백로그 상태
- `status/ready` - 작업 준비 완료
- `status/in-progress` - 진행 중
- `status/review` - 리뷰 중
- `status/blocked` - 블로킹 상태
- `status/done` - 완료

## 📊 Story Points 가이드

### 포인트 기준
- **1 SP**: 매우 간단 (1-2시간, 설정 변경, 문서 수정)
- **2 SP**: 간단 (반나절, 단순 기능 추가)
- **3 SP**: 보통 (1일, 일반적인 기능 구현)
- **5 SP**: 복잡 (2-3일, 복잡한 로직 또는 여러 컴포넌트)
- **8 SP**: 매우 복잡 (1주, 새로운 모듈 또는 대규모 변경)
- **13 SP**: 극도로 복잡 (2주, 아키텍처 변경 수준)
- **21 SP**: Epic으로 분할 필요

### 추정 기준
- 구현 복잡도
- 테스트 복잡도
- 의존성 수
- 불확실성 정도

## 🔄 워크플로우

### Epic 생성 프로세스
1. **계획 단계**: Epic 템플릿 작성
2. **분해 단계**: Story로 분할
3. **추정 단계**: Story Points 할당
4. **우선순위 결정**: 백로그 순서 결정
5. **승인**: 팀 리뷰 및 승인

### Story 진행 프로세스
1. **Backlog** → **Ready**: 상세 요구사항 정의 완료
2. **Ready** → **In Progress**: 개발 시작
3. **In Progress** → **Review**: 구현 완료, 리뷰 요청
4. **Review** → **Done**: 리뷰 완료, 배포 가능

## 📈 메트릭 및 추적

### Epic 레벨 메트릭
- Epic 완료율
- 예상 vs 실제 소요 시간
- Story Points 정확도

### Story 레벨 메트릭
- 사이클 타임 (Ready → Done)
- 리드 타임 (Backlog → Done)
- 결함률 (버그 발생 비율)

## 📚 참고 자료

### 내부 문서
- [Issues-Guidelines.md](./Issues-Guidelines.md) - 이슈 관리 가이드라인
- [Development-Guidelines.md](./Development-Guidelines.md) - 개발 가이드라인
- [Design-Rationale.md](./Design-Rationale.md) - 설계 근거

### 외부 참고
- [Atlassian Epic Guide](https://www.atlassian.com/agile/project-management/epics)
- [User Story Best Practices](https://www.atlassian.com/agile/project-management/user-stories)
- [Story Points Estimation](https://www.atlassian.com/agile/project-management/estimation)
