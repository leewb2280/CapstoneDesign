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
import re
import ast

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
    CSV 파일을 로드하고 데이터를 깨끗하게 정제합니다.
    1. 문자열로 저장된 리스트("['a', 'b']")를 실제 리스트로 변환
    2. '상세설명참조' 같은 무의미한 태그 제거
    3. 전성분 텍스트에서 불필요한 기호 제거
    4. 스킨케어 디바이스(기계) 제외 옵션 적용
    """
    if not os.path.exists(path):
        print(f"[경고] {path} 파일이 없습니다. 빈 리스트를 반환합니다.")
        return []

    products = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 1. 기본 정보 로드
            p = {
                "name": row.get("name", "No Name"),
                "price": float(row.get("price", 0)),
                "brand": row.get("brand", "Unknown"),
                "url": row.get("url", ""),
                "official_category": row.get("official_category", "Unknown")
            }

            # [필터링] 디바이스(기계)는 화장품 추천에서 제외
            if "디바이스" in p["official_category"]:
                continue

            # 2. 태그 정제
            raw_tags = row.get("tags", "[]")
            try:
                # 안전하게 문자열 리스트 파싱
                tags_list = ast.literal_eval(raw_tags)

                # 무의미한 태그 필터링
                clean_tags = []
                for t in tags_list:
                    if "상세" in t and "참조" in t: continue  # 상세설명참조 제거
                    clean_tags.append(t)
                p["tags"] = clean_tags
            except:
                p["tags"] = []

            # 3. 전성분 정제
            raw_ings = row.get("featured_ingredients", "[]")
            try:
                ings_list = ast.literal_eval(raw_ings)
                clean_ings = []
                for ing in ings_list:
                    # 줄바꿈 및 불필요한 기호 제거
                    text = ing.replace("\n", "")
                    text = re.sub(r'^\[.*?\]', '', text).strip()

                    if text:
                        clean_ings.append(text)

                p["featured_ingredients"] = clean_ings
            except:
                p["featured_ingredients"] = []

            products.append(p)

    print(f"📂 {len(products)}개의 제품 데이터를 로드했습니다. (디바이스 제외됨)")
    return products


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
    except:
        print("[Info] 날씨 API 호출 실패, 기본값을 사용합니다.")

    return env


# =========================================
# 3. 머신러닝 (Machine Learning)
# =========================================

def predict_trouble_proba(payload):
    """
    미리 학습된 모델(.pkl)을 로드하여 트러블 발생 확률을 예측합니다.
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
        f_skin = [
            float(cam.get("redness", 0)),
            float(cam.get("sebum", 0)),
            float(cam.get("moisture", 0)),
            float(cam.get("acne", 0))
        ]

        f_env = [
            float(env.get("uv", 0)),
            float(env.get("humidity", 0)),
            float(env.get("temperature", 0))
        ]

        is_hot_wash = 1.0 if str(life.get("wash_temp", "")).lower() == "hot" else 0.0
        is_sensitive = 1.0 if str(life.get("sensitivity", "")).lower() == "yes" else 0.0

        f_life = [
            float(life.get("sleep_hours_7d", 7)),
            float(life.get("water_intake_ml", 1500)),
            float(life.get("wash_freq_per_day", 2)),
            is_hot_wash,
            is_sensitive
        ]

        # 전체 합치기
        features = np.array([f_skin + f_env + f_life])

        # 예측 실행
        prob = model.predict_proba(features)[0, 1]
        return {"prob": round(prob, 2), "msg": f"트러블 발생 확률: {int(prob * 100)}%"}

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

        if raw in ["젤", "gel"]: return "gel"
        if raw in ["크림", "cream"]: return "cream"
        if raw in ["로션", "lotion"]: return "lotion"

        print("   ⚠️ gel, cream, lotion 중 하나로 입력해주세요.")


# =========================================
# 5. 데이터베이스 (PostgreSQL)
# =========================================

def get_latest_skin_data_from_db():
    """DB에서 최신 분석 데이터를 가져옵니다."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, acne, wrinkles, pores, pigmentation, redness, moisture, sebum, created_at 
            FROM analysis_log 
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row: return None

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
    """Skin Advisor의 최종 처방 결과를 DB에 저장합니다."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_log (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER,
            skin_age REAL,
            top3_products TEXT,
            routine_am TEXT,
            routine_pm TEXT,
            trouble_prob REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        products_json = json.dumps(rec_result["top3"], ensure_ascii=False)
        routine_am_json = json.dumps(routine["am"], ensure_ascii=False)
        routine_pm_json = json.dumps(routine["pm"], ensure_ascii=False)

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


def log_daily_status(rec_result, payload):
    """[로그 저장] 하루 데이터를 CSV 파일에 기록합니다."""
    if not LOG_PATH:
        print("[설정 오류] LOG_PATH가 지정되지 않아 로그를 저장하지 않습니다.")
        return

    file_exists = os.path.exists(LOG_PATH)

    try:
        with open(LOG_PATH, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            if not file_exists:
                header = [
                    "timestamp", "redness", "sebum", "moisture", "acne",
                    "uv", "humidity", "temperature",
                    "sleep", "water", "wash_freq", "wash_temp", "sensitivity",
                    "top1_product"
                ]
                writer.writerow(header)

            cam = payload["camera"]
            env = payload["env"]
            life = payload["lifestyle"]
            top1 = rec_result["top3"][0]["name"] if rec_result.get("top3") else "None"

            row = [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                cam.get("redness", 0),
                cam.get("sebum", 0),
                cam.get("moisture", 0),
                cam.get("acne", 0),
                env.get("uv", 0),
                env.get("humidity", 0),
                env.get("temperature", 0),
                life.get("sleep_hours_7d", 0),
                life.get("water_intake_ml", 0),
                life.get("wash_freq_per_day", 0),
                life.get("wash_temp", "normal"),
                life.get("sensitivity", "no"),
                top1
            ]
            writer.writerow(row)
            print(f"📝 [Log] 데이터가 '{LOG_PATH}'에 기록되었습니다.")

    except Exception as e:
        print(f"⚠️ [로그 저장 실패] {e}")