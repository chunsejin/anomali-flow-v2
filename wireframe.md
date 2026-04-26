# AnomaliFlow Wireframe (v1)

## 1. 목적
- 멀티테넌트 이상탐지 SaaS의 화면 구조를 정의한다.
- 역할별(`tenant_admin`, `ml_operator`, `viewer`) 접근 범위를 명확히 한다.
- 현재 백엔드 API(`/tasks`, `/tasks/{id}`, `/tasks/{id}/causal-report`, `/tasks/{id}/action-recommendation`)와 연결 가능한 UI 뼈대를 제공한다.

## 2. 정보 구조 (IA)
- `Auth`
  - 로그인/토큰 세션
- `Dashboard`
  - 작업 현황, 성공률, 지연, 최근 실패
- `Detection Run`
  - 데이터 업로드, 모델/파라미터 설정, 실행
- `Task Result`
  - 상태/결과/시각화
- `Causal Report`
  - 인과 초안 결과 조회
- `Action Recommendation`
  - 조치 초안 결과 조회
- `Operations`
  - 감사로그, 쿼터/설정

## 3. 전역 레이아웃 (Desktop)
```text
+----------------------------------------------------------------------------------+
| Topbar: [Tenant] [Environment] [Search]                        [User][Role]    |
+----------------------+-----------------------------------------------------------+
| Left Nav             | Page Content                                              |
| - Dashboard          | +-------------------- Header ---------------------------+ |
| - Detection Run      | | Title | Breadcrumb | Status Chips | Global Actions   | |
| - Task Result        | +-------------------------------------------------------+ |
| - Causal Report      | |                                                       | |
| - Recommendation     | | Main Grid (cards / tables / chart / forms)           | |
| - Operations         | |                                                       | |
|                      | +-------------------------------------------------------+ |
+----------------------+-----------------------------------------------------------+
```

## 4. 모바일 레이아웃
```text
+--------------------------------------+
| Topbar: [☰] Title        [User]      |
+--------------------------------------+
| Sticky Status Chips                   |
+--------------------------------------+
| Section 1 (form/card)                |
| Section 2 (chart/table summary)      |
| Section 3 (action buttons)           |
+--------------------------------------+
| Bottom Nav: Dash | Run | Result      |
+--------------------------------------+
```

## 5. 화면별 와이어프레임

## 5.1 Auth Session
```text
+--------------------------------------------------------------+
| Logo                                                         |
| [OIDC Login Button]  or  [Bearer Token Input][Apply]        |
|--------------------------------------------------------------|
| Session Info: tenant_id | actor_id | roles | plan_tier      |
| Error Area: auth fail reason                                |
+--------------------------------------------------------------+
```
- 권한:
  - 전체 역할 접근 가능

## 5.2 Dashboard
```text
+----------------------------------------------------------------------------------+
| KPI: [Active Tasks] [Success Rate] [p95 Latency] [Failures(24h)]               |
|----------------------------------------------------------------------------------|
| Left: Task Status Trend (PENDING/STARTED/RETRY/SUCCESS/FAILURE)                 |
| Right: Tenant Quota Usage                                                        |
|----------------------------------------------------------------------------------|
| Recent Tasks Table: task_id | algorithm | status | submitted_by | updated_at    |
+----------------------------------------------------------------------------------+
```
- 권한:
  - `viewer` 이상 조회 가능

## 5.3 Detection Run
```text
+----------------------------------------------------------------------------------+
| Step 1. Data Upload   [CSV Dropzone] [Sample Download]                          |
| Step 2. Data Type     [time_series | categorical | numerical]                   |
| Step 3. Model         [Select Model]                                            |
| Step 4. Parameters    [Dynamic Form]                                            |
| Step 5. Execute       [Run Workflow]                                             |
|----------------------------------------------------------------------------------|
| Validation/Error Panel                                                           |
+----------------------------------------------------------------------------------+
```
- 권한:
  - 실행 버튼은 `tenant_admin`, `ml_operator`만 활성
  - `viewer`는 폼 조회만 가능(실행 disabled)

## 5.4 Task Result
```text
+----------------------------------------------------------------------------------+
| Query: [task_id input] [Load]                                                   |
| Status Bar: PENDING/STARTED/RETRY/SUCCESS/FAILURE                                |
| Meta: tenant_id | trace_id | submitted_by | policy_version                      |
|----------------------------------------------------------------------------------|
| Visualization Area                                                               |
| - Outlier Graph                                                                  |
| - Root Cause Heatmap                                                             |
|----------------------------------------------------------------------------------|
| Raw Result JSON (collapsible)                                                    |
+----------------------------------------------------------------------------------+
```
- API 매핑:
  - `GET /tasks/{task_id}`

## 5.5 Causal Report
```text
+----------------------------------------------------------------------------------+
| Query: [task_id input] [Load Causal Report]                                     |
|----------------------------------------------------------------------------------|
| DAG Summary: dag_version | treatment | outcome | confounders                    |
| Effect: effect_size | CI(low/high) | refutation_result                          |
|----------------------------------------------------------------------------------|
| Notes / Export                                                                   |
+----------------------------------------------------------------------------------+
```
- API 매핑:
  - `GET /tasks/{task_id}/causal-report`

## 5.6 Action Recommendation
```text
+----------------------------------------------------------------------------------+
| Query: [task_id input] [Load Recommendation]                                    |
|----------------------------------------------------------------------------------|
| Scenario Card: scenario                                                          |
| Impact Card: expected_uplift                                                     |
| Risk/Priority: risk_level | priority                                             |
|----------------------------------------------------------------------------------|
| Recommended Next Actions (checklist)                                             |
+----------------------------------------------------------------------------------+
```
- API 매핑:
  - `GET /tasks/{task_id}/action-recommendation`

## 5.7 Operations
```text
+----------------------------------------------------------------------------------+
| Tabs: [Audit Log] [Quota] [Policy]                                              |
|----------------------------------------------------------------------------------|
| Audit Table: timestamp | actor | action | resource | result | request_id        |
| Quota View: plan_tier | active_count | max_concurrency                           |
| Policy View: policy_version | auth_enabled | tenant_enforcement                  |
+----------------------------------------------------------------------------------+
```

## 6. 상태별 UI 규칙
- `Loading`: 스켈레톤 + 실행 버튼 disabled + 취소/재시도 버튼 숨김
- `Empty`: 안내 문구 + 예시 task_id 제공
- `Error`: 표준 에러 블록(`code`, `message`, `details`) 표시
- `Success`: 결과 카드와 액션 버튼(복사/내보내기) 활성

## 7. 역할 기반 가드
- `tenant_admin`
  - 실행/조회/운영 설정 전부 가능
- `ml_operator`
  - 실행/조회 가능, 운영 일부 제한
- `viewer`
  - 조회 전용, 실행 버튼/설정 편집 비활성

## 8. 주요 사용자 플로우
1. 로그인 또는 토큰 적용
2. `Detection Run`에서 데이터/모델/파라미터 설정
3. 실행 후 `task_id` 획득
4. `Task Result`에서 상태 완료 확인
5. `Causal Report`/`Action Recommendation`에서 후속 분석 조회

## 9. 구현 우선순위
1. 공통 레이아웃 + Auth 세션
2. Detection Run + Task Result
3. Causal/Recommendation 조회 화면
4. Dashboard/Operations 고도화
