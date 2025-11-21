# 🧴 AI 맞춤형 스킨케어 어드바이저 (AI SkinCare Advisor)

## 📖 프로젝트 소개
사용자의 피부 상태를 **AI(OpenAI Vision)**로 정밀 분석하고, 현재 위치의 **날씨(OpenWeatherMap)**와 사용자의 생활 습관을 종합적으로 
고려하여 최적의 화장품과 스킨케어 루틴을 처방해주는 스마트 뷰티 솔루션입니다. 
라즈베리파이(Raspberry Pi) 기반의 온디바이스(On-Device) 환경에서 작동하도록 설계되었습니다.

## ✨ 주요 기능
* **📸 AI 피부 진단:** 카메라로 촬영된 이미지를 분석하여 여드름, 주름, 모공, 색소 침착 등의 상태를 수치화합니다.
* **🌤️ 환경 맞춤 분석:** 피부 나이를 예측하고, 올리브영 베스트 상품 데이터를 기반으로 사용자에게 꼭 필요한 제품(Top 3)과 아침/저녁 루틴을 추천합니다.
* **🧴 개인화 처방:** 피부 나이를 예측하고, 사용자에게 꼭 필요한 제품(Top 3)과 아침/저녁 루틴을 추천합니다.
* **📊 데이터 로깅:** 분석 결과와 처방 기록을 PostgreSQL 데이터베이스에 저장하여 피부 변화를 트래킹합니다.
* **🕷️ 데이터 자동 수집:** 셀레니움(Selenium)을 이용해 최신 스킨케어 제품 정보를 주기적으로 업데이트합니다.

## 🛠️ 기술 스택
* **Hardware:** Raspberry Pi 4, Camera Module
* **Language:** Python 3.x
* **AI & API:** OpenAI GPT-4o (Vision), OpenWeatherMap API
* **Database:** PostgreSQL (Local or Docker)
* **Libraries:** Selenium, Pandas, Psycopg2, NumPy, Requests

## 🚀 Raspberry Pi 에서의 설치 및 실행 방법

### 1. 기본 업데이트 (필수)
패키지 목록을 최신으로 갱신합니다.
```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. 시스템 패키지 설치
Python 라이브러리 구동에 필요한 시스템 패키지를 설치합니다.
```bash
# Numpy, DB, 크롬 드라이버 등 필수 패키지 일괄 설치
sudo apt-get install -y libatlas-base-dev libpq-dev postgresql chromium-browser chromium-chromedriver
```

### 3. 프로젝트 복제 및 설정
```bash
git clone https://github.com/leewb2280/CapstoneDesign.git
cd CapstoneDesign

# Python 라이브러리 설치
pip install -r requirements.txt
```

### 4. 환경변수 설정 (.env)
프로젝트 루트 경로에 .env 파일을 생성하고 아래 내용을 작성합니다.
```Ini, TOML
# API_KEY
# OpenWeatherMap API Key
OWM_API_KEY=your_openweathermap_api_key_here

# OpenAI API Key
OPENAI_API_KEY=sk-proj-your_openai_api_key_here

# PostgreSQL DB 접속 정보
DB_HOST=localhost
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_PORT=5432
```

## 🏃‍♂️ 실행 방법
추후 내용 채우기

## 📂 최종 폴더 구조
```Plaintext
CapstoneDesign/
├── skin_analyzer.py     # [모듈] OpenAI API 활용 피부 이미지 분석
├── skin_advisor.py      # [메인] 프로그램 실행 파일 (전체 흐름 제어)
├── advisor_core.py      # [핵심] 피부 나이 계산 및 제품 추천 알고리즘 (구 engine.py)
├── skincare_Scraper.py  # [도구] 올리브영 제품 정보 크롤러
├── utils.py             # [도구] DB연결, 파일입출력 등 공통 함수 모음
├── config.py            # [설정] API 키, 파일 경로, 가중치 등 전역 설정
├── .env                 # [보안] API Key 및 DB 비밀번호 저장 (Git 업로드 X)
├── requirements.txt     # [설정] 필요 라이브러리 목록
└── README.md            # 프로젝트 설명서
```
