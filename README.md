# 🧴 AI 맞춤형 스킨케어 어드바이저 (AI SkinCare Advisor)

## 📖 프로젝트 소개
사용자의 피부 상태를 AI(OpenAI Vision)로 분석하고, 현재 날씨(OpenWeatherMap)와 생활 습관을 고려하여 **최적의 화장품과 스킨케어 루틴을 처방**해주는 스마트 뷰티 솔루션입니다.
라즈베리파이와 카메라를 활용한 온디바이스(On-Device) 환경을 목표로 개발되었습니다.

## ✨ 주요 기능
* **📸 AI 피부 진단:** 카메라로 촬영된 이미지를 분석하여 여드름, 주름, 수분, 유분 등의 상태를 수치화합니다.
* **🌤️ 환경 맞춤 분석:** 현재 위치의 날씨(습도, 자외선, 온도)를 실시간으로 반영합니다.
* **🧴 개인화 처방:** 피부 나이를 예측하고, 사용자에게 꼭 필요한 제품(Top 3)과 아침/저녁 루틴을 추천합니다.
* **📊 데이터 로깅:** 분석 결과와 처방 기록을 PostgreSQL 데이터베이스에 저장하여 트래킹합니다.

## 🛠️ 기술 스택
* **Hardware:** Raspberry Pi 4, Camera Module
* **Language:** Python 3.x
* **AI & API:** OpenAI GPT-4o (Vision), OpenWeatherMap API
* **Database:** PostgreSQL (Docker Container)
* **Libraries:** OpenCV, Pandas, Psycopg2, NumPy

## 🚀 설치 및 실행 방법

### 1. 프로젝트 복제
```bash
git clone [https://github.com/leewb2280/CapstoneDesign.git](https://github.com/leewb2280/CapstoneDesign.git)
cd CapstoneDesign
```

### 2. 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정 (.env)
.env 파일을 같은 폴더안에 생성하고 밑의 코드를 작성합니다.
```bash
# API_KEY
OWM_API_KEY=6c5891515e6280535d63c4fe5e3fd9fb
OPENAI_API_KEY=[sk-proj-...]

# PostgreSQL 접속 정보
DB_HOST=[HOST_IP]
DB_NAME=[DB_NAME] # 일반적으론 postgres 사용
DB_USER=postgres
DB_PASSWORD=[PASSWORD]
DB_PORT=5432
```

## 📂 폴더 구조
```
CapstoneDesign/
├── skin_analyzer.py     # 이미지 분석 모듈
├── skin_advisor.py      # 화장품 및 루틴 추천 모듈
├── engine.py            # 추천 알고리즘 엔진
├── utils.py             # 유틸리티 함수 모음
├── config.py            # 설정 파일
├── .gitignore           # 업로드 거부 파일 목록
├── requirements.txt     # 필요 라이브러리 목록
└── README.md            # 프로젝트 설명서
```
