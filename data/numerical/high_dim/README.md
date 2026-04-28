# 고차원 수치 데이터 (High Dimensional)

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
