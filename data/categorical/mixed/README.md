# 혼합형 카테고리 데이터 (Mixed Categorical)

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
