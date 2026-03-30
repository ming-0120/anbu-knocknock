## 👵 안부 똑똑 (Care-Guard System)
<img width="480" height="262" alt="image" src="https://github.com/user-attachments/assets/34f2997d-8d27-4c96-b2cb-4931ba1dcf06" />

---
# 📋 프로젝트 개요

- **프로젝트명:** 안부똑똑 (Anbu-Knock Knock) - 센서 데이터 기반의 고독사 방지 시스템
- **개발 기간**: 2026.02.19 ~ 2026.03.25
- **목표:** 저비용 센서와 AI 알고리즘을 활용해 개인별 '생활 패턴의 변화'를 감지하는 맞춤형 돌봄 시스템 구축과 사회적 문제 중 하나인 고독사를 해결. →  문제 인식 → 차별화/방법 모색 이런 과정

## **💼 서비스 기획 배경**

- 1인 가구 및 고령 인구 증가로 인해 **고독사 문제가 지속적으로 증가**
- 기존 시스템은 ‘24시간 미활동’ 등 단순 기준으로 판단하여 **개인별 생활 패턴을 반영하지 못함**
- 카메라·음성 기반 방식은 **사생활 침해 이슈로 실사용에 한계 존재**
- 실제 생활에서는 외출, 배달, 수면 등 다양한 변수로 인해 **단순 활동 여부만으로 이상 판단이 어려움**

→  따라서 개인의 평소 패턴을 기반으로 **“변화”를 감지하는 AI 기반 접근 필요**

---

## **🔧** 기술 스택 (Tech Stack)

- **Hardware:** ESP32 DevKit V1, HC-SR501(PIR), MC-38(문 열림 센서)
- **Language:** C++ (Arduino IDE), Python 3.10+
- **Backend:** **FastAPI** (AI 라이브러리 연동 및 비동기 처리 최적화)
- **Frontend:** React (Tailwind CSS, Recharts 활용)
- **Database:** MySQL
- **AI/ML:** **Scikit-learn (Isolation Forest)**, Pandas (데이터 전처리)

---

# **💡 주요 기능 및 담당 역할**

## **📌 주요 기능**

- 센서 기반 생활 데이터 수집 (움직임, 문 열림 등) 및 실시간 전송
- 시간 단위로 데이터를 집계하여 개인별 생활 패턴 Feature 생성
- Isolation Forest 기반 **개인 맞춤형 이상 탐지 모델 적용**
- 이상 점수를 기반으로 위험도 Score 산출 및 단계별 등급 분류 (normal / watch / alert / emergency)
- Redis를 활용한 실시간 데이터 처리 및 빠른 상태 반영
- 운영자 대시보드에서 거주자 상태 모니터링 및 위험 상황 확인
- 이상 상황 발생 시 알림 및 대응 프로세스 지원 (작업 할당 / 상태 관리)
- STT + LLM 기반 통화 내용 요약 기능으로 대응 이력 관리

## **👩🏻‍💻 담당 역할**

- FastAPI 기반 **백엔드 아키텍처 전체 설계 및 구현**
- 센서 이벤트 → Feature 변환 → 모델 → Detector 흐름 설계
- Isolation Forest 기반 **개인별 이상 탐지 모델 구축 및 학습**
- decision_function 기반 이상 점수를 **Risk Score로 변환하는 로직 설계**
- Redis를 활용한 **실시간 데이터 집계 및 캐싱 처리 구현**
- 대시보드용 API 및 고위험 사용자 조회 로직 개발
- 모델 평가(Precision, Recall, F1) 및 Threshold 튜닝을 통한 성능 개선
- 서버 운영 중 발생한 데이터 오류 및 성능 이슈 분석 및 해결

## 📢 시스템 아키텍처 및 프로젝트 구조

## **🏗️ 아키텍처 특징**

- 센서 → 서버 → AI 모델 → 대시보드로 이어지는 **End-to-End 데이터 파이프라인 구조**
- ESP32 기반 센서에서 수집된 데이터를 실시간으로 FastAPI 서버로 전송하는 **경량 IoT 구조**
- Isolation Forest 기반 개인별 모델을 적용한 **Per-Resident 이상 탐지 구조**
- Redis 및 배치 처리를 활용한 **실시간 처리 + 주기적 분석 혼합 구조**
- React 대시보드를 통한 위험도 시각화 및 운영자 대응을 지원하는 **모니터링 중심 아키텍처**

### 📂 프로젝트 구조

```
care-guard-system/
├── hardware/           # [C++] ESP32 센서 제어 및 WiFi 데이터 전송
├── backend/            # [Python] FastAPI 서버, DB, AI 모델
│   ├── app/
│   │   ├── ml/         # Isolation Forest 기반 이상 탐지 로직
│   │   └── main.py     # API 엔드포인트 (Data 수집 및 결과 반환)
├── frontend/           # [React] 실시간 상태 대시보드 및 시각화
└── docs/               # 회로도 및 기획서 관리
```

---

# 🛠️ 문제 해결 및 트러블슈팅 경험

---

## **✅ 모델 성능 저하 문제 (Threshold 설계 문제)**

### **🧨 문제 상황**

- 동일한 모델임에도 평가 방식에 따라 F1 점수가 크게 변동

**🔍 원인 분석 및 해결 방법**

- 고정 cutoff(watch/alert 기준) 사용으로 recall이 낮아짐
- 실제 데이터 분포와 정책 기준이 불일치
    
    → 데이터 기반 threshold 탐색 방식으로 변경
    
    → precision/recall/F1을 직접 계산하여 최적 threshold 선정
    

**‼️ 핵심 코드**

```python
precision = tp / (tp + fp)
recall = tp / (tp + fn)

f1 = 2 * precision * recall / (precision + recall)
```

**📈 결과**

- F1: 0.5312 → 0.7179로 개선
- 미탐 감소 및 위험 탐지율 향상

---

## **✅ 실시간 데이터 반영 지연 문제 (Redis 도입)**

### **🧨 문제 상황**

- 센서 데이터가 대시보드에 즉시 반영되지 않음
- 일정 시간 지연 후 상태가 업데이트됨

### **🔍 원인 분석 및 해결 방법**

- DB 기반 조회 구조로 인해 쓰기/조회 지연 발생
- 실시간 처리가 아닌 배치 성격으로 동작

→ Redis 기반 버킷 구조 도입

→ 메모리 캐시를 활용하여 실시간 데이터 처리 구조로 개선

### **‼️ 핵심 코드**

```python
bucket=datetime.now().strftime("%Y%m%d%H%M")
key=f"sensor:{resident_id}:{bucket}"

redis.setex(key,60,value)
```

### **📈 결과**

- 데이터 반영 지연 → 실시간 수준으로 개선
- 대시보드 응답 속도 및 사용자 경험 향상

---

## **✅ Feature 값 분포 왜곡 문제 (log1p 적용)**

### **🧨 문제 상황**

- 활동 간격(feature)의 값 범위가 매우 커 모델 학습이 불안정
- 일부 큰 값이 전체 모델에 과도한 영향

### **🔍 원인 분석 및 해결 방법**

- 데이터 스케일 불균형으로 인해 특정 feature가 모델을 지배

→ log1p 변환 적용으로 값의 분포를 완만하게 조정

→ 극단값 영향을 줄이고 안정적인 학습 환경 구성

### **‼️ 핵심 코드**

```python
import numpy as np

df["x3_avg_interval"]=np.log1p(df["x3_avg_interval"])
```

### **📈 결과**

- 데이터 분포 안정화
- 모델 학습 안정성 및 이상 탐지 정확도 향상

---

# **🤔 회고**

- 이상 탐지는 모델보다 **데이터와 기준(Threshold 설계)이 더 중요함**을 체감
- 동일 모델이라도 평가 기준에 따라 성능이 크게 달라질 수 있음을 경험
- 실시간 서비스에서는 모델뿐 아니라 **데이터 처리 구조(캐싱, 배치, 흐름 설계)**가 핵심이라는 것을 이해
- 센서 데이터 특성상 노이즈와 결측이 많아 **Feature 설계의 중요성**을 깊이 느낀 경험
- 다음 단계로는 **모델 고도화(딥러닝), 개인화 기준 자동화, 시스템 확장성 개선**을 적용해보고 싶음

---

## **🤳 화면**
---
### **안부똑똑 발표 영상**
[![안부똑똑_발표영상](http://img.youtube.com/vi/P70DXkj3qCc/0.jpg)](https://youtu.be/596cN8_jkiM?si=9c_wA1_xwOUGBqoo)

<img width="1676" height="967" alt="스크린샷 2026-03-28 오후 3 31 20" src="https://github.com/user-attachments/assets/321829ca-37bd-4133-a6d4-4c020fc7a26a" />
<img width="1575" height="847" alt="스크린샷 2026-03-28 오후 3 37 49" src="https://github.com/user-attachments/assets/20fc977e-ea3f-4071-bd7e-5494b69f4f49" />
<img width="479" height="854" alt="스크린샷 2026-03-28 오후 3 40 17" src="https://github.com/user-attachments/assets/0d5ffced-e13a-4c7c-9d07-65145e11a3ef" />


