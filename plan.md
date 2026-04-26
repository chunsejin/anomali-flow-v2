# AnomaliFlow 통합 전환 계획 v2

## 1. 목표 및 완료 기준

### 목표
- 기존 단일 테넌트 이상탐지 서비스를 멀티 테넌트 SaaS로 전환한다.
- 이상치 탐지, 원인 후보 도출, 인과 검증, 조치 추천, 모델 운영관리를 하나의 폐루프로 통합한다.
- 엔터프라이즈 요구사항(SSO, RBAC, 감사로그, 보안통제, 운영가시성)을 충족한다.
- 기존 비동기 워크플로우(FastAPI + Celery + Mongo + Redis)는 중단 없이 점진 마이그레이션한다.
- UI를 Streamlit 중심에서 React + TypeScript + Ant Design 기반 엔터프라이즈 대시보드로 전환하고 Vercel에 배포한다.

### 완료 기준 (Definition of Done)
- 모든 API, 백그라운드 작업, 저장 데이터에 tenant_id 스코프가 강제된다.
- OIDC SSO + RBAC가 API와 UI 전체에 적용되고 권한 우회가 불가능하다.
- 분석 흐름이 아래 5단계로 운영된다.
  - 이상치 탐지
  - 설명 및 원인 후보 분석
  - 인과 분석
  - 조치 추천 및 시뮬레이션
  - 모델 운영관리(MLOps)
- 감사로그는 tenant 단위로 조회 가능하며 누가/언제/무엇을 수행했는지 추적 가능하다.
- 운영 대시보드에서 tenant별 SLO, 지연시간, 오류율, 작업 성공률을 확인할 수 있다.
- React 대시보드가 Vercel에서 운영되며 API 연동, 인증, 권한, 핵심 분석 화면이 동작한다.

## 2. 현재 상태 요약 (코드베이스 기준)
- main.py: 무인증 FastAPI + Celery task 생성/조회 엔드포인트.
- worker.py: Celery task 실행, MongoDB(celery_results.results)에 일부 결과 저장.
- app.py: Streamlit 기반 업로드/실행/조회 UI, 사용자/조직/권한 개념 부재.
- docker-compose.yml: 단일 Redis, 단일 Mongo, 단일 worker/fastapi/streamlit.
- 결론: 현재는 단일 테넌트 PoC 구조이며 엔터프라이즈 운영에 필요한 인증, 인가, 테넌트 격리, 감사, 관측성이 부족하다.

## 3. 목표 아키텍처 (통합안)

### 3.1 분석 및 운영 폐루프
- 단계 1: 이상치 탐지 (Rule, ML, DL, Ensemble).
- 단계 2: 설명/원인 후보 분석 (SHAP, 변화점, 중요도 분석).
- 단계 3: 인과 분석 (DAG, treatment/outcome/confounder, 효과 추정, 반박 검정).
- 단계 4: 조치 추천 (What-if, counterfactual, 우선순위 도출).
- 단계 5: 운영관리 (모델 등록, 모니터링, 재학습, 승인 워크플로우).

### 3.2 멀티 테넌시 모델
- 1단계: Shared DB + Shared Schema + tenant_id 강제.
- 2단계: 엔터프라이즈 상위 요금제 고객 대상 tenant 전용 DB 옵션.
- 핵심 인덱스 전략: (tenant_id, resource_id) 복합 인덱스 기본 적용.

### 3.3 인증/인가
- OIDC SSO (Okta/Azure AD/Google Workspace).
- FastAPI 미들웨어/디펜던시에서 JWT 검증.
- 기본 역할:
  - tenant_admin
  - ml_operator
  - viewer
  - platform_admin
- 권한 체크 위치:
  - API 요청 시점
  - Celery enqueue 시점
  - 결과 조회 및 다운로드 시점

### 3.4 데이터/작업 격리
- RequestContext 표준화: tenant_id, actor_id, roles, request_id, plan_tier.
- Celery payload에 tenant_context 필수 전달.
- Repository 계층에서 tenant filter 누락 방지(직접 raw query 금지).

### 3.5 엔터프라이즈 보안 기준
- 비밀관리: Secret Manager/Vault 우선.
- 암호화: at-rest, in-transit(TLS).
- 감사로그: append-only + 보존정책.
- API rate limit 및 tenant quota 적용.

## 4. 프론트엔드 전환 전략 (React + TypeScript + Ant Design + Vercel)

### 4.1 전환 원칙
- 기존 Streamlit UI는 즉시 제거하지 않고 병행 운영 후 단계적으로 종료.
- API 중심 아키텍처로 UI는 BFF 없이도 동작 가능하게 설계하되, 필요 시 API Gateway/BFF를 추가.
- 디자인 시스템은 Ant Design 토큰 기반으로 커스터마이징하고 tenant/role 기반 메뉴 제어를 적용.

### 4.2 기술 스택
- 프레임워크: React + TypeScript (권장: Next.js App Router).
- UI 컴포넌트: Ant Design.
- 차트: Ant Design Charts 또는 ECharts.
- 상태관리: React Query + Zustand(또는 Context 조합).
- 인증: OIDC 로그인, 토큰 기반 API 호출.
- 배포: Vercel(Production/Preview 분리).

### 4.3 UI 정보구조 (IA)
- 로그인/세션
  - SSO 로그인
  - 테넌트/역할 확인
- 대시보드 홈
  - tenant별 작업 현황, 성공률, p95 지연시간, 알림 요약
- 이상치 탐지 화면
  - 데이터 업로드, 알고리즘 선택, 파라미터 설정, 작업 실행
- 결과 분석 화면
  - 이상치 구간 시각화, 주요 feature 설명, 원인 후보 리스트
- 인과분석 화면
  - DAG 뷰어, 효과 추정 결과, 반박 검정 리포트
- 조치 추천 화면
  - What-if 시나리오, counterfactual 결과, 권장 조치 우선순위
- 운영관리 화면
  - 모델 버전/승인 이력, 드리프트 모니터링, 재학습 이벤트
- 감사로그/보안 화면
  - 사용자 활동 로그, 권한 변경 이력, 다운로드 추적
- 관리자 설정 화면
  - tenant 설정, quota, 보존정책, 알림 규칙

### 4.4 Ant Design 기반 정교화 항목
- 공통 디자인 토큰(색상, 간격, 타이포그래피) 표준화.
- 데이터 밀도가 높은 Table/ProTable 구성(필터, 정렬, 컬럼 저장).
- 대규모 시계열 차트의 성능 최적화(샘플링, lazy rendering).
- 권한 기반 컴포넌트 가드(버튼/메뉴/액션 숨김 + 서버 검증 병행).
- 에러/빈상태/로딩상태의 일관된 UX 패턴 적용.
- 접근성(키보드 탐색, aria, 명도 대비) 준수.

### 4.5 Vercel 배포 및 운영 계획
- 환경 분리:
  - Production
  - Staging(Preview)
- 환경변수 관리:
  - OIDC issuer/client
  - API base url
  - 로깅/모니터링 key
- 배포 파이프라인:
  - PR 생성 시 Preview 자동 배포
  - main 머지 시 Production 자동 배포
- 품질 게이트:
  - 타입체크
  - 단위 테스트
  - E2E 스모크 테스트
  - Lighthouse 기본 점검

## 5. 백엔드/API 계약 변경

### 5.1 FastAPI
- 인증 토큰 필수화.
- 서버에서 토큰 기반 tenant_id 추출(클라이언트 지정 금지).
- 응답 공통 필드:
  - tenant_id
  - submitted_by
  - trace_id
  - policy_version

### 5.2 Celery Task Contract
- 기존: (df, algorithm, params)
- 변경: (df, algorithm, params, tenant_context)
- tenant_context 필드:
  - tenant_id
  - actor_id
  - roles
  - request_id
  - plan_tier

### 5.3 데이터 모델
- TaskResult 필수 필드:
  - tenant_id, task_id, status, algorithm, params, created_by, created_at, updated_at, retention_class
- AuditEvent 신규 필드:
  - tenant_id, actor_id, action, resource_type, resource_id, result, ip, user_agent, timestamp
- CausalReport(신규):
  - tenant_id, analysis_id, dag_version, treatment, outcome, confounders, effect_size, confidence_interval, refutation_result
- ActionRecommendation(신규):
  - tenant_id, recommendation_id, scenario, expected_uplift, risk_level, priority, generated_at

## 6. 구현 단계 (Phase별)

### Phase 0: 기반 정리 (1주)
- 서비스/리포지토리 계층 분리(main.py, worker.py).
- RequestContext 타입/유틸 도입.
- tenant_id 필수 규칙 및 lint/check 스크립트 도입.
- 산출물: ADR, 코드 규칙, 기본 테스트 템플릿.

### Phase 1: 인증/인가 도입 (2주)
- OIDC 검증 미들웨어 적용.
- RBAC 정책(역할-행위-리소스) 파일화.
- 기존 tasks API 인증 필수화.
- 산출물: 401/403 표준 응답, 정책 테스트.

### Phase 2: 멀티 테넌시 데이터 전환 (2~3주)
- tenant_id 포함 스키마 확장.
- 인덱스 추가: {tenant_id:1, task_id:1}, {tenant_id:1, created_at:-1}.
- 레거시 백필(tenant_id=default) + dual-read 전략.
- 산출물: 마이그레이션 런북, 롤백 절차.

### Phase 3: 분석 폐루프 기능 확장 (3주)
- 이상치 결과에 설명/원인 후보 분석 연결.
- 인과분석 모듈(DAG, 효과 추정, 반박 검정) API 추가.
- 조치 추천/시뮬레이션 API 추가.
- 산출물: CausalReport/ActionRecommendation 생성 파이프라인.

### Phase 4: UI 현대화 (React/TS/AntD) (3주)
- Next.js + Ant Design 초기 구조 생성.
- 인증 연동, 역할별 메뉴 가드 적용.
- 핵심 화면(홈, 탐지, 분석, 인과, 조치, 운영, 감사) 구현.
- Streamlit과 병행 운영(feature flag) 후 점진 전환.
- 산출물: Vercel Staging 배포, UAT 체크리스트.

### Phase 5: 엔터프라이즈 운영성 (2주)
- OpenTelemetry, 구조화 로그, trace에 tenant_id 포함.
- tenant별 SLO 메트릭/알림 구성.
- 감사로그 조회 API 및 UI 완성.
- 산출물: 운영 대시보드, 온콜 가이드.

### Phase 6: 하드닝/컴플라이언스 (1~2주)
- 의존성/이미지 보안 스캔.
- 데이터 보존/삭제 정책 적용.
- DR/백업 복구 리허설.
- 산출물: 보안 점검표, 복구 훈련 결과.

### Phase 7: 와이어프레임 반영 및 화면 전달 (2주)
- `wireframe.md` 기준 IA(`Auth`, `Dashboard`, `Detection Run`, `Task Result`, `Causal Report`, `Action Recommendation`, `Operations`)를 React 라우트로 확정.
- 데스크톱/모바일 공통 레이아웃(Topbar/LeftNav/BottomNav) 구현.
- 역할 기반 가드(`tenant_admin`, `ml_operator`, `viewer`)를 화면/버튼 레벨로 일관 적용.
- 상태별 UI 규칙(loading/empty/error/success)과 표준 에러 블록(`code`, `message`, `details`) 공통 컴포넌트화.
- API 연결 화면 우선 구현:
  - `GET /tasks/{task_id}`
  - `GET /tasks/{task_id}/causal-report`
  - `GET /tasks/{task_id}/action-recommendation`
- 산출물: `wireframe.md` 추적 가능한 화면 구현 체크리스트, 클릭 가능한 프로토타입, QA 시나리오.

## 7. 테스트 및 검증 시나리오

### 자동화 테스트
- 단위 테스트:
  - RBAC 정책 평가
  - tenant context 파싱
  - repository tenant filter 강제
- 통합 테스트:
  - tenant A/B 데이터 누수 없음 검증
  - 인증 없음 401, 권한 없음 403
- E2E 테스트:
  - SSO 로그인 -> 업로드 -> 탐지 -> 인과분석 -> 조치추천 -> 결과 조회

### 보안/회귀 테스트
- IDOR 및 수평 권한상승 차단 검증.
- 잘못된 JWT/만료 JWT/issuer 불일치 거부.
- 기존 알고리즘 정확도 및 처리시간 회귀 점검.

### 성능/신뢰성 테스트
- 다중 tenant 동시 enqueue 시 p95 지연시간 측정.
- worker 재시작/Redis 지연/부분 실패 상황에서 재시도 및 중복 실행 방지 검증.
- UI 성능: 대용량 테이블/차트 렌더링 시간과 상호작용 지연 측정.

## 8. 배포 및 롤아웃 전략
- 총 12~16주 권장.
- feature flag:
  - auth_enabled
  - tenant_enforcement
  - causal_analysis_enabled
  - action_recommendation_enabled
  - react_ui_enabled
  - audit_log_enabled
- 롤아웃 순서:
  1. 내부 스테이징 tenant
  2. 파일럿 고객 1~2개
  3. 전체 tenant 확장
- Go/No-Go 기준:
  - 보안 critical/high 0건
  - 데이터 누수 0건
  - SLO 충족
  - UI 주요 사용자 시나리오 통과율 99% 이상

## 9. 리스크 및 대응
- 리스크: tenant filter 누락으로 데이터 노출.
  - 대응: repository 강제, 정적 검사, 통합 테스트 게이트.
- 리스크: 인증 도입으로 기존 UI 플로우 중단.
  - 대응: feature flag 기반 병행 운영, 점진 전환.
- 리스크: shared queue noisy neighbor.
  - 대응: tenant quota, 우선순위, 전용 queue 옵션.
- 리스크: 대시보드 복잡도 증가로 사용자 학습 비용 상승.
  - 대응: 역할별 기본 뷰, 단계별 온보딩, 도움말 패널 제공.

## 10. 기본 가정
- 보안 및 감사가능성을 최우선으로 한다.
- 초기에는 Shared DB 모델로 시작하고 상위 고객에 전용 DB를 제공한다.
- OIDC, Secret Manager, 모니터링 스택 사용 가능한 클라우드 환경을 전제로 한다.
- 기존 알고리즘 워크플로우 호환은 API versioning 및 feature flag로 보장한다.

## 11. 즉시 실행 Backlog (우선순위 상)
- P0
  - RequestContext 및 tenant enforcement 미들웨어 도입
  - OIDC + RBAC 적용
  - TaskResult/AuditEvent 스키마 확장
- P1
  - 인과분석 API 초안 + CausalReport 저장
  - React/TypeScript/Ant Design 대시보드 골격 및 인증 연동
  - Vercel Preview 배포 연결
- P2
  - 조치추천 시뮬레이션 화면
  - 운영 대시보드 고도화(SLO/알림/감사)
  - Streamlit 종료 계획 수립 및 안내
- P3
  - `wireframe.md`의 7개 핵심 화면을 React 라우트/페이지로 1차 구현
  - 공통 레이아웃/상태 컴포넌트(loading/empty/error/success) 패키징
  - 모바일 브레이크포인트 기준 반응형 검수(핵심 플로우 3개)
