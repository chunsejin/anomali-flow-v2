아래처럼 **“이상치 탐지 → 원인 후보 도출 → 인과 검증 → 조치 추천 → 모델 운영관리”**가 하나의 폐루프로 돌아가도록 프로젝트 체계를 잡는 것이 가장 안정적입니다.

---

# 1. 전체 프로젝트 구조

## 프로젝트명 예시

**AI 기반 이상치·인과분석 모델 생성 및 운영관리 플랫폼**

## 핵심 목표

* 센서·로그·거래·사용자 행동 데이터에서 **이상치/이상상태를 자동 탐지**
* 단순 상관관계가 아니라 **원인 변수, 영향 경로, 조치 효과**를 인과적으로 분석
* 탐지 모델, 인과 모델, 설명 모델을 **반복 생성·검증·배포·모니터링**
* 현업 담당자가 “왜 이상인가?”, “무엇이 원인인가?”, “무엇을 조치해야 하는가?”를 확인할 수 있는 운영 체계 구축

---

# 2. 권장 아키텍처

```text
[데이터 수집]
센서 / MES / ERP / 웹로그 / 거래 / 품질검사 / 고객행동
        ↓
[데이터 레이크·시계열 DB]
Raw Data / 정제 데이터 / 이벤트 로그 / 라벨 데이터
        ↓
[Feature Store]
통계 Feature / 시계열 Feature / 공정 Feature / 사용자 Feature
        ↓
[이상치 탐지 모델]
Rule-based / Isolation Forest / LOF / AutoEncoder / LSTM / Transformer
        ↓
[원인 후보 분석]
SHAP / Feature Importance / 변화점 탐지 / 이벤트 연관 분석
        ↓
[인과분석 모델]
DAG / SCM / DoWhy / EconML / Causal Forest / Double ML
        ↓
[조치 추천·시뮬레이션]
Counterfactual / What-if / 정책 효과 추정
        ↓
[운영관리]
MLflow / Model Registry / 모니터링 / 재학습 / 승인 워크플로우
```

이상치 탐지는 보통 **비지도 이상치 탐지**와 **신규성 탐지**로 나눌 수 있으며, scikit-learn 문서에서도 outlier detection은 주로 비지도 이상 탐지, novelty detection은 정상 데이터 기반의 준지도 탐지로 구분합니다. ([Scikit-learn][1])

---

# 3. 프로젝트 Work Package 체계

| 구분              | 주요 내용                                          | 산출물                        |
| --------------- | ---------------------------------------------- | -------------------------- |
| WP1. 문제정의       | 이상상태 정의, KPI, 현업 의사결정 시나리오 정의                  | 문제정의서, 이상유형 목록             |
| WP2. 데이터 체계     | 데이터 수집, 정제, 품질관리, 라벨링 기준 수립                    | 데이터 사전, 라벨링 가이드            |
| WP3. Feature 설계 | 시계열, 통계, 이벤트, 도메인 Feature 생성                   | Feature 명세서, Feature Store |
| WP4. 이상치 탐지     | 규칙기반 + ML/DL 기반 이상탐지 모델 개발                     | 이상탐지 모델, 성능 리포트            |
| WP5. 원인 후보 분석   | SHAP, 중요도 분석, 변화점 탐지, 이벤트 상관분석                 | 원인 후보 리포트                  |
| WP6. 인과분석       | DAG 설계, treatment/outcome/confounder 정의, 효과 추정 | 인과 그래프, 효과 추정 결과           |
| WP7. 조치 추천      | counterfactual, what-if 분석, 조치 우선순위 도출         | 조치 추천 모델, 시뮬레이션 결과         |
| WP8. MLOps 운영   | 모델 등록, 승인, 배포, 모니터링, 재학습                       | 모델 레지스트리, 운영 대시보드          |

---

# 4. 이상치 분석 체계

## 4.1 이상치 유형 정의

먼저 이상치를 하나로 보지 말고 다음처럼 분류해야 합니다.

| 유형                 | 설명         | 예시                         |
| ------------------ | ---------- | -------------------------- |
| Point Anomaly      | 단일 값이 비정상  | 온도 200℃ 급등                 |
| Contextual Anomaly | 상황 대비 비정상  | 야간에는 정상이나 주간에는 비정상인 전력 사용량 |
| Collective Anomaly | 패턴 전체가 비정상 | 일정 구간의 진동 패턴 변화            |
| Change Point       | 상태 전환 지점   | 장비 성능이 특정 시점 이후 저하         |
| Drift              | 데이터 분포 변화  | 계절, 설비 노후화, 사용자 행동 변화      |

## 4.2 모델 구성

| 단계             | 모델                                            | 목적            |
| -------------- | --------------------------------------------- | ------------- |
| 1차 Baseline    | IQR, Z-score, Moving Average, EWMA            | 빠른 규칙 기반 탐지   |
| 2차 ML          | Isolation Forest, LOF, One-Class SVM, XGBoost | 다변량 이상치 탐지    |
| 3차 DL          | AutoEncoder, LSTM-AE, Transformer, VAE        | 복잡한 시계열 패턴 탐지 |
| 4차 Ensemble    | Rule + ML + DL Score Fusion                   | 탐지 안정성 향상     |
| 5차 Explanation | SHAP, Attention, Feature Attribution          | 이상 원인 설명      |

PyOD는 Python 기반 이상치 탐지 라이브러리로, tabular, time series, graph, text, image 데이터에 적용 가능한 다양한 detector를 제공하므로 초기 PoC와 알고리즘 비교에 적합합니다. ([PyOD][2])

---

# 5. 인과분석 체계

이상치 탐지만으로는 “무엇이 원인인가?”를 확정하기 어렵습니다. 따라서 이상치 탐지 후에는 **인과 그래프 기반 분석**으로 넘어가야 합니다.

## 5.1 인과분석 기본 구조

| 요소         | 설명            | 예시                    |
| ---------- | ------------- | --------------------- |
| Treatment  | 원인 후보 변수      | 압력 증가, 온도 상승, 광고비 증액  |
| Outcome    | 결과 변수         | 불량률, 매출, 이탈률, 고장률     |
| Confounder | 교란변수          | 생산라인, 작업자, 계절, 캠페인 유형 |
| Mediator   | 매개변수          | 체류시간, 장비 부하율          |
| DAG        | 변수 간 원인-결과 구조 | 온도 → 압력 → 불량률         |

DoWhy는 인과분석을 위해 ① causal graph와 구조적 가정 모델링, ② 식별 가능성 판단, ③ 효과 추정, ④ robustness check와 sensitivity analysis를 통한 반박 검증이라는 4단계 API를 제시합니다. ([Microsoft][3])

## 5.2 인과분석 모델

| 목적          | 권장 방법                                               |
| ----------- | --------------------------------------------------- |
| 평균 효과 추정    | ATE, ATT, Difference-in-Differences                 |
| 개별 조건별 효과   | CATE, HTE, Causal Forest                            |
| 관측데이터 기반 추정 | Propensity Score, Double ML                         |
| 조치 시뮬레이션    | Counterfactual Inference                            |
| 원인 검증       | Refutation Test, Placebo Test, Sensitivity Analysis |

EconML은 관측데이터 또는 실험데이터에서 개별화된 처치효과, 즉 heterogeneous treatment effect를 추정하기 위한 causal machine learning 패키지로 활용할 수 있습니다. ([PyWhy][4])

---

# 6. AI 모델 생성·분석 관리 체계

핵심은 “모델을 한 번 개발하고 끝내는 것”이 아니라, **모델 생성–검증–승인–배포–감시–재학습**을 체계화하는 것입니다.

## 6.1 Model Factory 구조

| 구성요소                | 역할                                        |
| ------------------- | ----------------------------------------- |
| Data Versioning     | 학습 데이터 버전 관리                              |
| Feature Registry    | Feature 정의, 생성 방식, 사용 이력 관리               |
| Experiment Tracking | 모델별 파라미터, 성능, 데이터셋, 코드 버전 기록              |
| Model Registry      | 승인된 모델 버전 관리                              |
| Evaluation Report   | Precision, Recall, F1, PR-AUC, 탐지 지연시간 기록 |
| Causal Report       | 인과 그래프, 효과 크기, 신뢰구간, 반박검정 결과 기록           |
| Approval Workflow   | 연구자·현업·관리자의 배포 승인                         |
| Monitoring          | 성능 저하, 데이터 drift, 이상탐지 알람 품질 감시           |

MLflow Model Registry는 등록 모델에 대해 고유 이름, 버전, alias, tag, metadata를 관리할 수 있어 모델 생명주기 관리에 적합합니다. ([MLflow AI Platform][5])

## 6.2 Feature Store 운영

Feature Store는 학습과 운영 환경에서 같은 Feature를 재사용하게 해주는 핵심 계층입니다. Feast는 production ML 시스템에서 Feature를 정의, 관리, 검증, 서빙하기 위한 오픈소스 Feature Store로 설명됩니다. ([Feast][6])

---

# 7. 운영 거버넌스 체계

AI 모델 운영은 기술만으로는 부족합니다. 다음과 같은 거버넌스가 필요합니다.

| 영역       | 관리 항목                            |
| -------- | -------------------------------- |
| 데이터 거버넌스 | 데이터 출처, 품질, 결측, 이상값, 라벨 신뢰도      |
| 모델 거버넌스  | 모델 버전, 승인자, 사용 목적, 적용 범위         |
| 인과 거버넌스  | DAG 근거, 변수 정의, 교란변수 통제 여부        |
| 리스크 관리   | 오탐, 미탐, 잘못된 원인판단, 자동조치 위험        |
| 설명가능성    | 이상치 근거, 주요 변수, 원인 후보, 조치 근거      |
| 감사 추적성   | 누가, 언제, 어떤 모델을, 어떤 데이터로 배포했는지 기록 |

NIST AI RMF는 AI 위험관리를 Govern, Map, Measure, Manage의 네 가지 기능으로 구성하므로, 이 프로젝트의 운영 거버넌스도 이 구조를 참조하는 것이 좋습니다. ([NIST AI Resource Center][7])

---

# 8. 성능평가 지표

## 8.1 이상치 탐지 평가

| 지표               | 설명                       |
| ---------------- | ------------------------ |
| Precision        | 이상이라고 판단한 것 중 실제 이상 비율   |
| Recall           | 실제 이상 중 탐지한 비율           |
| F1-score         | Precision과 Recall의 균형    |
| PR-AUC           | 이상치가 희소한 경우 ROC-AUC보다 유용 |
| False Alarm Rate | 오탐 비율                    |
| Detection Delay  | 이상 발생 후 탐지까지 걸린 시간       |
| Top-k Hit Rate   | 상위 k개 이상 알람 중 실제 이상 비율   |

## 8.2 인과분석 평가

| 지표                        | 설명                |
| ------------------------- | ----------------- |
| Effect Size               | 처치가 결과에 미치는 영향 크기 |
| Confidence Interval       | 효과 추정의 불확실성       |
| Refutation Test Pass Rate | 반박검정 통과율          |
| Sensitivity Score         | 숨은 교란변수에 대한 민감도   |
| Policy Uplift             | 조치 적용 시 개선 효과     |
| Counterfactual Validity   | 반사실 시나리오의 타당성     |

DoWhy 문서에서도 관측데이터 기반 인과분석 결과는 “증명”이라기보다 여러 robustness test로 반박을 시도해야 하며, 반박검정을 통과하지 못한 분석은 수정되어야 한다고 설명합니다. ([PyWhy][8])

---

# 9. 권장 개발 일정: 3개월 PoC 기준

| 기간     | 주요 과업                 | 산출물                 |
| ------ | --------------------- | ------------------- |
| 1~2주차  | 문제정의, 데이터 조사, 이상유형 정의 | 요구사항 정의서, 데이터 목록    |
| 3~4주차  | 데이터 파이프라인, Feature 설계 | 정제 데이터셋, Feature 명세 |
| 5~6주차  | Baseline 이상치 모델 개발    | Rule/ML 기반 모델       |
| 7~8주차  | DL 모델 및 Ensemble 구성   | AutoEncoder/LSTM 모델 |
| 9~10주차 | 인과 그래프 설계 및 효과 추정     | DAG, 인과분석 리포트       |
| 11주차   | 모델 관리·대시보드 구축         | MLflow, 알람 대시보드     |
| 12주차   | 통합 검증 및 PoC 보고        | 최종 보고서, 운영 가이드      |

Google Cloud의 MLOps 문서도 ML 시스템에서 CI, CD, CT, 즉 지속적 통합·배포·학습 자동화를 구현하는 접근을 설명하고 있으므로, 3개월 PoC 이후에는 재학습과 모니터링 자동화까지 확장하는 것이 바람직합니다. ([Google Cloud Documentation][9])

---

# 10. 최종 추천 체계

가장 현실적인 운영 구조는 다음과 같습니다.

```text
1단계: 이상치 탐지
- Rule 기반 빠른 탐지
- ML/DL 기반 정밀 탐지
- 이상 점수 산출

2단계: 설명 분석
- 어떤 Feature가 이상 탐지에 기여했는지 분석
- SHAP, Feature Importance, 변화점 탐지 적용

3단계: 인과분석
- 원인 후보를 DAG로 구조화
- Treatment, Outcome, Confounder 정의
- DoWhy/EconML 기반 효과 추정

4단계: 조치 추천
- What-if 분석
- Counterfactual 시뮬레이션
- 조치 우선순위 산정

5단계: 운영관리
- 모델 버전 관리
- 성능 모니터링
- 데이터 Drift 감지
- 재학습 및 승인 워크플로우
```

