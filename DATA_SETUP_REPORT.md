## 📊 Anomaly Detection 데이터셋 설정 완료 보고서

### ✅ 완료된 작업

#### 1️⃣ 폴더 구조 조직

```
data/
├── timeseries/
│   ├── univariate/          ← 단변량 시계열 데이터
│   │   ├── raw/
│   │   └── processed/
│   └── multivariate/        ← 다변량 시계열 데이터
│       ├── raw/
│       └── processed/
├── numerical/
│   ├── tabular/             ← 테이블 형 수치 데이터
│   │   ├── raw/
│   │   └── processed/
│   └── high_dim/            ← 고차원 수치 데이터
│       ├── raw/
│       └── processed/
├── categorical/
│   └── mixed/               ← 혼합형 카테고리 데이터
│       ├── raw/
│       └── processed/
└── archive/                 ← 기존 데이터 보관
```

---

#### 2️⃣ 생성된 데이터셋 (7개)

| # | 카테고리 | 파일명 | 타입 | 크기 | 특징 |
|---|---------|--------|------|------|------|
| 1 | timeseries/univariate | `synthetic_univariate.csv` | 시계열 단변량 | 1,000 rows | 사인 패턴 + 3개 이상치 구간 |
| 2 | timeseries/multivariate | `synthetic_multivariate_sensor.csv` | 시계열 다변량 | 500 rows | 3개 센서 (온도/기압/습도) + 이상치 |
| 3 | timeseries/multivariate | `timeseries_DailyDelhiClimateTest.csv` | 시계열 실제 | 1,461 rows | 실제 기후 데이터 (Delhi) |
| 4 | numerical/tabular | `synthetic_tabular_transactions.csv` | 수치 테이블 | 1,000 rows | 거래 특성 5개 + 5% 이상치 |
| 5 | numerical/high_dim | `synthetic_high_dim.csv` | 고차원 수치 | 200 rows | 100개 특성 + 10% 이상치 |
| 6 | numerical/high_dim | `breast_cancer.csv` | 의료 데이터 | 569 rows | 유방암 진단 (30개 특성) |
| 7 | categorical/mixed | `categorical_bike_buyers_clean.csv` | 혼합형 | 1,000 rows | 자전거 구매자 (수치+범주형) |
| 8 | categorical/mixed | `synthetic_mixed_network.csv` | 혼합형 | 500 rows | 네트워크 트래픽 데이터 |

---

#### 3️⃣ 각 카테고리별 데이터 설명

##### 🕐 **시계열 (TimeSeries)**

**단변량 (Univariate)**
- 단일 변수의 시간 계열 데이터
- 사용 모델: ARIMA, LSTM Autoencoder, Isolation Forest
- 이상치 유형: 스파이크, 급상승/급하강

```python
import pandas as pd
df = pd.read_csv('timeseries/univariate/raw/synthetic_univariate.csv')
# 특성: timestamp, value, label
# Label: 0=정상, 1=이상
```

**다변량 (Multivariate)**
- 여러 센서/지표의 동시 기록 데이터
- 사용 모델: VAR, Multivariate LSTM, Transformer
- 이상치 유형: 변수 간 상관관계 붕괴

```python
df_climate = pd.read_csv('timeseries/multivariate/raw/timeseries_DailyDelhiClimateTest.csv')
# Delhi 기후 데이터: 온도, 습도, 풍속, 기압

df_sensor = pd.read_csv('timeseries/multivariate/raw/synthetic_multivariate_sensor.csv')
# 센서 데이터: 온도, 기압, 습도 (3개 변수)
```

---

##### 🔢 **수치형 (Numerical)**

**테이블 형식 (Tabular)**
- 행이 레코드, 열이 특성인 전형적인 데이터프레임
- 사용 모델: Isolation Forest, LOF, One-Class SVM
- 특성: 거래액, 시간간격, 위험도, 계정나이, 실패시도 등

```python
df_tx = pd.read_csv('numerical/tabular/raw/synthetic_tabular_transactions.csv')
# 거래 데이터: 5개 수치 특성 + 이상치 레이블

# 기본 분석
print(df_tx.describe())
print(f"이상치 비율: {df_tx['label'].mean():.1%}")
```

**고차원 (High Dimensional)**
- 수십~수백 개의 특성을 가진 데이터
- 사용 모델: PCA, Autoencoder, VAE
- 특징: 차원의 저주 극복 필요

```python
# 의료 데이터
df_cancer = pd.read_csv('numerical/high_dim/raw/breast_cancer.csv')
# 30개 특성 (암 진단 관련)

# 합성 고차원 데이터
df_high = pd.read_csv('numerical/high_dim/raw/synthetic_high_dim.csv')
# 100개 특성 + 이상치 (10%)
```

---

##### 🏷️ **혼합형/카테고리 (Categorical/Mixed)**

- 수치형과 범주형 특성이 혼합된 데이터
- 사용 모델: CatBoost, One-Hot Encoding + Isolation Forest
- 특징: 범주형 변수 인코딩 필요

```python
# 자전거 구매자 데이터
df_bike = pd.read_csv('categorical/mixed/raw/categorical_bike_buyers_clean.csv')

# 네트워크 트래픽 데이터
df_network = pd.read_csv('categorical/mixed/raw/synthetic_mixed_network.csv')
# IP 타입, 프로토콜, 포트 번호, 데이터 전송량 등
```

---

### 🎯 활용 방법

#### **1단계: 데이터 탐색**

```python
import pandas as pd
import numpy as np

# 1. 시계열 단변량
df = pd.read_csv('data/timeseries/univariate/raw/synthetic_univariate.csv')
print(df.head())
print(f"Shape: {df.shape}")
print(f"이상치: {df['label'].sum()} / {len(df)}")

# 시각화
import matplotlib.pyplot as plt
plt.figure(figsize=(12, 4))
plt.plot(df['value'], alpha=0.7)
anomalies = df[df['label'] == 1]
plt.scatter(anomalies.index, anomalies['value'], color='red', s=50, label='Anomaly')
plt.legend()
plt.show()
```

#### **2단계: 전처리**

```python
from sklearn.preprocessing import StandardScaler, RobustScaler

X = df.drop(['timestamp', 'label'], axis=1)
y = df['label']

# 정규화 (이상치에 민감하지 않은 RobustScaler 권장)
scaler = RobustScaler()
X_scaled = scaler.fit_transform(X)
```

#### **3단계: 이상 탐지 모델 학습**

```python
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

# Isolation Forest
model = IsolationForest(contamination=0.05, random_state=42)
y_pred = model.fit_predict(X_scaled)
y_score = model.score_samples(X_scaled)

# LOF
lof = LocalOutlierFactor(n_neighbors=20, contamination=0.05)
y_pred_lof = lof.fit_predict(X_scaled)

# One-Class SVM
ocsvm = OneClassSVM(kernel='rbf', gamma='auto')
y_pred_svm = ocsvm.fit_predict(X_scaled)
```

#### **4단계: 성능 평가**

```python
from sklearn.metrics import (
    precision_recall_fscore_support,
    roc_auc_score,
    confusion_matrix,
    roc_curve,
    auc
)

# 이진 평가
precision, recall, f1, _ = precision_recall_fscore_support(y, y_pred, average='binary')
roc_auc = roc_auc_score(y, y_score)

print(f"Precision: {precision:.3f}")
print(f"Recall: {recall:.3f}")
print(f"F1-Score: {f1:.3f}")
print(f"ROC-AUC: {roc_auc:.3f}")

# 혼동 행렬
cm = confusion_matrix(y, y_pred)
print(f"\n혼동 행렬:\n{cm}")
```

---

### 📚 권장 모델 가이드

#### **시계열 데이터**

| 모델 | 적용 유형 | 장점 | 단점 |
|------|---------|------|------|
| **Moving Average** | 규칙 기반 | 빠름, 간단 | 복잡한 패턴 미탐지 |
| **ARIMA** | 시계열 | 통계 기반, 해석 가능 | 정상성 가정 필요 |
| **Isolation Forest** | ML | 다변량 지원, 속도 | 조율 필요 |
| **LSTM AE** | DL | 복잡 패턴 학습 | 학습 데이터 필요, 해석성 낮음 |

#### **수치형 테이블 데이터**

| 모델 | 크기 | 권장 경우 |
|------|------|---------|
| **IForest** | < 100K | 기본 추천 |
| **LOF** | < 50K | 밀도 기반 이상 |
| **One-Class SVM** | < 50K | 작은 데이터 |
| **Autoencoder** | > 10K | 복잡한 패턴 |

#### **고차원 데이터**

```python
# PCA 기반 이상 탐지
from sklearn.decomposition import PCA

pca = PCA(n_components=10)
X_pca = pca.fit_transform(X_scaled)

# PCA 재구성 오차
X_reconstructed = pca.inverse_transform(X_pca)
reconstruction_error = np.sum((X_scaled - X_reconstructed) ** 2, axis=1)

# 임계값 설정
threshold = np.percentile(reconstruction_error, 95)
y_pred_pca = (reconstruction_error > threshold).astype(int)
```

---

### 📖 참고 자료

- **PyOD**: https://pyod.readthedocs.io/
- **Scikit-learn**: https://scikit-learn.org/stable/modules/outlier_detection.html
- **프로젝트 가이드**: [anomali.md](../anomali.md)
- **각 데이터셋 상세 정보**: `data/README.md`

---

### 🚀 다음 단계

1. **기본 모델 학습**: `scripts/train_baseline_models.py` 생성 및 실행
2. **앙상블 모델**: 여러 모델 점수 결합
3. **원인 분석**: SHAP, Feature Importance 적용
4. **인과분석**: DoWhy, EconML 활용
5. **대시보드**: 모니터링 및 알림 시스템 구축

---

**작성일**: 2024년 (프로젝트 실행 시점)  
**최종 수정**: 2026년 4월 28일
