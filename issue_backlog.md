# 구현 우선순위 이슈 백로그 (main.py / worker.py / app.py)

기준 문서: plan.md (통합 전환 계획 v2)

## P0 (보안/테넌트 격리 필수)

### 1. [P0][main.py] OIDC/JWT 인증 + RequestContext 주입 + RBAC 적용
- 대상 파일: main.py
- 문제
  - 현재 /tasks, /tasks/{task_id}가 무인증으로 노출되어 있음.
  - tenant_id/actor_id/roles/request_id 컨텍스트가 없음.
- 작업
  - JWT 검증 디펜던시 추가 및 OIDC issuer/audience 검증.
  - RequestContext 모델(tenant_id, actor_id, roles, request_id, plan_tier) 도입.
  - 엔드포인트별 RBAC 정책 체크(tenant_admin, ml_operator, viewer, platform_admin).
- 완료 기준
  - 인증 없는 요청은 401, 권한 부족은 403.
  - 모든 요청 처리 경로에서 RequestContext 접근 가능.

### 2. [P0][worker.py] Celery 계약 변경: tenant_context 필수 + 실행 전 검증
- 대상 파일: worker.py, main.py
- 문제
  - 현재 task payload에 tenant 컨텍스트가 없음.
  - worker에서 작업 데이터의 tenant 격리를 보장하지 못함.
- 작업
  - run_*_workflow 시그니처를 (df, algorithm, params, tenant_context)로 변경.
  - tenant_context 유효성 검증(필수 필드 누락/역할 불일치 차단).
  - task 실행 로그에 tenant_id, request_id 포함.
- 완료 기준
  - tenant_context 없이 enqueue/실행 불가.
  - task 결과에 tenant 식별 정보 연결 가능.

### 3. [P0][main.py+worker.py] Mongo Repository 계층 도입 + tenant 강제 필터 + 감사로그 저장
- 대상 파일: main.py, worker.py (신규 repository 모듈 포함)
- 문제
  - 직접 Mongo 접근으로 tenant 필터 누락 위험.
  - 감사로그(AuditEvent) 수집 부재.
- 작업
  - TaskResultRepository/AuditRepository 도입, raw collection 접근 금지.
  - TaskResult, AuditEvent 스키마에 tenant_id 및 감사 필드 반영.
  - write/read helper에서 tenant_id 인자 필수화.
- 완료 기준
  - 리포지토리 외부에서 DB 직접 접근 제거.
  - AuditEvent가 주요 액션(enqueue/result-read/failure)에 대해 생성됨.

## P1 (운영 안정화/호환성)

### 4. [P1][main.py] 표준 API 응답 스키마 및 trace_id 연동
- 대상 파일: main.py
- 작업
  - 공통 응답 모델: tenant_id, submitted_by, trace_id, policy_version.
  - 에러 응답 표준화(code, message, details).
  - request_id/trace_id를 로깅과 응답에 동시 반영.
- 완료 기준
  - 성공/실패 응답 포맷 일관성 확보.

### 5. [P1][worker.py] Idempotency Key + 재시도 정책 + tenant quota 제어
- 대상 파일: worker.py, celeryconfig.py
- 작업
  - 중복 요청 방지를 위한 idempotency key 지원.
  - 재시도 횟수/백오프/실패 분류 표준화.
  - shared queue 환경에서 tenant별 동시성/쿼터 제한 추가.
- 완료 기준
  - 동일 요청 중복 실행 방지.
  - noisy neighbor 영향 완화 지표 수집 가능.

### 6. [P1][app.py] Streamlit 인증 세션 연동 + 역할 기반 UI 가드
- 대상 파일: app.py
- 작업
  - OIDC 로그인 토큰 저장/갱신 및 백엔드 Authorization 헤더 적용.
  - 역할별 기능 노출 제어(조회 전용 vs 실행 권한).
  - 권한 에러(401/403) UX 처리 추가.
- 완료 기준
  - 인증 없는 사용자는 실행/조회 불가.
  - 사용자 역할에 따라 UI 액션 제한.

## P2 (분석/UX 고도화 및 React 전환 준비)

### 7. [P2][worker.py] CausalReport/ActionRecommendation 저장 파이프라인 초안
- 대상 파일: worker.py (신규 모델/저장 모듈 포함)
- 작업
  - CausalReport, ActionRecommendation 문서 스키마 초안 구현.
  - 이상치 결과와 인과/조치 리포트의 연결키 정의(task_id, analysis_id).
- 완료 기준
  - 추후 인과분석/조치추천 API에서 재사용 가능한 저장 구조 확보.

### 8. [P2][app.py] 결과 시각화 모듈 분리 및 API 중심 구조로 리팩터링
- 대상 파일: app.py
- 작업
  - 데이터 전처리, API 호출, 시각화 로직 분리.
  - React 대시보드 전환을 고려한 API 계약 중심 리팩터링.
- 완료 기준
  - app.py 단일 파일 의존도 축소, 기능 모듈화.

### 9. [P2][main.py+worker.py+app.py] 관측성 기본선: 구조화 로그 + tenant/request 상관관계
- 대상 파일: main.py, worker.py, app.py
- 작업
  - JSON 로그 포맷 통일.
  - tenant_id, request_id, task_id를 공통 상관키로 남김.
  - 실패 유형 분류 및 운영 대시보드 입력 포맷 정리.
- 완료 기준
  - API-Worker-UI 흐름 추적 가능한 로그 체인 확보.
