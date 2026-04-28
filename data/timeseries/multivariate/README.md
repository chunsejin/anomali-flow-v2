# 시계열 다변량 데이터 (Multivariate Time Series)

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
