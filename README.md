# anomali-flow-v2

FastAPI + Celery 기반 이상탐지(Anomaly Detection) 플랫폼입니다.  
멀티테넌시 컨텍스트(tenant/role/request_id)를 포함한 작업 실행, 대시보드 조회, 감사 로그(Audit), 인과 리포트/액션 추천 조회를 지원합니다.

## 1. 기술 스택

- Backend API: FastAPI
- Async Worker: Celery
- Broker: Redis
- Result/Meta Storage: MongoDB
- Frontend: React + TypeScript + Vite + Ant Design
- Legacy/Exploration UI: Streamlit
- Orchestration (optional): Prefect Orion

## 2. 프로젝트 구조

- `main.py`: FastAPI API 엔드포인트
- `worker.py`: Celery 태스크 및 이상탐지 워크플로우
- `auth.py`: 인증/권한 및 RequestContext 처리
- `repositories.py`: MongoDB 저장소 접근 레이어
- `app.py`: Streamlit UI
- `streamlit_api.py`: Streamlit에서 API 호출 래퍼
- `frontend/`: React 웹 UI
- `docker-compose.yml`: 통합 실행 구성

## 3. 빠른 시작 (Docker Compose)

사전 준비:
- Docker Desktop
- Docker Compose v2 (`docker compose`)

실행:

```bash
docker compose up --build
```

실행 후 접근:
- Frontend: http://localhost:5173
- FastAPI: http://localhost:8000
- Streamlit: http://localhost:8501
- Prefect Orion: http://localhost:4200
- Redis: localhost:6379
- MongoDB: localhost:27017

중지:

```bash
docker compose down
```

데이터까지 삭제:

```bash
docker compose down -v
```

## 4. 로컬 개발 실행

권장: Redis/Mongo는 Docker로 실행하고 앱은 로컬에서 실행

### 4.1 Redis/Mongo만 먼저 실행

```bash
docker compose up -d redis mongo
```

### 4.2 Python 백엔드/워커

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

FastAPI:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Celery Worker (새 터미널):

```bash
celery -A worker worker --loglevel=info
```

Streamlit UI (선택, 새 터미널):

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### 4.3 Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 5. 인증/권한 동작

기본적으로 API는 인증을 사용합니다 (`AUTH_ENABLED=true`).  
개발 편의를 위해 인증 비활성화 모드도 지원합니다.

### 5.1 인증 비활성화 (개발 모드)

예시 환경변수:

```bash
AUTH_ENABLED=false
DEV_TENANT_ID=default
DEV_ACTOR_ID=dev-user
DEV_ROLES=tenant_admin,ml_operator,viewer
DEV_PLAN_TIER=standard
```

### 5.2 인증 활성화

토큰 기반 인증 사용 시 `Authorization: Bearer <token>` 헤더 필요.

- HS 검증 모드: `JWT_SECRET` 설정
- OIDC 검증 모드: `OIDC_ISSUER_URL`, `OIDC_AUDIENCE` 설정

토큰에 포함되어야 하는 대표 claim:
- `tenant_id` (또는 `org_id`/`organization_id`)
- `sub`
- `roles` 또는 `role` 또는 `groups`

## 6. 주요 환경변수

- `AUTH_ENABLED` (default: `true`)
- `CORS_ALLOW_ORIGINS` (default: `http://localhost:5173,http://127.0.0.1:5173`)
- `CELERY_BROKER_URL` (default: `redis://redis:6379/0`)
- `CELERY_RESULT_BACKEND` (default: `mongodb://mongo:27017/celery_results`)
- `TENANT_QUOTA_STANDARD` (default: `2`)
- `TENANT_QUOTA_PRO` (default: `5`)
- `TENANT_QUOTA_ENTERPRISE` (default: `10`)
- `ANOMALIFLOW_API_BASE_URL` (Streamlit API base URL, default: `http://localhost:8000`)
- `VITE_API_BASE_URL` (Frontend API base URL, default: `http://localhost:8000`)

## 7. API 개요

공통:
- 응답은 Envelope 형태(`tenant_id`, `trace_id`, `data`, `error`)
- `X-Request-Id` 헤더 권장 (미지정 시 서버 생성)

엔드포인트:
- `POST /tasks`
- `GET /tasks/{task_id}`
- `GET /dashboard/summary`
- `GET /operations/audit-events`
- `GET /operations/quota`
- `GET /tasks/{task_id}/causal-report`
- `GET /tasks/{task_id}/action-recommendation`

### 7.1 작업 생성 예시

```bash
curl -X POST "http://localhost:8000/tasks" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: req-123" \
  -d '{
    "df": [{"value": 1.0}, {"value": 1.2}, {"value": 10.0}],
    "algorithm": "IsolationForest",
    "params": {
      "data_type": "numerical",
      "contamination": 0.1
    }
  }'
```

`data_type`별 지원 알고리즘:
- `time_series`: `IsolationForest`, `GMM`
- `categorical`: `LOF`, `DBSCAN`
- `numerical`: `IsolationForest`, `GMM`, `DBSCAN`, `LOF`, `KMeans`

## 8. 프런트엔드 E2E 테스트

```bash
cd frontend
npm install
npx playwright install
npm run test:e2e
```

UI 모드:

```bash
npm run test:e2e:ui
```

## 9. 샘플 데이터

- `data/categorical_bike_buyers_clean.csv`
- `data/timeseries_DailyDelhiClimateTest.csv`

## 10. 트러블슈팅

- CORS 오류 발생 시: `CORS_ALLOW_ORIGINS`에 프런트 주소 포함 여부 확인
- Worker가 작업을 처리하지 않으면: Redis/Mongo 상태, `celery -A worker worker` 실행 여부 확인
- 401/403 오류 시: `AUTH_ENABLED` 설정과 토큰 claim(`tenant_id`, `sub`, `roles`) 확인
- quota 초과 오류 시: `TENANT_QUOTA_*` 환경변수 또는 활성 작업 수 확인

## 11. 라이선스

이 저장소는 루트의 `LICENSE` 파일을 따릅니다.
