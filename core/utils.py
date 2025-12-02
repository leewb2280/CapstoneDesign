# utils.py
"""
[유틸리티 및 데이터 처리 담당]
API 서버, 머신러닝 모델, 데이터베이스 간의 연결을 담당하는 핵심 모듈입니다.

기능 목록:
1. Weather API: 현재 날씨 정보 조회
2. ML Prediction: 트러블 예측 모델 실행
3. Database: 제품 조회, 피부 데이터 조회, 추천 결과 저장
"""

import json
import urllib.request
import logging

import joblib
import psycopg2
import numpy as np

# 설정 파일 로드 (DB 접속 정보, 모델 경로 등)
from services.config import *

from services.filters import get_filter_query
1
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. 외부 API 통신 (Weather)
# ==============================================================================

def get_current_weather(api_key: str = None) -> dict:
    """
    날씨 정보를 가져옵니다. (이중화 로직 적용)
    1순위: OpenWeatherMap (API Key 필요, 정확도 높음)
    2순위: Open-Meteo (API Key 불필요, 백업용)
    3순위: 기본값 (모두 실패 시)

    Args:
        api_key (str): OWM API Key

    Returns:
        dict: {'uv': float, 'humidity': int, 'temperature': float, 'source': str}
    """
    # 위치 설정 (광주광역시 좌표)
    lat, lon = 35.15944, 126.85250

    # 3순위: 최후의 보루 (기본값)
    fallback_env = {
        "uv": 5.0,
        "humidity": 45,
        "temperature": 24.0,
        "source": "fallback"
    }

    # ---------------------------------------------------------
    # 1순위: OpenWeatherMap
    # ---------------------------------------------------------
    if api_key:
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={api_key}"
            with urllib.request.urlopen(url, timeout=3) as res:
                data = json.load(res)

                # OWM은 무료 버전에서 UV를 제공하지 않는 경우가 많아 기본값 5.0 사용
                return {
                    "temperature": float(data["main"]["temp"]),
                    "humidity": int(data["main"]["humidity"]),
                    "uv": 5.0,
                    "source": "api(OpenWeatherMap)"
                }
        except Exception as e:
            logger.warning(f"⚠️ OpenWeatherMap 호출 실패 ({e}), 백업 API를 시도합니다.")

    # ---------------------------------------------------------
    # 2순위: Open-Meteo
    # ---------------------------------------------------------
    try:
        # Open-Meteo는 키가 필요 없고 UV, 습도, 기온을 한 번에 줍니다.
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,uv_index"
        )

        with urllib.request.urlopen(url, timeout=3) as res:
            data = json.load(res)
            current = data.get("current", {})

            return {
                "temperature": float(current.get("temperature_2m", 24.0)),
                "humidity": int(current.get("relative_humidity_2m", 45)),
                "uv": float(current.get("uv_index", 5.0)),
                "source": "api(Open-Meteo)"
            }

    except Exception as e:
        logger.error(f"❌ Open-Meteo 호출 실패 ({e}), 기본값을 사용합니다.")

    # 모든 API 실패 시 기본값 반환
    return fallback_env

# ==============================================================================
# 2. 머신러닝 (Machine Learning)
# ==============================================================================

def predict_trouble_proba(payload: dict) -> dict:
    """
    학습된 모델(.pkl)을 사용하여 피부 트러블 발생 확률을 예측합니다.
    * 팀원 코드(final_skin.py)의 Temperature Scaling(T=1.8) 로직을 이식하여
      과도한 확신(Overconfidence)을 보정했습니다.
    """
    if not os.path.exists(MODEL_PATH):
        # 모델이 없을 때는 안전하게 0% 처리
        return {"prob": 0.0, "msg": "AI 모델 파일이 없어 예측을 건너뜁니다."}

    try:
        model = joblib.load(MODEL_PATH)

        # 1. 데이터 추출
        cam = payload["camera"]
        env = payload["env"]
        life = payload["lifestyle"]

        # 2. Feature Vector 생성 (학습 순서: Skin -> Env -> Life)

        # (1) 피부 데이터
        f_skin = [
            float(cam.get("redness", 0)),
            float(cam.get("sebum", 0)),
            float(cam.get("moisture", 0)),
            float(cam.get("acne", 0))
        ]

        # (2) 환경 데이터
        f_env = [
            float(env.get("uv", 0)),
            float(env.get("humidity", 0)),
            float(env.get("temperature", 0))
        ]

        # (3) 생활습관 데이터
        is_hot_wash = 1.0 if str(life.get("wash_temp", "")).lower() == "hot" else 0.0
        is_sensitive = 1.0 if str(life.get("sensitivity", "")).lower() == "yes" else 0.0

        f_life = [
            float(life.get("sleep_hours_7d", 7)),
            float(life.get("water_intake_ml", 1500)),
            float(life.get("wash_freq_per_day", 2)),
            is_hot_wash,
            is_sensitive
        ]

        # 3. 최종 입력 배열 생성 (2D Array)
        features = np.array([f_skin + f_env + f_life])

        # 4. 예측 실행 및 보정 (Temperature Scaling)
        # (1) Raw Probability 추출 (Class 1이 트러블 발생일 확률)
        prob_raw = model.predict_proba(features)[0, 1]

        # (2) 수치 안정성 처리 (log(0) 방지)
        prob_safe = np.clip(prob_raw, 1e-4, 1 - 1e-4)

        # (3) 온도 보정 적용 (T=1.8)
        T = 1.8
        logit = np.log(prob_safe / (1.0 - prob_safe))
        logit_T = logit / T
        final_prob = 1.0 / (1.0 + np.exp(-logit_T))

        # 5. 결과 메시지 생성
        final_prob = float(final_prob)  # numpy float -> native float
        percent = int(final_prob * 100)

        if final_prob < 0.3:
            msg = f"트러블 위험 낮음 ({percent}%) - 현재 상태 유지"
        elif final_prob < 0.6:
            msg = f"트러블 위험 보통 ({percent}%) - 수분/진정 관리 권장"
        else:
            msg = f"트러블 위험 높음 ({percent}%) - 자극을 줄이는 루틴 필요"

        return {
            "prob": round(final_prob, 2),
            "msg": msg
        }

    except Exception as e:
        logger.error(f"ML 예측 오류: {e}")
        # 에러 발생 시 멈추지 않고 확률 없음으로 반환
        return {"prob": 0.0, "msg": "예측 중 오류가 발생했습니다."}


# ==============================================================================
# 3. 데이터베이스 (PostgreSQL)
# ==============================================================================

def init_db():
    """
    [DB 초기화 통합 함수]
    서버 시작 시 CSV 파일 구조에 맞춰 모든 테이블을 안전하게 생성합니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # ---------------------------------------------------------
        # 1. users (사용자)
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(50) PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ---------------------------------------------------------
        # 2. user_profiles (사용자 상세 정보)
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id VARCHAR(50) PRIMARY KEY,
                age INTEGER,
                sleep_hours_7d REAL,
                water_intake_ml INTEGER,
                wash_freq_per_day INTEGER,
                wash_temp TEXT,
                sensitivity TEXT,
                pref_texture TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)

        # ---------------------------------------------------------
        # 3. products (제품 정보)
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER,
                brand TEXT,            -- 브랜드 없는 경우 대비 (NULL 허용)
                official_category TEXT,
                tags TEXT,
                featured_ingredients TEXT,
                url TEXT,
                image_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- CSV 호환용 추가
            );
        """)

        # ---------------------------------------------------------
        # 4. analysis_log (피부 분석 기록)
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_log (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50),
                acne INTEGER,
                wrinkles INTEGER,
                pores INTEGER,
                pigmentation INTEGER,
                redness INTEGER,
                moisture INTEGER,
                sebum INTEGER,
                image_path TEXT,
                total_score INTEGER,   -- 종합 점수 (NULL 허용)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ---------------------------------------------------------
        # 5. recommendation_log (추천 기록)
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_log (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50),
                analysis_id INTEGER,
                skin_age REAL,
                top3_products TEXT,
                routine_am TEXT,
                routine_pm TEXT,
                trouble_prob REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ---------------------------------------------------------
        # 6. training_log (AI 학습용 데이터)
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_log (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                redness REAL, sebum REAL, moisture REAL, acne REAL,
                uv REAL, humidity REAL, temperature REAL,
                sleep_hours REAL, water_intake INTEGER,
                wash_freq REAL, is_hot_wash INTEGER, is_sensitive INTEGER
            );
        """)

        conn.commit()
        cursor.close()
        conn.close()
        logger.info("✅ 모든 DB 테이블이 CSV 구조에 맞춰 정상적으로 초기화되었습니다.")

    except Exception as e:
        logger.error(f"❌ DB 초기화 중 오류 발생: {e}")

def load_products_from_db() -> list:
    """
    DB의 'products' 테이블에서 모든 제품 정보를 가져옵니다.
    (JSON 형태의 태그/성분 데이터를 파이썬 리스트로 변환하여 반환)
    """
    products = []
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
            SELECT name, price, brand, official_category, tags, featured_ingredients, url, image_url 
            FROM products
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if not rows:
            logger.warning("⚠️ [DB] 제품 데이터가 비어있습니다. data_collector.py를 실행하세요.")
            return []

        for row in rows:
            name, price, brand, category, tags_raw, ings_raw, url, img = row

            # JSON 문자열 -> 파이썬 리스트 변환 (안전장치 포함)
            tags_list = json.loads(tags_raw) if tags_raw else []
            ings_list = json.loads(ings_raw) if ings_raw else []

            products.append({
                "name": name,
                "price": price,
                "brand": brand,
                "official_category": category,
                "tags": tags_list,
                "featured_ingredients": ings_list,
                "url": url,
                "image_url": img
            })

        logger.info(f"📂 [DB] {len(products)}개의 제품 로드 완료")
        return products

    except Exception as e:
        logger.error(f"❌ [DB 로드 실패] {e}")
        return []


def get_skin_data_by_id(analysis_id: int) -> dict:
    """
    특정 분석 ID(analysis_id)에 해당하는 피부 데이터를 DB에서 조회합니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
            SELECT id, acne, wrinkles, pores, pigmentation, redness, moisture, sebum, created_at 
            FROM analysis_log 
            WHERE id = %s
        """
        cursor.execute(query, (analysis_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row:
            return None

        row_id, acne, wrinkles, pores, pigmentation, redness, moisture, sebum, created_at = row

        # 분석 로직에서 사용하기 편한 Dictionary 형태로 반환
        return {
            "id": row_id,
            "acne": acne,
            "wrinkle": wrinkles,
            "pore": pores,
            "pigmentation": pigmentation,
            "redness": redness,
            "sebum": sebum,
            "moisture": moisture,
            "tone": 50  # 톤 데이터는 현재 더미값
        }

    except Exception as e:
        logger.error(f"⚠️ [DB 연결 오류] {e}")
        return None


def save_recommendation_to_db(user_id: str, analysis_id: int, skin_age: float,
                              rec_result: dict, routine: dict, trouble_prob: float):
    """
    최종 추천 결과(제품, 루틴, 예측확률)를 DB에 저장합니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 복잡한 데이터 구조(List/Dict)는 JSON 문자열로 변환하여 저장
        products_json = json.dumps(rec_result["top3"], ensure_ascii=False)
        routine_am_json = json.dumps(routine["am"], ensure_ascii=False)
        routine_pm_json = json.dumps(routine["pm"], ensure_ascii=False)

        insert_query = """
            INSERT INTO recommendation_log 
            (user_id, analysis_id, skin_age, top3_products, routine_am, routine_pm, trouble_prob)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        data = (
            user_id,
            analysis_id,
            skin_age,
            products_json,
            routine_am_json,
            routine_pm_json,
            trouble_prob
        )

        cursor.execute(insert_query, data)
        conn.commit()

        cursor.close()
        conn.close()

        logger.info(f"✅ [DB] 추천 결과 저장 완료 (User: {user_id})")

    except Exception as e:
        logger.error(f"⚠️ [DB 저장 실패] {e}")


# ==============================================================================
# 4. 사용자 관리 및 기록 조회 (User & History)
# ==============================================================================


# 프로필 저장/업데이트 (Upsert)
def save_user_profile_db(user_id, data: dict):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 이미 있으면 업데이트, 없으면 삽입 (ON CONFLICT 구문 사용)
        query = """
            INSERT INTO user_profiles 
            (user_id, age, sleep_hours_7d, water_intake_ml, wash_freq_per_day, sensitivity, pref_texture, wash_temp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET
                age = EXCLUDED.age,
                sleep_hours_7d = EXCLUDED.sleep_hours_7d,
                water_intake_ml = EXCLUDED.water_intake_ml,
                wash_freq_per_day = EXCLUDED.wash_freq_per_day,
                sensitivity = EXCLUDED.sensitivity,
                pref_texture = EXCLUDED.pref_texture,
                wash_temp = EXCLUDED.wash_temp,
                updated_at = CURRENT_TIMESTAMP;
        """
        cursor.execute(query, (
            user_id,
            data.get('age'),
            data.get('sleep_hours_7d'),
            data.get('water_intake_ml'),
            data.get('wash_freq_per_day'),
            data.get('sensitivity'),
            data.get('pref_texture'),
            data.get('wash_temp', 'warm')
        ))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"프로필 저장 실패: {e}")
        return False


# 프로필 조회
def get_user_profile_db(user_id):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
            SELECT age, sleep_hours_7d, water_intake_ml, wash_freq_per_day, sensitivity, pref_texture, wash_temp
            FROM user_profiles
            WHERE user_id = %s
        """
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            # 딕셔너리로 변환하여 반환
            return {
                "age": row[0],
                "sleep_hours_7d": row[1],
                "water_intake_ml": row[2],
                "wash_freq_per_day": row[3],
                "sensitivity": row[4],
                "pref_texture": row[5],
                "wash_temp": row[6]
            }
        return None  # 프로필 없음
    except Exception as e:
        logger.error(f"프로필 조회 실패: {e}")
        return None


def register_user_db(user_id, password, name):
    """회원가입: DB에 사용자 추가"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 이미 있는지 확인
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if cursor.fetchone():
            return False  # 이미 존재함

        cursor.execute("INSERT INTO users (user_id, password, name) VALUES (%s, %s, %s)",
                       (user_id, password, name))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"회원가입 실패: {e}")
        return False


def authenticate_user_db(user_id, password):
    """로그인: 아이디/비번 일치 확인"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT password, name FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row and row[0] == password:  # 비밀번호 일치 (실무에선 해시 암호화 필수)
            return {"user_id": user_id, "name": row[1]}
        return None
    except Exception as e:
        logger.error(f"로그인 검사 실패: {e}")
        return None


def check_user_exists_db(user_id):
    """아이디가 DB에 진짜 존재하는지 확인"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
        exists = cursor.fetchone()
        cursor.close()
        conn.close()
        return True if exists else False
    except:
        return False


def search_skin_history_db(
        user_id: str,
        condition: str = None,
        start_date: str = None,
        end_date: str = None,
        page: int = 1,
        page_size: int = 50
):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 기본 쿼리
        base_query = """
                    FROM analysis_log a
                    LEFT JOIN recommendation_log r ON a.id = r.analysis_id
                    WHERE a.user_id = %s
                """
        params = [user_id]

        # 2. 필터 적용 (기존과 동일)
        if condition:
            filter_result = get_filter_query(condition)
            if filter_result:
                sql_part, val = filter_result
                base_query += f" {sql_part}"
                if val is not None:
                    params.append(val)

        if start_date:
            base_query += " AND a.created_at >= %s"
            params.append(start_date)

        if end_date:
            base_query += " AND a.created_at <= %s"
            params.append(end_date + " 23:59:59")

        # 4. 개수 세기
        count_sql = f"SELECT COUNT(*) {base_query}"
        cursor.execute(count_sql, tuple(params))
        total_count = cursor.fetchone()[0]

        # 5. 데이터 조회 (⭐️ 수정됨: 추천 정보 컬럼 추가!)
        offset = (page - 1) * page_size
        data_sql = f"""
                    SELECT 
                        a.id, a.created_at, 
                        a.moisture, a.sebum, a.redness, a.pores, a.wrinkles, a.acne, a.pigmentation,
                        a.image_path, 
                        r.skin_age,
                        r.top3_products, r.routine_am, r.routine_pm
                    {base_query}
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s
                """
        full_params = params + [page_size, offset]

        cursor.execute(data_sql, tuple(full_params))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        records = []
        for r in rows:
            # 인덱스: 0~8(점수), 9(이미지), 10(나이), 11(제품), 12(아침), 13(저녁)

            # DB에 JSON 문자열로 저장된 것을 파이썬 객체(List/Dict)로 복원
            top3_raw = r[11]
            routine_am_raw = r[12]
            routine_pm_raw = r[13]

            top3 = json.loads(top3_raw) if top3_raw else []
            routine_am = json.loads(routine_am_raw) if routine_am_raw else []
            routine_pm = json.loads(routine_pm_raw) if routine_pm_raw else []

            # 점수 계산
            moisture = r[2] or 0
            sebum = r[3] or 0
            redness = r[4] or 0
            pore = r[5] or 0
            wrinkles = r[6] or 0
            acne = r[7] or 0
            pigmentation = r[8] or 0

            negative_sum = acne + wrinkles + pore + redness + pigmentation
            overall_score = max(0, 100 - int(negative_sum / 5))

            records.append({
                "id": r[0],
                "date": r[1].strftime("%Y-%m-%d %H:%M"),
                "image_path": r[9],
                "skin_age": r[10] if r[10] else 0,
                "overall_score": overall_score,

                # 앱으로 보낼 추가 정보
                "products": top3,
                "routine": {
                    "am": routine_am,
                    "pm": routine_pm
                },

                "scores": {
                    "moisture": moisture, "sebum": sebum,
                    "redness": redness, "pore": pore,
                    "wrinkles": wrinkles, "acne": acne,
                    "pigmentation": pigmentation
                }
            })

        import math
        return {
            "total_count": total_count,
            "total_pages": math.ceil(total_count / page_size),
            "current_page": page,
            "records": records
        }

    except Exception as e:
        logger.error(f"히스토리 조회 실패: {e}")
        return {"total_count": 0, "records": []}


def get_skin_period_stats_db(user_id: str, start_date: str, end_date: str):
    """
    특정 기간 동안의 피부 상태 통계(평균 점수, 측정 횟수 등)를 계산하여 반환합니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 평균 점수 계산 (AVG 함수 사용)
        # COALESCE(AVG(...), 0): 데이터가 없어서 NULL이 나오면 0으로 바꿔줌
        stat_query = """
            SELECT 
                COUNT(*),
                COALESCE(AVG(moisture), 0),
                COALESCE(AVG(sebum), 0),
                COALESCE(AVG(redness), 0),
                COALESCE(AVG(pores), 0),
                COALESCE(AVG(wrinkles), 0),
                COALESCE(AVG(acne), 0)
            FROM analysis_log
            WHERE user_id = %s 
              AND created_at >= %s 
              AND created_at <= %s
        """

        # 날짜 포맷 맞추기 (시작일 00:00 ~ 종료일 23:59)
        s_date = start_date
        e_date = end_date + " 23:59:59"

        cursor.execute(stat_query, (user_id, s_date, e_date))
        row = cursor.fetchone()

        # 2. 피부 나이 평균 계산 (recommendation_log 테이블 조회)
        age_query = """
            SELECT COALESCE(AVG(skin_age), 0)
            FROM recommendation_log
            WHERE user_id = %s 
              AND created_at >= %s 
              AND created_at <= %s
        """
        cursor.execute(age_query, (user_id, s_date, e_date))
        avg_age = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        # 데이터가 하나도 없으면 0 리턴
        count = row[0]
        if count == 0:
            return None

        # 소수점 1자리까지 반올림하여 리턴
        return {
            "total_count": count,
            "avg_moisture": round(row[1], 1),
            "avg_sebum": round(row[2], 1),
            "avg_redness": round(row[3], 1),
            "avg_pore": round(row[4], 1),
            "avg_wrinkle": round(row[5], 1),
            "avg_acne": round(row[6], 1),
            "avg_skin_age": round(avg_age, 1)
        }

    except Exception as e:
        logger.error(f"통계 계산 실패: {e}")
        return None


def save_analysis_log_db(user_id, file_path, scores, total_score=0): # 👈 total_score 인자 추가
    """
    [DB 저장 전담] 분석 결과와 이미지 경로, 그리고 '종합 점수'를 DB에 저장합니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 쿼리에 total_score 컬럼 추가
        insert_sql = """
            INSERT INTO analysis_log 
            (user_id, image_path, moisture, sebum, redness, pores, wrinkles, acne, pigmentation, total_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        # 딕셔너리에서 값 추출
        params = (
            user_id, file_path,
            scores['moisture'], scores['sebum'], scores['redness'],
            scores['pores'], scores['wrinkles'], scores['acne'], scores['pigmentation'],
            total_score
        )

        cursor.execute(insert_sql, params)
        new_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()
        return new_id

    except Exception as e:
        logger.error(f"DB 저장 실패: {e}")
        return None


# ==============================================================================
# 5. AI 모델 학습 (Training)
# ==============================================================================

def save_training_log_db(user_id: str, payload: dict):
    """
    [데이터 수집] AI 학습을 위해 모든 환경/피부/생활 변수를 DB에 기록합니다.
    (final_skin.py의 log_today 역할)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 2. 데이터 추출
        cam = payload["camera"]
        env = payload["env"]
        life = payload["lifestyle"]

        # Hot 세안 여부, 민감성 여부는 0/1 숫자로 변환
        is_hot = 1 if str(life.get("wash_temp", "")).lower() == "hot" else 0
        is_sens = 1 if str(life.get("sensitivity", "")).lower() == "yes" else 0

        # 3. 데이터 삽입
        insert_sql = """
            INSERT INTO training_log 
            (user_id, redness, sebum, moisture, acne, uv, humidity, temperature, 
             sleep_hours, water_intake, wash_freq, is_hot_wash, is_sensitive)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (
            user_id,
            float(cam.get("redness", 0)), float(cam.get("sebum", 0)),
            float(cam.get("moisture", 0)), float(cam.get("acne", 0)),
            float(env.get("uv", 0)), float(env.get("humidity", 0)), float(env.get("temperature", 0)),
            float(life.get("sleep_hours_7d", 7)), int(life.get("water_intake_ml", 1500)),
            float(life.get("wash_freq_per_day", 2)), is_hot, is_sens
        ))

        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"📝 [Training] 학습 데이터 기록 완료 (User: {user_id})")

    except Exception as e:
        logger.error(f"⚠️ 학습 데이터 저장 실패: {e}")


def train_model_from_db():
    """
    [모델 재학습] DB에 쌓인 데이터를 읽어와 AI 모델을 업데이트합니다.
    (final_skin.py의 train_trouble_model 역할)
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    import pandas as pd

    logger.info("🎓 [Training] 모델 재학습 프로세스 시작...")

    try:
        conn = psycopg2.connect(**DB_CONFIG)

        # 1. DB에서 모든 로그 가져오기 (시간순 정렬)
        query = "SELECT * FROM training_log ORDER BY user_id, created_at ASC"
        df = pd.read_sql(query, conn)
        conn.close()

        if len(df) < 50:
            logger.warning(f"데이터 부족({len(df)}개). 최소 50개 이상 쌓이면 학습하세요.")
            return {"status": "skipped", "msg": "데이터 부족"}

        # 2. 라벨링 (Labeling): 2일 뒤 홍조가 악화되었는가?
        X = []
        y = []

        # 사용자별로 그룹화해서 미래 데이터 비교
        grouped = df.groupby("user_id")

        horizon_days = 2  # 2일 뒤 예측

        for user, group in grouped:
            # 날짜 인덱스 설정
            group = group.sort_values("created_at")
            vals = group.to_dict("records")

            for i in range(len(vals) - horizon_days):
                curr = vals[i]
                future = vals[i + horizon_days]

                # 피처 벡터 (입력)
                features = [
                    curr["redness"], curr["sebum"], curr["moisture"], curr["acne"],
                    curr["uv"], curr["humidity"], curr["temperature"],
                    curr["sleep_hours"], curr["water_intake"], curr["wash_freq"],
                    curr["is_hot_wash"], curr["is_sensitive"]
                ]

                # 라벨 (정답): 미래 홍조가 60 이상이고, 현재보다 8 이상 증가했으면 '악화(1)'
                red_now = curr["redness"]
                red_fut = future["redness"]

                is_trouble = 1 if (red_fut >= 60 and (red_fut - red_now) >= 8) else 0

                X.append(features)
                y.append(is_trouble)

        if len(X) < 10:
            return {"status": "skipped", "msg": "유효한 학습 샘플(쌍)이 너무 적습니다."}

        # 3. 모델 학습
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", C=0.5))
        ])

        model.fit(X, y)

        # 4. 저장
        joblib.dump(model, MODEL_PATH)
        logger.info(f"✅ 모델 업데이트 완료! (샘플 수: {len(X)})")
        return {"status": "success", "sample_count": len(X)}

    except Exception as e:
        logger.error(f"❌ 학습 중 오류 발생: {e}")
        return {"status": "error", "msg": str(e)}