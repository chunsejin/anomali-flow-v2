# 📊 Task Result & Causal Report 시각화 가이드

## 개요

Task Result와 Causal Report의 Raw JSON 데이터를 효과적으로 시각화하고 분석하기 위한 차트 컴포넌트 및 도구 모음입니다.

---

## 🎯 제공되는 시각화 유형

### 1. **Task Result 시각화**

#### Outlier Distribution Chart
- **설명**: 정상/이상 데이터의 비율을 파이 차트로 표시
- **사용 사례**: 이상치 탐지 결과의 심각도 파악
- **메트릭**: 이상치 개수, 비율, 임계값

```python
# Python 사용 예
from scripts.visualize_json_reports import JsonVisualizer

visualizer = JsonVisualizer()
visualizer.visualize_task_result(task_data, save=True)
```

#### Score Distribution
- **설명**: 이상치 점수(outlier score)의 분포도
- **사용 사례**: 이상 탐지 모델의 신뢰도 평가
- **메트릭**: 정상/이상 점수의 분리도

#### Metrics Overview
- **설명**: 수치 메트릭들의 상위 10개를 막대 그래프로 표시
- **사용 사례**: Task result의 주요 지표 파악

---

### 2. **Causal Report 시각화**

#### Effect Size & Confidence Interval
- **설명**: 인과 효과 크기와 신뢰도 구간을 에러바 그래프로 표시
- **사용 사례**: 처치(treatment) 효과의 신뢰도 평가
- **메트릭**: Effect Size, CI Low, CI High, CI Width

```python
# Python 사용 예
visualizer.visualize_causal_report(causal_data, save=True)
```

#### Causal DAG (Directed Acyclic Graph)
- **설명**: Treatment → Outcome 관계와 교란변수(confounders) 표시
- **사용 사례**: 인과 구조 이해 및 검증

#### Effect Size Category
- **설명**: Effect Size를 크기별 범주(Weak/Moderate/Strong/Very Strong)로 분류
- **사용 사례**: 효과 크기의 실질적 의미 해석

#### Robustness Check
- **설명**: Refutation test 결과 및 통계적 안정성 표시
- **사용 사례**: 인과분석 결과의 신뢰성 판단

---

### 3. **비교 분석 시각화**

#### Anomaly Rate vs Effect Size
- **설명**: 이상치 발생률과 인과 효과를 병렬로 비교
- **사용 사례**: 이상 발생과 처치 효과의 상관관계 파악

```python
# Python 사용 예
visualizer.visualize_comparison(task_data, causal_data, save=True)
```

#### Treatment-Outcome Relationship
- **설명**: 처치와 결과의 인과 관계 표현
- **사용 사례**: 전체 인과 시나리오 이해

#### Confidence Analysis
- **설명**: 신뢰도 구간 시각화로 불확실성 표현
- **사용 사례**: 효과 추정의 정확도 평가

---

## 💻 사용 방법

### A. Python 스크립트로 시각화 생성

#### 1단계: 스크립트 실행

```bash
cd e:\anomali-flow-v2
python scripts/visualize_json_reports.py
```

#### 2단계: 생성된 이미지 확인

```bash
# 생성 위치
data/visualizations/
├── task_result_<task_id>.png
├── causal_report_<analysis_id>.png
└── comparison_<task_id>.png
```

#### 3단계: 커스텀 데이터로 시각화

```python
from pathlib import Path
from scripts.visualize_json_reports import JsonVisualizer
import json

# 자신의 JSON 데이터 로드
with open("data/my_task_result.json") as f:
    task_data = json.load(f)

with open("data/my_causal_report.json") as f:
    causal_data = json.load(f)

# 시각화 생성
visualizer = JsonVisualizer(output_dir=Path("data/visualizations"))
visualizer.visualize_task_result(task_data, save=True)
visualizer.visualize_causal_report(causal_data, save=True)
visualizer.visualize_comparison(task_data, causal_data, save=True)
```

---

### B. Frontend (React) 컴포넌트로 시각화

#### 1. TaskResultView에서 차트 표시

```tsx
import {
  TaskResultOutlierChart,
  JsonMetricsTable,
  JsonHierarchyView,
} from "./components/JsonVisualizer";

function TaskResultView({ token }: { token: string }) {
  const [taskData, setTaskData] = useState<TaskData | null>(null);

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {/* 기존 코드... */}
      
      {/* 새로운 시각화 컴포넌트 */}
      <TaskResultOutlierChart data={taskData} />
      <JsonMetricsTable data={taskData?.result} />
      <JsonHierarchyView data={taskData} title="Task Data Structure" />
    </Space>
  );
}
```

#### 2. CausalReportView에서 차트 표시

```tsx
import {
  CausalDagChart,
  CausalEffectChart,
  JsonMetricsTable,
} from "./components/JsonVisualizer";

function CausalReportView({ token }: { token: string }) {
  const [causalData, setData] = useState<Record<string, unknown> | null>(null);

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {/* 기존 코드... */}
      
      {/* 새로운 시각화 컴포넌트 */}
      <CausalDagChart data={causalData} />
      <CausalEffectChart data={causalData} />
      <JsonMetricsTable data={causalData} />
    </Space>
  );
}
```

#### 3. 통합 분석 대시보드

```tsx
import { IntegratedAnalysisDashboard } from "./components/IntegratedAnalysisDashboard";

// 메인 App에서 새 탭으로 추가
<Tabs>
  <TabPane tab="Integrated Analysis" key="analysis">
    <IntegratedAnalysisDashboard 
      token={token}
      getEnvelopeFunc={getEnvelope}
    />
  </TabPane>
</Tabs>
```

---

## 📊 차트 컴포넌트 상세 설명

### TaskResultOutlierChart
```tsx
interface TaskResultData {
  task_id: string;
  status: string;
  result?: {
    outlier_indices?: number[];      // 이상치 인덱스 배열
    outlier_scores?: number[];       // 이상치 점수
    index?: unknown[];               // 전체 인덱스
  };
}
```

**표시되는 정보:**
- ✅ 전체 레코드 수
- ✅ 탐지된 이상치 수
- ✅ 이상치 비율 (%)
- ✅ 색상 코딩: 정상(초록색), 이상(빨강색)

---

### CausalEffectChart
```tsx
interface CausalReportData {
  effect_size: number;              // 처치 효과 크기
  confidence_interval?: {
    low: number;                    // 신뢰도 구간 하한
    high: number;                   // 신뢰도 구간 상한
  };
}
```

**표시되는 정보:**
- ✅ Effect Size 값과 레이블 (Weak/Moderate/Strong/Very Strong)
- ✅ 95% 신뢰도 구간
- ✅ 구간 폭 (CI Width)
- ✅ 시각적 범위 표시 (SVG 에러바)

---

### CausalDagChart
```tsx
interface CausalReportData {
  treatment: string;                // 처치 변수명
  outcome: string;                  // 결과 변수명
  confounders?: string[];           // 교란변수 목록
  refutation_result?: string;       // 반박 검정 결과
}
```

**표시되는 정보:**
- ✅ Treatment → Outcome 화살표
- ✅ 식별된 Confounder 목록
- ✅ Robustness check 결과
- ✅ 색상: 파랑(Treatment), 초록(Outcome), 주황(Confounder)

---

### JsonMetricsTable
```tsx
// JSON의 모든 수치 메트릭을 자동 추출
// 최상위 20개 메트릭을 표로 표시

columns: [
  "Metric Name",     // 메트릭 이름 (계층 구조)
  "Type",            // 데이터 타입 (number/string/boolean/array/object)
  "Value",           // 실제 값
  "Distribution"     // 진행바로 값의 범위 표시
]
```

---

### JsonHierarchyView
```tsx
// JSON 구조를 계층적으로 표시
// 최대 3단계 깊이까지 표현

표시 형식:
├── key1: value
├── key2: [Array] (5 items)
│   ├── [0]: ...
│   ├── [1]: ...
│   └── ...
└── key3: { Object }
    ├── nested1: ...
    └── nested2: ...
```

---

### ComparisonDashboard
```tsx
// Task Result와 Causal Report를 함께 비교

표시 항목:
1. Anomalies Detected (red/green)
2. Causal Effect Size (blue/red)
3. Treatment (메트릭)
4. Outcome (메트릭)
5. 통찰력 (Insight): 이상 vs 인과 효과 연관성
```

---

## 🔍 해석 가이드

### Outlier Rate가 높은데 Effect Size가 낮은 경우
```
⚠️ 이상치가 많이 탐지되지만, 식별된 처치의 인과 효과가 약함
→ 다른 원인 후보 탐색 필요
→ 처치 정의 재검토 필요
```

### Outlier Rate와 Effect Size가 모두 높은 경우
```
✓ 이상치 탐지와 인과 효과가 일치
→ 식별된 처치가 이상 원인으로 타당함
→ 신뢰도 높은 분석 결과
```

### Confidence Interval이 넓은 경우
```
⚠️ 효과 추정의 불확실성이 큼
→ 데이터 부족 또는 노이즈 많음
→ 더 많은 관찰 필요
```

### Refutation Test가 Failed인 경우
```
⚠️ 숨겨진 교란변수 가능성 높음
→ 인과 결론 신뢰도 낮음
→ 추가 분석 또는 실험 필요
```

---

## 📁 파일 구조

```
anomali-flow-v2/
├── scripts/
│   └── visualize_json_reports.py       # Python 시각화 스크립트
├── frontend/
│   └── src/
│       └── components/
│           ├── JsonVisualizer.tsx      # React 시각화 컴포넌트
│           └── IntegratedAnalysisDashboard.tsx  # 통합 대시보드
└── data/
    └── visualizations/                # 생성된 차트 저장 위치
        ├── task_result_*.png
        ├── causal_report_*.png
        └── comparison_*.png
```

---

## 🚀 다음 단계

1. **실시간 대시보드**: WebSocket을 통해 실시간 업데이트
2. **고급 필터링**: 특정 메트릭만 표시하도록 커스터마이징
3. **내보내기**: PDF, Excel 등 다양한 형식으로 내보내기
4. **비교 분석**: 여러 Task/Report를 동시 비교
5. **이상 조건 경고**: 임계값 초과 시 자동 알림

---

## 📞 문의 및 지원

- **문제 보고**: Issue 제출
- **기능 요청**: PR 제출
- **문서**: 프로젝트 README 참고

---

**Last Updated**: 2026년 4월 28일  
**Version**: 1.0.0
