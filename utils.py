# utils.py
"""
[유틸리티 및 데이터 처리 담당]
이 파일은 프로그램의 '손과 발' 역할을 하는 함수들을 모아둔 곳입니다.
1. 파일 입출력 (JSON, CSV) 및 데이터 전처리
2. 외부 API 통신 (OpenWeatherMap 날씨)
3. 머신러닝 모델(.pkl) 로드 및 예측 실행
4. 사용자 인터페이스 (CLI 입력/질문)
5. 데이터베이스(PostgreSQL) 연결 및 읽기/쓰기
"""

import json
import csv
import os
import urllib.request
import datetime
import joblib
import psycopg2
import numpy as np
import platform
import re
import time
import undetected_chromedriver as uc

from config import * # 설정 파일 불러오기


# =========================================
# 1. 파일 입출력 (File I/O)
# =========================================

def load_json(path, default=None):
    """JSON 파일을 안전하게 읽어옵니다. 파일이 없으면 기본값 반환."""
    if not os.path.exists(path): return default if default else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default if default else {}


def save_json(path, data):
    """데이터를 JSON 파일로 저장합니다. (한글 깨짐 방지 처리)"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_products_csv(path):
    """
    올리브영 제품 데이터(CSV)를 로드합니다.
    문자열로 저장된 리스트("['tag1', 'tag2']")를 실제 파이썬 리스트로 변환합니다.
    """
    if not os.path.exists(path):
        print(f"[경고] {path} 파일이 없습니다. 빈 리스트를 반환합니다.")
        return []

    products = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 리스트 형태의 문자열 파싱 ("[tag1, tag2]" -> ["tag1", "tag2"])
            for key in ["tags", "featured_ingredients"]:
                val = row.get(key, "[]")
                if val.startswith("["):
                    try:
                        row[key] = json.loads(val)
                    except:
                        row[key] = []
                else:
                    row[key] = [x.strip() for x in val.split(",") if x.strip()]

            # 가격/평점 숫자 변환
            row["price"] = float(row.get("price", 0))
            row["rating"] = float(row.get("rating", 0))
            products.append(row)
    return products


def log_daily_status(result_summary, payload):
    """
    오늘의 피부 상태와 환경 정보를 CSV(weekly_log.csv)에 누적 저장합니다.
    나중에 이 데이터를 모아서 머신러닝 모델을 재학습시킬 수 있습니다.
    """
    is_new = not os.path.exists(LOG_PATH)

    # 로그에 남길 핵심 데이터 추출
    log_data = {
        "date": datetime.date.today().isoformat(),
        "skin_age": result_summary.get("skin_age", 0),
        "uv": payload["env"]["uv"],
        "redness": payload["camera"]["redness"],
        "acne": payload["camera"]["acne"],
        "moisture": payload["camera"]["moisture"],
        "sleep": payload["lifestyle"].get("sleep_hours_7d", 7)
    }

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=log_data.keys())
        if is_new: w.writeheader()
        w.writerow(log_data)


# =========================================
# 2. 외부 API 통신 (Weather)
# =========================================

def get_current_weather(api_key=None):
    """
    OpenWeatherMap API를 통해 현재 날씨 정보를 가져옵니다.
    API 호출 실패 시 프로그램이 멈추지 않도록 기본값(fallback)을 반환합니다.
    """
    # (실제 구현시에는 lat/lon 인자 필요, 여기선 광주 좌표 하드코딩 예시)
    lat, lon = 35.15944, 126.85250

    # 기본값 (API 실패/키 누락 시 사용)
    env = {"uv": 5.0, "humidity": 45, "temperature": 24.0, "source": "fallback"}

    if not api_key: return env  # 키 없으면 바로 기본값

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={api_key}"
        with urllib.request.urlopen(url, timeout=3) as res:
            data = json.load(res)
            env["temperature"] = float(data["main"]["temp"])
            env["humidity"] = int(data["main"]["humidity"])
            env["source"] = "api(weather)"
            # UV는 별도 API 필요하나 예시 단순화를 위해 생략하거나 OpenMeteo 사용 가능
    except:
        print("[Info] 날씨 API 호출 실패, 기본값을 사용합니다.")

    return env


# =========================================
# 3. 머신러닝 (Machine Learning)
# =========================================

def predict_trouble_proba(payload):
    """
    미리 학습된 모델(.pkl)을 로드하여 트러블 발생 확률을 예측합니다.
    주의: 학습할 때 사용한 12개 피처(Feature)의 순서를 정확히 지켜야 합니다.
    """
    if not os.path.exists(MODEL_PATH):
        return {"prob": None, "msg": "데이터가 부족해 아직 예측할 수 없어요."}

    try:
        model = joblib.load(MODEL_PATH)

        # 데이터 준비
        cam = payload["camera"]
        env = payload["env"]
        life = payload["lifestyle"]

        # 모델 학습때 사용한 12개 피처 순서 구성
        # 순서: [홍조, 유분, 수분, 여드름, UV, 습도, 기온, 수면, 물섭취, 세안횟수, 세안온도(Hot?), 민감여부(Yes?)]

        # 1. 피부 지표 (4개)
        f_skin = [
            float(cam.get("redness", 0)),
            float(cam.get("sebum", 0)),
            float(cam.get("moisture", 0)),
            float(cam.get("acne", 0))
        ]

        # 2. 환경 지표 (3개)
        f_env = [
            float(env.get("uv", 0)),
            float(env.get("humidity", 0)),
            float(env.get("temperature", 0))
        ]

        # 3. 생활습관 지표 (5개)
        # wash_temp: hot이면 1.0, 아니면 0.0
        is_hot_wash = 1.0 if str(life.get("wash_temp", "")).lower() == "hot" else 0.0
        # sensitivity: yes이면 1.0, 아니면 0.0
        is_sensitive = 1.0 if str(life.get("sensitivity", "")).lower() == "yes" else 0.0

        f_life = [
            float(life.get("sleep_hours_7d", 7)),
            float(life.get("water_intake_ml", 1500)),
            float(life.get("wash_freq_per_day", 2)),
            is_hot_wash,
            is_sensitive
        ]

        # 전체 합치기 (4 + 3 + 5 = 12개)
        features = np.array([f_skin + f_env + f_life])

        # 예측 실행 (확률값 반환)
        prob = model.predict_proba(features)[0, 1]
        return {"prob": round(prob, 2), "msg": f"트러블 발생 확률: {int(prob * 100)}%"}

    except ValueError as ve:
        return {"prob": None, "msg": f"예측 오류: 입력 데이터 형태가 맞지 않습니다. ({ve})"}
    except Exception as e:
        return {"prob": None, "msg": f"예측 오류: {str(e)}"}


# =========================================
# 4. 사용자 입력 인터페이스 (UI)
# =========================================

def _ask_one(spec, current=None):
    """[내부 함수] 질문 하나를 출력하고 사용자 입력을 받아 형변환합니다."""
    label = spec["label"]
    typ = spec["type"]
    choices = spec.get("choices")

    shown_current = current if current is not None else spec["default"]

    while True:
        prompt = f"- {label}"
        if choices: prompt += f" (선택: {', '.join(choices)})"
        prompt += f" [현재: {shown_current}]: "

        raw = input(prompt).strip()

        # 그냥 엔터 치면 현재값 유지
        if raw == "": return shown_current

        try:
            if typ == "int":
                return int(raw)
            elif typ == "float":
                return float(raw)
            elif typ == "choice":
                val = raw.lower()
                if choices and val not in choices:
                    print(f"   ⚠️ 잘못된 입력입니다. {choices} 중 하나를 입력하세요.")
                    continue
                return val
            return raw
        except:
            print("   ⚠️ 숫자/형식이 올바르지 않습니다.")


def collect_lifestyle_interactive(existing=None):
    """생활습관(수면, 물 섭취 등)을 CLI에서 차례대로 질문합니다."""
    print("\n📝 [생활습관 체크] 값을 입력하세요 (Enter = 기존값 유지)")
    data = dict(existing or {})

    # config.py에 있는 LIFESTYLE_FIELDS 설정을 사용해 반복 질문
    for key, spec in LIFESTYLE_FIELDS.items():
        cur = data.get(key, spec["default"])
        data[key] = _ask_one(spec, current=cur)

    return data


def ask_pref_texture(current="gel"):
    """선호하는 화장품 제형(젤/크림/로션)을 질문합니다."""
    print("\n🧴 [선호 제형 설정]")
    while True:
        raw = input(f"- 선호하는 제형은? (gel/cream/lotion 중 택1) [현재: {current}]: ").strip().lower()
        if raw == "": return current

        # 한글 입력 대응
        if raw in ["젤", "gel"]: return "gel"
        if raw in ["크림", "cream"]: return "cream"
        if raw in ["로션", "lotion"]: return "lotion"

        print("   ⚠️ gel, cream, lotion 중 하나로 입력해주세요.")


# =========================================
# 5. 데이터베이스 (PostgreSQL)
# =========================================

def get_latest_skin_data_from_db():
    """
    PostgreSQL DB('analysis_log' 테이블)에서 가장 최신 분석 데이터를 가져옵니다.
    SkinCareAdvisor가 이해할 수 있는 딕셔너리 형태로 변환해 반환합니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG) # config.py의 설정 사용
        cursor = conn.cursor()

        # 최신 데이터 1건 조회 (ID 역순 정렬)
        cursor.execute("""
            SELECT id, acne, wrinkles, pores, pigmentation, redness, moisture, sebum, created_at 
            FROM analysis_log 
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row: return None

        # DB 데이터를 변수에 매핑
        row_id, acne, wrinkles, pores, pigm, redness, moisture, sebum, created_at = row

        print(f"📅 [DB 로드] ID:{row_id} | 측정일시: {created_at}")

        return {
            "id": row_id,
            "acne": acne,
            "wrinkle": wrinkles,
            "pore": pores,
            "pigmentation": pigm,
            "redness": redness,
            "sebum": sebum,
            "moisture": moisture,
            "tone": 50
        }

    except Exception as e:
        print(f"⚠️ [DB 연결 오류] {e}")
        return None


def save_recommendation_to_db(analysis_id, skin_age, rec_result, routine, trouble_prob):
    """
    Skin Advisor의 최종 처방 결과(피부나이, 추천제품, 루틴 등)를
    PostgreSQL DB('recommendation_log' 테이블)에 저장합니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 테이블이 없으면 생성 (SERIAL = 자동 증가 ID)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_log (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER,  -- analysis_log의 ID와 연결됨
            skin_age REAL,
            top3_products TEXT,
            routine_am TEXT,
            routine_pm TEXT,
            trouble_prob REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 리스트/딕셔너리 형태의 데이터는 JSON 문자열로 변환하여 저장
        products_json = json.dumps(rec_result["top3"], ensure_ascii=False)
        routine_am_json = json.dumps(routine["am"], ensure_ascii=False)
        routine_pm_json = json.dumps(routine["pm"], ensure_ascii=False)

        # 데이터 삽입 (? 대신 %s 사용)
        insert_query = """
        INSERT INTO recommendation_log 
        (analysis_id, skin_age, top3_products, routine_am, routine_pm, trouble_prob)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        data = (analysis_id, skin_age, products_json, routine_am_json, routine_pm_json, trouble_prob)

        cursor.execute(insert_query, data)
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ [DB] 처방 결과가 PostgreSQL에 저장되었습니다.")

    except Exception as e:
        print(f"⚠️ [DB 저장 실패] {e}")


# =========================================
# 6. 스크래핑 헬퍼 (Scraping Helpers)
# =========================================

def clean_price_text(text):
    """가격 문자열(예: '25,000원')에서 숫자만 추출하여 정수로 변환합니다."""
    if not text: return 0
    match = re.search(r'[\d,]+', text)
    if match:
        return int(match.group(0).replace(',', ''))
    return 0


def setup_chrome_driver(headless=False):
    """
    OS(Windows/Linux)를 감지하여 적절한 옵션으로 크롬 드라이버를 반환합니다.
    라즈베리파이(Linux) 환경 대응 로직이 포함되어 있습니다.
    """
    current_os = platform.system()
    print(f"🖥️ 감지된 운영체제: {current_os}")

    options = uc.ChromeOptions()
    driver_path = None

    if current_os == 'Linux':
        options.add_argument("--headless")  # 화면 없음 모드
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # config.py에서 가져오는 것이 좋으나, utils 안에서는 직접 참조하거나 인자로 받아야 함
        # 여기서는 편의상 하드코딩 혹은 config import 필요
        from config import LINUX_DRIVER_PATH
        driver_path = LINUX_DRIVER_PATH

    # headless 인자가 True면 윈도우에서도 백그라운드 실행
    if headless and current_os == 'Windows':
        options.add_argument("--headless")

    try:
        print("🚀 브라우저를 실행합니다...")
        driver = uc.Chrome(options=options, driver_executable_path=driver_path)
        return driver
    except Exception as e:
        print(f"❌ 브라우저 실행 실패: {e}")
        if current_os == 'Linux':
            print("Tip: sudo apt-get install chromium-chromedriver 설치 확인 필요")
        return None


def scroll_to_bottom(driver, count=5, sleep_range=(2, 4)):
    """페이지를 아래로 스크롤합니다."""
    import random
    print("📜 스크롤 시작...")
    for i in range(count):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(*sleep_range))
        print(f"   - 스크롤 {i + 1}/{count} 완료")