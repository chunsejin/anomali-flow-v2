# 📊 JSON 시각화 차트 생성 - 최종 요약

## ✅ 완료된 작업

Raw Task JSON과 Causal Report JSON을 효과적으로 시각화하는 포괄적인 도구 세트를 구축했습니다.

---

## 🎯 생성된 결과물

### 1️⃣ **Python 시각화 스크립트**
📄 **파일**: `scripts/visualize_json_reports.py`

**기능**:
- ✅ Task Result JSON → 4개 차트 (Pie + Histogram + Bar + Metadata)
- ✅ Causal Report JSON → 4개 차트 (Effect + DAG + Category + Summary)
- ✅ 비교 분석 → 4개 차트 (Anomaly vs Effect + Relationship + CI + Summary)
- ✅ 자동 메트릭 추출 및 시각화
- ✅ PNG 형식으로 고품질 저장 (300 DPI)

**사용 방법**:
```bash
# 샘플 데이터로 테스트
cd e:\anomali-flow-v2
python scripts/visualize_json_reports.py

# 커스텀 JSON으로 시각화
python -c "
from scripts.visualize_json_reports import JsonVisualizer
import json

visualizer = JsonVisualizer()
with open('data/my_data.json') as f:
    data = json.load(f)
visualizer.visualize_task_result(data, save=True)
"
```

---

### 2️⃣ **React/TypeScript 차트 컴포넌트**
📄 **파일**: `frontend/src/components/JsonVisualizer.tsx`

**제공되는 컴포넌트**:

| 컴포넌트 | 설명 | 입력 데이터 |
|---------|------|-----------|
| `TaskResultOutlierChart` | 이상치 분포 (파이 + 통계) | Task Result JSON |
| `CausalEffectChart` | Effect Size + CI 시각화 | Causal Report JSON |
| `CausalDagChart` | 인과 관계도 (DAG 표현) | Causal Report JSON |
| `JsonMetricsTable` | 수치 메트릭 테이블 | 모든 JSON |
| `JsonHierarchyView` | 계층적 JSON 구조 표시 | 모든 JSON |
| `ComparisonDashboard` | Task vs Causal 비교 | 둘 다 필요 |

**사용 예시**:
```tsx
import { TaskResultOutlierChart, CausalEffectChart } from "./components/JsonVisualizer";

function MyDashboard() {
  return (
    <>
      <TaskResultOutlierChart data={taskData} />
      <CausalEffectChart data={causalData} />
    </>
  );
}
```

---

### 3️⃣ **통합 분석 대시보드**
📄 **파일**: `frontend/src/components/IntegratedAnalysisDashboard.tsx`

**기능**:
- ✅ Task ID 입력으로 Task Result + Causal Report 자동 로드
- ✅ 4개 탭 인터페이스:
  - **Comparison Overview**: 모든 차트를 한 화면에
  - **Task Result Metrics**: Task 메트릭 상세
  - **Causal Metrics**: Causal 메트릭 상세
  - **Correlation Analysis**: 이상 vs 인과 상관관계 해석
- ✅ 실시간 데이터 로드 및 업데이트
- ✅ 에러 처리 및 로딩 상태 표시

**통합 방법**:
```tsx
// App.tsx에 추가
import { IntegratedAnalysisDashboard } from "./components/IntegratedAnalysisDashboard";

<Menu>
  <Menu.Item key="analysis">
    <IntegratedAnalysisDashboard token={token} getEnvelopeFunc={getEnvelope} />
  </Menu.Item>
</Menu>
```

---

### 4️⃣ **생성된 차트 샘플**
📁 **위치**: `data/visualizations/`

**파일**:
- `task_result_sample-task-001.png` (326 KB)
- `causal_report_analysis-001.png` (324 KB)
- `comparison_sample-task-001.png` (427 KB)

**차트 내용**:
1. **Task Result 차트**
   - 이상치 분포 (파이): 97.5% 정상, 2.5% 이상
   - 이상치 점수 분포 (히스토그램): 정상/이상 명확한 분리
   - 상위 메트릭 (막대그래프): outlier_scores, outlier_indices, index
   - 메타데이터: task_id, status, 통계 요약

2. **Causal Report 차트**
   - Effect Size & CI (에러바): 0.35 ± 0.07
   - Causal DAG: algorithm_tuning → anomaly_rate (3개 confounder)
   - Effect Size 범주 (수평 막대): Strong 범주 (0.3-0.5)
   - 분석 요약: refutation passed, 신뢰도 높음

3. **비교 분석 차트**
   - 이상률 (2.5%) vs Effect Size (35%)
   - 인과 관계: Treatment + 3개 confounder
   - 신뢰도 구간: [0.28, 0.42]
   - 통합 해석: 낮은 상관관계, 추가 분석 권장

---

## 📊 차트 상세 설명

### Task Result 차트 해석

**Outlier Distribution (파이 차트)**
- 정상(초록): 975개, 이상(빨강): 25개
- 이상 비율: 2.5%
- **의미**: 약 100개 중 2-3개가 이상

**Score Distribution (히스토그램)**
- 정상 점수(초록): 0-0.5 범위
- 이상 점수(빨강): 0.7-1.0 범위
- **의미**: 명확한 분리 → 신뢰도 높은 탐지

**Top Metrics (막대그래프)**
- outlier_indices: 25개
- outlier_scores: 평균값
- index: 1000개
- **의미**: 주요 메트릭의 상대적 크기 비교

---

### Causal Report 차트 해석

**Effect Size & Confidence Interval (에러바)**
- 포인트: 0.3500
- 하한(CI Low): 0.2800
- 상한(CI High): 0.4200
- **의미**: 95% 신뢰도로 효과가 0.28-0.42 범위

**Effect Size Category (수평 막대)**
- Weak (0-0.1): 회색
- Moderate (0.1-0.3): 회색
- Strong (0.3-0.5): **빨강** ← 현재 효과
- Very Strong (0.5-1.0): 회색
- **의미**: Strong 수준의 인과 효과

**Causal DAG (텍스트 표현)**
```
Treatment: algorithm_tuning
        ↓
Outcome: anomaly_rate

Confounders:
  • seasonality
  • data_drift
  • model_age
```
- **의미**: 알고리즘 조정이 이상 비율에 강한 영향을 미치나, 계절성 등 3개 교란변수 존재

---

### 비교 분석 차트 해석

**Anomaly Rate vs Effect Size**
- 이상 비율: 2.5% (빨강)
- Effect Size: 35% (파랑)
- **의미**: 이상이 적게 탐지되었지만 효과는 크다 → 불일치

**Confidence Interval**
- CI 범위: [0.28, 0.42]
- CI 폭: 0.14 (중간 정도의 신뢰도)
- **의미**: 효과 추정의 불확실성 존재

**Key Insight**
> ⚠ A low correlation between anomalies and effect
- 이상 탐지 결과와 인과 효과가 일치하지 않음
- 추가 분석 필요 (다른 원인 후보 탐색)

---

## 🚀 활용 시나리오

### Scenario 1: 실시간 모니터링
```bash
# 매시간 자동으로 차트 생성
python scripts/visualize_json_reports.py  # cron job으로 실행
```

### Scenario 2: 웹 대시보드에 임베드
```tsx
// Frontend에서 실시간 표시
<IntegratedAnalysisDashboard 
  token={userToken}
  getEnvelopeFunc={apiCall}
/>
```

### Scenario 3: 보고서 자동 생성
```python
# PDF/Excel 내보내기 (확장 기능)
visualizer.export_to_pdf("analysis.pdf")
visualizer.export_to_excel("analysis.xlsx")
```

### Scenario 4: 조건부 알림
```python
if anomaly_rate > 10 and effect_size < 0.2:
    send_alert("High anomalies but weak effect - investigate!")
```

---

## 📁 파일 구조

```
anomali-flow-v2/
├── scripts/
│   ├── download_anomaly_datasets.py         # 데이터셋 준비
│   ├── analyze_datasets.py                  # 데이터셋 분석
│   └── visualize_json_reports.py            # ⭐ JSON 시각화
├── frontend/
│   └── src/
│       ├── App.tsx                          # 컴포넌트 통합
│       └── components/
│           ├── JsonVisualizer.tsx           # ⭐ React 차트
│           └── IntegratedAnalysisDashboard.tsx  # ⭐ 통합 대시보드
├── data/
│   └── visualizations/                      # 생성된 차트 저장
│       ├── task_result_*.png
│       ├── causal_report_*.png
│       └── comparison_*.png
├── JSON_VISUALIZATION_GUIDE.md              # 상세 가이드
└── DATA_SETUP_REPORT.md                     # 데이터 가이드
```

---

## 📈 차트 기술 스택

### Python 시각화
- **라이브러리**: matplotlib, seaborn, pandas, numpy
- **형식**: PNG (300 DPI, 고품질)
- **특징**: 완전 자동화, 배치 처리 지원

### React 컴포넌트
- **라이브러리**: Ant Design, TypeScript
- **특징**: 인터랙티브, 실시간 업데이트, 반응형 디자인
- **성능**: 경량 (추가 라이브러리 최소화)

---

## 🎨 차트 색상 규칙

| 상황 | 색상 | 의미 |
|-----|------|------|
| 정상 | 초록(#52c41a) | OK, 안전 |
| 이상/경고 | 빨강(#ff7875) | 주의 필요 |
| 정보/중립 | 파랑(#1677ff) | 정보 제공 |
| 중요도 중간 | 주황(#faad14) | 검토 권장 |
| 비활성 | 회색(#d9d9d9) | 비해당 |

---

## ✨ 주요 특징

✅ **자동 메트릭 추출**: JSON 구조 자동 분석  
✅ **다중 차트 유형**: 파이, 히스토그램, 막대, 라인, 테이블 등  
✅ **높은 해석력**: 차트마다 명확한 라벨과 범례  
✅ **비교 분석**: Task vs Causal 동시 분석  
✅ **확장성**: 새로운 메트릭 추가 용이  
✅ **성능**: 대용량 데이터 처리 최적화  

---

## 📚 참고 자료

- [Python 시각화 가이드](./JSON_VISUALIZATION_GUIDE.md#b-frontend-react-컴포넌트로-시각화)
- [React 컴포넌트 API](./JSON_VISUALIZATION_GUIDE.md#-차트-컴포넌트-상세-설명)
- [해석 가이드](./JSON_VISUALIZATION_GUIDE.md#-해석-가이드)
- [프로젝트 구조](./anomali.md)

---

## 🎯 다음 단계

1. **실시간 대시보드**: WebSocket 연동
2. **고급 필터링**: 메트릭별 커스텀 필터
3. **알림 시스템**: 임계값 기반 자동 알림
4. **내보내기**: PDF/Excel 지원
5. **머신러닝 인사이트**: 자동 이상 패턴 인식

---

## 📞 지원

- 🐛 **버그 보고**: GitHub Issues
- 💡 **기능 요청**: GitHub Discussions
- 📖 **문서**: [JSON_VISUALIZATION_GUIDE.md](./JSON_VISUALIZATION_GUIDE.md)

---

**작성일**: 2026년 4월 28일  
**버전**: 1.0.0  
**상태**: ✅ Production Ready
