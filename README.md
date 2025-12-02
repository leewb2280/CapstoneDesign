# 🧴 AI Skin Advisor (캡스톤 디자인)
> 라즈베리파이 설치 및 실행 가이드

이 문서는 라즈베리파이(Raspberry Pi 4 권장) 환경에서 **AI 피부 분석**를 구축하고 실행하는 방법을 설명합니다.

---

## 🛠️ 1. 하드웨어 준비 (Hardware Setup)
다음 부품들이 라즈베리파이에 연결되어 있어야 합니다.
* **Raspberry Pi 4 Model B** (권장)
* **Pi Camera Module** (CSI 인터페이스 연결)
* **피부 센서 (유수분 측정기)** (SPI 인터페이스 연결)
* **터치 디스플레이** (HDMI/DSI 연결)

---

## ⚙️ 2. 라즈베리파이 기본 설정
터미널을 열고 다음 명령어들을 순서대로 입력하세요.

### 2-1. 시스템 업데이트
```bash
sudo apt update
sudo apt upgrade -y
```

### 2-2. 인터페이스 활성화 (SPI & Camera)
피부 센서(SPI)와 카메라 사용을 위해 설정이 필요합니다.

```bash
sudo raspi-config
```

1. Interface Options 선택
2. SPI -> Yes (활성화)
3. Camera (Legacy Camera가 아닌 Libcamera 사용 시 별도 설정 불필요, OS 버전에 따라 다름)
4. Finish 후 재부팅

### 2-3. 필수 시스템 패키지 설치
카메라 제어 및 수치 계산에 필요한 라이브러리를 설치합니다.

```bash
# libcamera (카메라), libatlas (Numpy 가속), PostgreSQL(DB) 설치
sudo apt install -y python3-tk libcamera-apps libopenblas-dev postgresql
```

### 2-4. 하드웨어 접근 권한 설정
파이썬에서 sudo 없이 센서와 카메라를 제어하기 위해 권한을 추가합니다.<br>
(입력 후 재부팅하거나 로그아웃/로그인 해야 적용됩니다.)
```bash
sudo usermod -a -G gpio,video,spi,i2c $USER
```

---

## 🐍 3. 프로젝트 설치 (Software Setup)
### 3-1. 프로젝트 클론 및 이동
```bash
git clone https://github.com/leewb2280/CapstoneDesign.git
cd CapstoneDesign
```

### 3-2. 가상환경 생성 및 라이브러리 설치
시스템 파이썬을 보호하기 위해 가상환경을 사용합니다.
```bash
# 가상환경 생성
python3 -m venv venv --system-site-packages

# 가상환경 활성화
source venv/bin/activate

# 필수 라이브러리 설치 (requirements.txt 이용)
pip install -r requirements.txt
```

---

## 🗄️ 4. 데이터베이스(PostgreSQL) 설정
### 4-1. DB 접속 및 유저 생성
라즈베리파이 로컬에 DB를 구축합니다.
```bash
sudo -u postgres psql
```
PostgreSQL 프롬프트(postgres=#)가 나오면 아래 명령어를 한 줄씩 입력하세요.

```sql
-- 비밀번호는 .env 설정과 동일하게 'password'로 설정 (보안상 변경 가능)
ALTER USER postgres PASSWORD 'password';

-- 데이터베이스가 없다면 생성 (기본 postgres DB 사용 시 생략 가능)
-- CREATE DATABASE postgres;

-- 종료
\q
```

---

## 🔑 5. 환경 변수 설정 (.env)
프로젝트 폴더 안에 .env 파일을 생성하고 API 키를 입력합니다.
```bash
nano .env
```

.env 파일 내용
```Ini, TOML
# Database (라즈베리파이 로컬)
DB_HOST=localhost
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=password
DB_PORT=5432

# API Keys
NAVER_CLIENT_ID=your_naver_id
NAVER_CLIENT_SECRET=your_naver_secret
OPENAI_API_KEY=your_openai_key
OWM_API_KEY=your_weather_key
```
입력 후 Ctrl+O (저장), Enter, Ctrl+X (종료).

---

## 🚀 6. 서버 실행 (Manual Run)
```bash
# 가상환경이 켜진 상태에서 실행
python main.py
```
서버가 정상 실행되면 밑의 주소에서 접속 가능합니다.

내부:<br>
테스트 사이트: http://localhost:8000<br>
코드 확인 사이트: http://localhost:8000/docs

외부:<br>
테스트 사이트: http://IP_입력:8000 <br>
코드 확인 사이트: http://IP_입력:8000/docs

이후 원활한 작동을 위해 데이터 수집을 먼저 해주십시오.