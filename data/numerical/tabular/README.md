# 수치형 테이블 데이터 (Tabular Numerical)

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
