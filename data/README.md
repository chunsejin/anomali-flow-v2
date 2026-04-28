# Anomaly Detection 데이터셋 저장소

## 폴더 구조

```
data/
├── timeseries/              # 시계열 데이터
│   ├── univariate/          # 단변량 시계열
│   │   ├── raw/             # 원본 데이터
│   │   └── processed/       # 전처리된 데이터
│   └── multivariate/        # 다변량 시계열
│       ├── raw/
│       └── processed/
├── numerical/               # 수치형 데이터
│   ├── tabular/             # 테이블 형식 데이터
│   │   ├── raw/
│   │   └── processed/
│   └── high_dim/            # 고차원 데이터
│       ├── raw/
│       └── processed/
├── categorical/             # 혼합/범주형 데이터
│   └── mixed/
│       ├── raw/
│       └── processed/
└── archive/                 # 기존 데이터 보관
```

## 데이터셋 요약

| 카테고리 | 타입 | 크기 | 특징 |
|------|------|------|------|
| **timeseries/univariate** | 시계열 | 1000-5000 | 단일 변수, 시간 계열성 |
| **timeseries/multivariate** | 시계열 | 500-10000 | 다중 변수, 상관관계 |
| **numerical/tabular** | 테이블 | 1000-500K | 전형적인 ML 데이터 |
| **numerical/high_dim** | 수치 | 200-5000 | 수십~수백 특성 |
| **categorical/mixed** | 혼합 | 500-10000 | 수치+범주형 혼합 |

## 사용 방법

### 1. 데이터 탐색
```python
import pandas as pd

# 시계열 단변량
df = pd.read_csv('timeseries/univariate/raw/synthetic_univariate.csv')

# 시계열 다변량
df = pd.read_csv('timeseries/multivariate/raw/synthetic_multivariate_sensor.csv')

# 수치형 테이블
df = pd.read_csv('numerical/tabular/raw/synthetic_tabular_transactions.csv')
```

### 2. 이상 탐지 모델 학습
```python
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

df = pd.read_csv('numerical/tabular/raw/synthetic_tabular_transactions.csv')
X = df.drop('label', axis=1)
y = df['label']

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

model = IsolationForest(contamination=0.05)
y_pred = model.fit_predict(X_scaled)
```

### 3. 성능 평가
```python
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score

precision, recall, f1, _ = precision_recall_fscore_support(y, y_pred, average='binary')
auc = roc_auc_score(y, model.score_samples(X_scaled))
```

## 권장 모델

### 시계열 데이터
- **Rule-based**: Moving Average, EWMA, IQR
- **ML**: Isolation Forest, LOF, XGBoost
- **DL**: LSTM Autoencoder, Transformer

### 수치형 테이블
- **ML**: Isolation Forest, One-Class SVM, LOF
- **DL**: Autoencoder, Variational Autoencoder

### 고차원 데이터
- **PCA**: 차원 축소 후 이상 탐지
- **Autoencoder**: 비선형 차원 축소

### 혼합/범주형 데이터
- **CatBoost**: 범주형 변수 직접 처리
- **One-Hot + ML**: 범주형 인코딩 후 모델 적용

## 참고 자료

- PyOD: https://pyod.readthedocs.io/
- Scikit-learn Outlier Detection: https://scikit-learn.org/stable/modules/outlier_detection.html
- DoWhy: https://py-why.github.io/dowhy/
- Anomali.md (프로젝트 가이드): ../anomali.md

## 라이센스
각 데이터셋의 원본 라이센스를 참고하세요.
