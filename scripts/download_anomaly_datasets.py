"""
Anomaly Detection 벤치마크 데이터셋 다운로드 스크립트

다음 카테고리의 데이터셋을 다운로드합니다:
- 시계열 단변량 (Univariate Time Series)
- 시계열 다변량 (Multivariate Time Series)  
- 수치형 테이블 (Tabular Numerical)
- 고차원 수치 (High Dimensional)
- 혼합형 카테고리 (Mixed Categorical)
"""

import os
import urllib.request
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 기본 경로 설정
BASE_DIR = Path(__file__).parent.parent / "data"

def ensure_dir(path):
    """디렉토리가 없으면 생성"""
    path.mkdir(parents=True, exist_ok=True)
    return path

def download_file(url, filepath, description):
    """파일 다운로드"""
    try:
        print(f"📥 다운로드 중: {description}")
        urllib.request.urlretrieve(url, filepath)
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        print(f"   ✓ 완료: {filepath} ({file_size:.2f} MB)")
        return True
    except Exception as e:
        print(f"   ✗ 실패: {e}")
        return False

def generate_synthetic_data():
    """합성 데이터 생성"""
    print("\n" + "="*60)
    print("📊 합성 데이터 생성")
    print("="*60)
    
    # 1. 시계열 단변량 (정상 패턴 + 이상치)
    print("\n1️⃣  시계열 단변량 데이터 생성...")
    univariate_dir = ensure_dir(BASE_DIR / "timeseries" / "univariate" / "raw")
    
    np.random.seed(42)
    t = np.arange(1000)
    # 정상 시계열 (sin 패턴 + 노이즈)
    normal = 10 * np.sin(t / 100) + np.random.normal(0, 1, 1000)
    # 이상치 삽입
    anomaly = normal.copy()
    anomaly[200:210] = 25  # 급격한 상승
    anomaly[500:505] = -20  # 급격한 하강
    anomaly[800] = 50  # 단일 스파이크
    
    df_univariate = pd.DataFrame({
        'timestamp': pd.date_range('2023-01-01', periods=1000, freq='h'),
        'value': anomaly,
        'label': 0
    })
    df_univariate.loc[[200, 201, 202, 203, 204, 205, 206, 207, 208, 209], 'label'] = 1
    df_univariate.loc[[500, 501, 502, 503, 504], 'label'] = 1
    df_univariate.loc[800, 'label'] = 1
    
    df_univariate.to_csv(univariate_dir / "synthetic_univariate.csv", index=False)
    print(f"   ✓ {univariate_dir / 'synthetic_univariate.csv'} 생성")
    
    # 2. 시계열 다변량 (센서 데이터 패턴)
    print("\n2️⃣  시계열 다변량 데이터 생성...")
    multivariate_dir = ensure_dir(BASE_DIR / "timeseries" / "multivariate" / "raw")
    
    n_samples = 500
    np.random.seed(42)
    temp = 20 + 5 * np.sin(np.arange(n_samples) / 50) + np.random.normal(0, 1, n_samples)
    pressure = 1013 + 10 * np.cos(np.arange(n_samples) / 60) + np.random.normal(0, 2, n_samples)
    humidity = 50 + 15 * np.sin(np.arange(n_samples) / 40) + np.random.normal(0, 2, n_samples)
    
    # 이상치 주입
    temp[100:110] = 50
    pressure[200:205] = 900
    humidity[350:355] = 95
    
    df_multivariate = pd.DataFrame({
        'timestamp': pd.date_range('2023-01-01', periods=n_samples, freq='h'),
        'temperature': temp,
        'pressure': pressure,
        'humidity': humidity
    })
    
    df_multivariate.to_csv(multivariate_dir / "synthetic_multivariate_sensor.csv", index=False)
    print(f"   ✓ {multivariate_dir / 'synthetic_multivariate_sensor.csv'} 생성")
    
    # 3. 수치형 테이블 (전자상거래 거래 데이터)
    print("\n3️⃣  수치형 테이블 데이터 생성...")
    tabular_dir = ensure_dir(BASE_DIR / "numerical" / "tabular" / "raw")
    
    n_records = 1000
    np.random.seed(42)
    df_tabular = pd.DataFrame({
        'transaction_amount': np.random.exponential(50, n_records),
        'time_since_last_tx': np.random.exponential(100, n_records),
        'merchant_risk_score': np.random.uniform(0, 100, n_records),
        'user_account_age': np.random.uniform(1, 365 * 5, n_records),
        'num_failed_attempts': np.random.poisson(0.5, n_records)
    })
    
    # 이상치 주입 (고액 거래 + 높은 실패율)
    anomaly_indices = np.random.choice(n_records, 50, replace=False)
    df_tabular.loc[anomaly_indices, 'transaction_amount'] = np.random.uniform(500, 2000, 50)
    df_tabular.loc[anomaly_indices, 'num_failed_attempts'] = np.random.poisson(5, 50)
    
    df_tabular['label'] = 0
    df_tabular.loc[anomaly_indices, 'label'] = 1
    
    df_tabular.to_csv(tabular_dir / "synthetic_tabular_transactions.csv", index=False)
    print(f"   ✓ {tabular_dir / 'synthetic_tabular_transactions.csv'} 생성")
    
    # 4. 고차원 수치 데이터 (이미지-like)
    print("\n4️⃣  고차원 수치 데이터 생성...")
    high_dim_dir = ensure_dir(BASE_DIR / "numerical" / "high_dim" / "raw")
    
    n_samples = 200
    n_features = 100
    np.random.seed(42)
    X = np.random.normal(0, 1, (n_samples, n_features))
    
    # 이상치 샘플 (매우 다른 분포)
    anomaly_idx = np.random.choice(n_samples, 20, replace=False)
    X[anomaly_idx] = np.random.normal(5, 2, (20, n_features))
    
    df_high_dim = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(n_features)])
    df_high_dim['label'] = 0
    df_high_dim.loc[anomaly_idx, 'label'] = 1
    
    df_high_dim.to_csv(high_dim_dir / "synthetic_high_dim.csv", index=False)
    print(f"   ✓ {high_dim_dir / 'synthetic_high_dim.csv'} 생성")
    
    # 5. 카테고리/혼합 데이터 (네트워크 트래픽)
    print("\n5️⃣  혼합형 카테고리 데이터 생성...")
    mixed_dir = ensure_dir(BASE_DIR / "categorical" / "mixed" / "raw")
    
    n_records = 500
    np.random.seed(42)
    df_mixed = pd.DataFrame({
        'src_ip_type': np.random.choice(['internal', 'external'], n_records),
        'protocol': np.random.choice(['TCP', 'UDP', 'ICMP'], n_records),
        'packet_size': np.random.exponential(1000, n_records),
        'connection_duration': np.random.exponential(100, n_records),
        'port_number': np.random.choice([22, 80, 443, 3389, 8080, 9999], n_records),
        'data_transferred': np.random.exponential(10000, n_records)
    })
    
    # 이상치 주입 (비정상 프로토콜 + 거대 데이터 전송)
    anomaly_idx = np.random.choice(n_records, 30, replace=False)
    df_mixed.loc[anomaly_idx, 'packet_size'] = np.random.uniform(50000, 100000, 30)
    df_mixed.loc[anomaly_idx, 'data_transferred'] = np.random.uniform(500000, 1000000, 30)
    
    df_mixed['label'] = 0
    df_mixed.loc[anomaly_idx, 'label'] = 1
    
    df_mixed.to_csv(mixed_dir / "synthetic_mixed_network.csv", index=False)
    print(f"   ✓ {mixed_dir / 'synthetic_mixed_network.csv'} 생성")

def download_real_datasets():
    """공개 데이터셋 다운로드"""
    print("\n" + "="*60)
    print("📥 공개 데이터셋 다운로드")
    print("="*60)
    
    datasets = [
        {
            'name': 'KDD Cup 99 (침입 탐지)',
            'category': 'numerical/tabular/raw',
            'url': 'https://archive.ics.uci.edu/ml/machine-learning-databases/kddcup99-mld/kddcup.data.gz',
            'filename': 'kddcup99.gz',
            'description': 'KDD Cup 99 - 네트워크 침입 탐지 데이터'
        },
        {
            'name': 'Shuttle (우주선 데이터)',
            'category': 'numerical/tabular/raw',
            'url': 'https://archive.ics.uci.edu/ml/machine-learning-databases/shuttle/shuttle.trn',
            'filename': 'shuttle_train.txt',
            'description': 'Shuttle - 우주선 센서 이상 탐지'
        },
        {
            'name': 'Breast Cancer Wisconsin',
            'category': 'numerical/high_dim/raw',
            'url': 'https://archive.ics.uci.edu/ml/machine-learning-databases/breast-cancer-wisconsin/wdbc.data',
            'filename': 'breast_cancer.csv',
            'description': 'Breast Cancer - 의료 이상 탐지'
        }
    ]
    
    success_count = 0
    for dataset in datasets:
        try:
            filepath = BASE_DIR / dataset['category'] / dataset['filename']
            ensure_dir(filepath.parent)
            
            if not filepath.exists():
                if download_file(dataset['url'], filepath, dataset['description']):
                    success_count += 1
            else:
                print(f"✓ 이미 존재: {dataset['description']}")
                success_count += 1
        except Exception as e:
            print(f"✗ 오류 ({dataset['name']}): {e}")
    
    return success_count

def create_readme_files():
    """각 폴더에 README 파일 생성"""
    print("\n" + "="*60)
    print("📝 README 파일 생성")
    print("="*60)
    
    readme_content = {
        'timeseries/univariate': """# 시계열 단변량 데이터 (Univariate Time Series)

## 설명
- 시간에 따라 단일 변수의 값이 기록된 데이터
- 이상치: 갑작스러운 급증/급감, 스파이크, 트렌드 변화

## 사용 모델
- ARIMA, Exponential Smoothing
- Isolation Forest, LOF
- LSTM Autoencoder, GRU
- Prophet

## 데이터셋
- `synthetic_univariate.csv`: 합성 센서 데이터

## 평가 지표
- Precision, Recall, F1-Score
- Detection Delay
- False Alarm Rate
""",
        'timeseries/multivariate': """# 시계열 다변량 데이터 (Multivariate Time Series)

## 설명
- 시간에 따라 여러 변수가 동시에 기록된 데이터
- 이상치: 변수 간 상관관계 붕괴, 동시다발 편차

## 사용 모델
- Vector Autoregression (VAR)
- Multivariate LSTM Autoencoder
- Transformer
- Graph Neural Network

## 데이터셋
- `timeseries_DailyDelhiClimateTest.csv`: 실제 기후 데이터
- `synthetic_multivariate_sensor.csv`: 합성 센서 데이터

## 주의사항
- 변수 간 상관관계 고려
- 스케일 정규화 필수
""",
        'numerical/tabular': """# 수치형 테이블 데이터 (Tabular Numerical)

## 설명
- 행이 레코드, 열이 특성인 전형적인 데이터프레임
- 이상치: 통계적 이상, 도메인 기반 이상

## 사용 모델
- Isolation Forest
- Local Outlier Factor (LOF)
- One-Class SVM
- XGBoost (unsupervised)
- Autoencoder

## 데이터셋
- `kddcup99.gz`: 네트워크 침입 탐지 (실제)
- `shuttle_train.txt`: 우주선 센서 데이터 (실제)
- `synthetic_tabular_transactions.csv`: 합성 거래 데이터

## 전처리
- 결측치 처리
- 스케일 정규화 (StandardScaler/RobustScaler)
- 범주형 변수 인코딩
""",
        'numerical/high_dim': """# 고차원 수치 데이터 (High Dimensional)

## 설명
- 특성 수가 매우 많은 데이터 (수십~수천 개)
- 이상치: 특성 공간의 저밀도 영역

## 사용 모델
- Autoencoder (차원 축소 + 이상 탐지)
- Variational Autoencoder (VAE)
- Principal Component Analysis (PCA)
- Isolation Forest (차원 저항성)

## 데이터셋
- `breast_cancer.csv`: 의료 데이터 (실제)
- `synthetic_high_dim.csv`: 합성 고차원 데이터

## 고려사항
- 차원의 저주 (curse of dimensionality)
- 특성 선택/추출 필수
""",
        'categorical/mixed': """# 혼합형 카테고리 데이터 (Mixed Categorical)

## 설명
- 수치형과 범주형 특성이 혼합된 데이터
- 이상치: 비정상적 조합, 연관성 붕괴

## 사용 모델
- One-Hot Encoding + Isolation Forest
- CatBoost (범주형 지원)
- SHAP + Tree-based Models
- Gower Distance + LOF

## 데이터셋
- `categorical_bike_buyers_clean.csv`: 자전거 구매자 (실제)
- `synthetic_mixed_network.csv`: 합성 네트워크 트래픽 데이터

## 전처리
- 범주형 변수 인코딩 (Label/One-Hot)
- 수치형 정규화
- 불균형 처리
"""
    }
    
    for category, content in readme_content.items():
        readme_path = BASE_DIR / category / "README.md"
        ensure_dir(readme_path.parent)
        readme_path.write_text(content)
        print(f"✓ {readme_path}")
    
    # 메인 README
    main_readme = """# Anomaly Detection 데이터셋 저장소

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
"""
    
    main_readme_path = BASE_DIR / "README.md"
    main_readme_path.write_text(main_readme)
    print(f"✓ {main_readme_path}")

def main():
    """메인 실행 함수"""
    print("🚀 Anomaly Detection 데이터셋 설정 시작\n")
    
    # 1. 합성 데이터 생성
    generate_synthetic_data()
    
    # 2. 공개 데이터셋 다운로드 시도
    download_real_datasets()
    
    # 3. README 파일 생성
    create_readme_files()
    
    print("\n" + "="*60)
    print("✅ 완료!")
    print("="*60)
    print(f"\n📂 데이터가 다음 경로에 저장되었습니다:")
    print(f"   {BASE_DIR}")
    print("\n📖 각 폴더의 README.md를 참고하세요.")
    print("🔍 'data/README.md'에서 전체 구조를 확인할 수 있습니다.")

if __name__ == "__main__":
    main()
