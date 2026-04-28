# SHAP/LIME 분석 기능 통합 가이드

## 개요
이상치 탐지 결과에 대한 특성 중요도 분석(SHAP/LIME)을 통합하여, 사용자가 "왜 이것이 이상인가?"를 확인할 수 있도록 지원합니다.

## 구현 내역

### 1. 백엔드 (Python)

#### requirements.txt 업데이트
- `shap`: SHAP(SHapley Additive exPlanations) 라이브러리
- `lime`: LIME(Local Interpretable Model-agnostic Explanations) 라이브러리  
- `matplotlib`: 시각화 라이브러리 (SHAP 내부에서 사용)

#### explainers.py (신규 파일)
SHAP/LIME 기반 분석 함수들을 모듈화한 파일

**주요 함수:**
- `calculate_shap_values()`: SHAP 값 계산
  - TreeExplainer (Isolation Forest용)
  - KernelExplainer (다른 모델용)
  - 특성 중요도(feature importance) 계산
  - 이상치별 top-k 기여 특성 추출
  
- `calculate_lime_explanation()`: LIME 기반 인스턴스 레벨 설명
  - 개별 이상치에 대한 로컬 설명 생성
  
- `generate_explanation_report()`: 통합 분석 리포트 생성
  - 지정된 방법(SHAP, LIME)으로 종합 분석

#### worker.py 수정
- `explainers` 모듈 임포트 추가
- 각 workflow(`run_timeseries_workflow`, `run_categorical_workflow`, `run_numerical_workflow`)에서 SHAP 분석 호출
- 분석 결과를 task 결과에 포함

#### main.py 수정
**신규 API 엔드포인트:**

1. **GET /tasks/{task_id}/explanations**
   - 해당 task의 SHAP 분석 결과 조회
   - 특성 중요도 및 이상치별 설명 반환
   - 권한: tenant_admin, ml_operator, viewer

2. **POST /tasks/{task_id}/request-explanation**
   - 기존 task에 대해 새로운 분석 요청
   - 백그라운드에서 SHAP 계산
   - 권한: tenant_admin, ml_operator

### 2. 프론트엔드 (TypeScript/React)

#### src/api.ts 수정
**신규 인터페이스:**
- `ShapExplanation`: SHAP 분석 결과 타입 정의

**신규 함수:**
- `getTaskExplanations()`: task의 SHAP 결과 조회
- `requestTaskExplanation()`: 새로운 분석 요청

#### src/ExplanationViewer.tsx (신규 컴포넌트)
SHAP 분석 결과 시각화 컴포넌트

**기능:**
- 특성 중요도 순위 테이블 (상위 15개)
  - 특성명
  - 중요도 점수
  - 상대 임팩트(%)
  
- 이상치별 주요 기여 특성 테이블 (상위 10개)
  - 인스턴스 ID
  - Top 3 기여 특성 및 SHAP 값
  
- 요약 통계
  - 사용 알고리즘
  - 분석 방법(SHAP/LIME)
  - 분석된 샘플 수
  - 설명된 이상치 수
  
- 해석 가이드 섹션
  - SHAP 값 의미 설명
  - 특성 중요도 해석 방법

### 3. 데이터 흐름

```
사용자 업로드 및 이상치 탐지
  ↓
worker.py에서 SHAP 분석 병렬 실행
  ↓
분석 결과를 task_result에 저장
  ↓
Frontend GET /tasks/{task_id}/explanations 요청
  ↓
ExplanationViewer에서 시각화
```

## 사용 방법

### 1. 백엔드 설정
```bash
# requirements 설치
pip install -r requirements.txt

# worker 시작
celery -A worker worker -l info

# main API 시작
python -m uvicorn main:app --reload
```

### 2. 프론트엔드 사용
1. 데이터 업로드 및 이상치 탐지 실행
2. task_id 획득 후, 결과 조회
3. "분석" 탭에서 SHAP 결과 시각화 확인

### 3. API 사용 (직접 호출)
```bash
# SHAP 결과 조회
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/tasks/{task_id}/explanations

# 새로운 분석 요청
curl -X POST -H "Authorization: Bearer <token>" \
  http://localhost:8000/tasks/{task_id}/request-explanation
```

## 성능 고려사항

### SHAP 계산 비용
- **TreeExplainer**: O(depth × sample × feature) - 빠름
- **KernelExplainer**: O(2^feature × sample) - 느림

### 최적화 전략
- `sample_size`: 분석할 최대 샘플 수 (기본 100)
- `background_sample_size`: SHAP 배경 데이터 (기본 50)
- 대용량 데이터의 경우 샘플링 권장

### 타임아웃 설정
- API 응답 시간: 30초 (설정 가능)
- 대규모 분석은 비동기 처리 권장

## 확장 가능성

### 향후 개선안
1. **LIME 시각화**: `lime.js` 또는 custom plot 추가
2. **Shapley Force Plot**: SHAP force plot 추가
3. **의존성 분석**: SHAP dependence plot 추가
4. **상호작용 분석**: SHAP interaction values 추가
5. **캐싱**: 분석 결과 캐싱으로 성능 향상
6. **비동기 계산**: 대규모 분석을 위한 작업 큐 추가

## 테스트

### 단위 테스트 (explainers.py)
```python
import pandas as pd
from sklearn.ensemble import IsolationForest
from explainers import calculate_shap_values

X = pd.DataFrame(...)
model = IsolationForest()
model.fit(X)
outliers = model.predict(X) == -1

result = calculate_shap_values(model, X, "IsolationForest", 
                              np.where(outliers)[0].tolist())
assert "feature_importance" in result
```

### 통합 테스트
```bash
# Frontend에서 ExplanationViewer 테스트
npm test -- ExplanationViewer.tsx
```

## 문제 해결

### SHAP 계산 실패
- 원인: 메모리 부족, 특성 수 과다
- 해결: sample_size 감소, background_sample_size 감소

### API 응답 404
- 원인: 분석 결과가 아직 생성되지 않음
- 해결: POST /tasks/{task_id}/request-explanation으로 요청

### 성능 저하
- 원인: KernelExplainer 사용 (tree가 아닌 모델)
- 해결: TreeExplainer 호환 모델 사용 권장

## 참고 자료
- [SHAP 공식 문서](https://shap.readthedocs.io/)
- [LIME 논문](https://arxiv.org/abs/1602.04938)
- [Interpretable ML 책](https://christophm.github.io/interpretable-ml-book/)
