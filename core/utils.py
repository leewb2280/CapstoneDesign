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

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. 외부 API 통신 (Weather)
# ==============================================================================

def get_current_weather(api_key: str = None) -> dict:
    """
    OpenWeatherMap API를 통해 현재 날씨 정보를 가져옵니다.

    Args:
        api_key (str): OWM API Key

    Returns:
        dict: {'uv': float, 'humidity': int, 'temperature': float, 'source': str}
    """
    # 위치 설정 (예시: 광주광역시 좌표)
    # 실서비스 시에는 GPS 좌표를 앱에서 받아오도록 수정 가능
    lat, lon = 35.15944, 126.85250

    # 기본값 (API 키가 없거나 호출 실패 시 사용)
    fallback_env = {
        "uv": 5.0,
        "humidity": 45,
        "temperature": 24.0,
        "source": "fallback"
    }

    if not api_key:
        return fallback_env

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={api_key}"

        with urllib.request.urlopen(url, timeout=3) as res:
            data = json.load(res)

            return {
                "temperature": float(data["main"]["temp"]),
                "humidity": int(data["main"]["humidity"]),
                "uv": 5.0,  # 무료 API는 UV를 안 주는 경우가 많아 고정값 사용
                "source": "api(weather)"
            }

    except Exception as e:
        logger.warning(f"날씨 API 호출 실패 ({e}), 기본값을 사용합니다.")
        return fallback_env


# ==============================================================================
# 2. 머신러닝 (Machine Learning)
# ==============================================================================

def predict_trouble_proba(payload: dict) -> dict:
    """
    학습된 모델(.pkl)을 사용하여 피부 트러블 발생 확률을 예측합니다.

    Args:
        payload (dict): camera, env, lifestyle 데이터가 포함된 딕셔너리

    Returns:
        dict: {'prob': float, 'msg': str}
    """
    if not os.path.exists(MODEL_PATH):
        return {"prob": None, "msg": "AI 모델 파일이 없습니다."}

    try:
        model = joblib.load(MODEL_PATH)

        # 1. 데이터 추출
        cam = payload["camera"]
        env = payload["env"]
        life = payload["lifestyle"]

        # 2. Feature Vector 생성 (학습 순서 중요: Skin -> Env -> Life)
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

        # 4. 예측 실행
        # [중요] 모델 클래스 0번이 '트러블 발생' 확률임
        prob = model.predict_proba(features)[0, 0]

        return {
            "prob": round(prob, 2),
            "msg": f"트러블 발생 확률: {int(prob * 100)}%"
        }

    except Exception as e:
        logger.error(f"ML 예측 오류: {e}")
        return {"prob": None, "msg": f"예측 중 오류 발생: {str(e)}"}


# ==============================================================================
# 3. 데이터베이스 (PostgreSQL)
# ==============================================================================

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

        row_id, acne, wrinkles, pores, pigm, redness, moisture, sebum, created_at = row

        # 분석 로직에서 사용하기 편한 Dictionary 형태로 반환
        return {
            "id": row_id,
            "acne": acne,
            "wrinkle": wrinkles,
            "pore": pores,
            "pigmentation": pigm,
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

        # 테이블이 없을 경우 생성 (안전장치)
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

def create_user_table():
    """사용자 정보(아이디/비밀번호)를 저장할 테이블 생성"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(50) PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # [추가] 2. 사용자 상세 프로필 테이블 (6가지 항목)
        # user_id를 Foreign Key로 사용하여 users 테이블과 연결
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
                CONSTRAINT fk_user
                    FOREIGN KEY(user_id) 
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );
        """)

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"사용자 테이블 생성 실패: {e}")


# [신규 함수] 프로필 저장/업데이트 (Upsert)
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


# [신규 함수] 프로필 조회
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


def get_user_history_db(user_id):
    """
    특정 사용자의 과거 기록을 조회합니다.
    recommendation_log와 analysis_log를 JOIN하여 풍부한 데이터를 가져옵니다.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # JOIN 쿼리: 추천 기록 + 분석 기록(이미지, 점수 등)
        query = """
            SELECT 
                r.id, r.skin_age, r.top3_products, r.created_at,
                a.image_path, a.acne, a.wrinkles, a.pores, a.pigmentation, a.redness, a.moisture, a.sebum
            FROM recommendation_log r
            LEFT JOIN analysis_log a ON r.analysis_id = a.id
            WHERE r.user_id = %s 
            ORDER BY r.id DESC
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        history = []
        for r in rows:
            # r[0]: record_id, r[1]: skin_age, r[2]: top3_json, r[3]: date
            # r[4]: img_path, r[5]~r[11]: scores

            top3 = json.loads(r[2]) if r[2] else []

            # 이미지 경로가 없거나 파일이 없으면 기본 이미지 처리 (프론트에서 처리하도록 None 보냄)
            img_path = r[4] if r[4] else None

            history.append({
                "record_id": r[0],
                "skin_age": r[1],
                "top3_names": [p['name'] for p in top3],
                "date": str(r[3]),
                "image_path": img_path,
                "scores": {
                    "acne": r[5], "wrinkles": r[6], "pores": r[7],
                    "pigmentation": r[8], "redness": r[9],
                    "moisture": r[10], "sebum": r[11]
                }
            })

        return history
    except Exception as e:
        logger.error(f"기록 조회 실패: {e}")
        return []


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
        start_date: str = None,  # [New] 검색 시작일 (YYYY-MM-DD)
        end_date: str = None,  # [New] 검색 종료일 (YYYY-MM-DD)
        page: int = 1,
        page_size: int = 50
):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 기본 쿼리
        base_query = "FROM analysis_log WHERE user_id = %s"
        params = [user_id]

        # 2. [기존] 상태 조건 필터 적용
        if condition:
            filter_result = get_filter_query(condition)
            if filter_result:
                sql_part, val = filter_result
                base_query += f" {sql_part}"
                if val is not None:
                    params.append(val)

        # 3. [신규] 날짜 기간 필터 적용
        # 사용자가 날짜를 입력했다면 WHERE 절에 추가
        if start_date:
            base_query += " AND created_at >= %s"
            params.append(start_date)  # 예: '2025-11-01'

        if end_date:
            # 해당 날짜의 23시 59분까지 포함하기 위해 날짜 처리가 필요할 수 있지만
            # 여기서는 편의상 입력된 날짜(00시 00분) 기준으로 처리하거나
            # 프론트에서 시간을 붙여서 보내는 것을 가정합니다.
            base_query += " AND created_at <= %s"
            params.append(end_date + " 23:59:59")  # 그 날짜의 마지막 시간까지 포함

        # 4. 개수 세기 (Pagination용)
        count_sql = f"SELECT COUNT(*) {base_query}"
        cursor.execute(count_sql, tuple(params))
        total_count = cursor.fetchone()[0]

        # 5. 데이터 조회
        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT id, created_at, moisture, sebum, redness, pores, wrinkles, acne
            {base_query}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        full_params = params + [page_size, offset]

        cursor.execute(data_sql, tuple(full_params))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        records = []
        for r in rows:
            records.append({
                "id": r[0],
                "date": r[1].strftime("%Y-%m-%d %H:%M"),
                "scores": {
                    "moisture": r[2], "sebum": r[3],
                    "redness": r[4], "pore": r[5],
                    "wrinkles": r[6], "acne": r[7]
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

# 이 파일이 실행될 때 테이블이 없으면 생성하도록 설정
if __name__ == "__main__":
    create_user_table()
    print("✅ 사용자 테이블 확인 완료")