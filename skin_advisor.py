# skin_advisor.py
"""
[피부 맞춤형 조언 및 처방 담당]
이 파일은 프로그램의 '지휘자(Orchestrator)' 역할을 합니다.
수집된 데이터(DB, 날씨, 설문)를 모두 모아 Engine에 전달하고,
최종 결과를 사용자에게 보여주고 DB에 저장합니다.
"""

import sys
import os
import datetime
import numpy as np  # [수정] numpy 타입 감지를 위해 추가
from dotenv import load_dotenv

# 설정 및 유틸리티 모듈 임포트
from config import *
from utils import (
    load_json, save_json, load_products_csv, get_current_weather,
    log_daily_status, predict_trouble_proba,
    collect_lifestyle_interactive, ask_pref_texture,
    get_latest_skin_data_from_db,
    save_recommendation_to_db
)
# 핵심 로직 엔진 임포트
from analysis_logic import SkinCareAdvisor


# =========================================
# Numpy 타입을 파이썬 기본 타입으로 변환하는 함수
# =========================================
def convert_numpy_to_native(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_to_native(i) for i in obj]
    return obj


def main():
    # =========================================
    # 1. 초기 설정
    # =========================================
    load_dotenv()  # .env 파일에서 API 키 로드
    api_key = os.getenv("OWM_API_KEY")

    print("=== 🧴 AI 맞춤형 스킨케어 어드바이저 시작 ===")

    # =========================================
    # 2. 데이터 수집 단계 (Data Collection)
    # =========================================

    # (1) 생활습관
    saved_life = load_json(LIFESTYLE_JSON)
    life_style = collect_lifestyle_interactive(saved_life)
    save_json(LIFESTYLE_JSON, life_style)

    # (2) 사용자 선호
    saved_prefs = load_json(USER_PREFS_JSON, default={"pref_texture": "gel", "age": 23})
    new_texture = ask_pref_texture(saved_prefs.get("pref_texture", "gel"))

    user_data = {"age": saved_prefs.get("age", 23), "pref_texture": new_texture}
    save_json(USER_PREFS_JSON, user_data)

    # (3) 피부 데이터 (DB 로드)
    print("\n📸 [피부 데이터 로드]")
    db_data = get_latest_skin_data_from_db()

    analysis_id = None

    if db_data:
        analysis_id = db_data.get("id")
        camera_data = db_data
        print(f"✅ DB 분석 데이터(ID:{analysis_id})를 사용합니다.")
    else:
        print("⚠️ DB 데이터를 찾을 수 없어 테스트용 더미 데이터를 사용합니다.")
        camera_data = {
            "tone": 55, "sebum": 70, "moisture": 35, "acne": 65,
            "wrinkle": 30, "pore": 60, "pigmentation": 40, "redness": 45
        }

    # (4) 날씨 환경
    env_data = get_current_weather(api_key)
    print(f"\n[환경] 기온 {env_data['temperature']}도, 습도 {env_data['humidity']}%, UV {env_data['uv']}")

    # [Payload 통합]
    payload = {
        "camera": camera_data,
        "env": env_data,
        "lifestyle": life_style,
        "user": user_data,
        "time": {"hour": datetime.datetime.now().hour}
    }

    # =========================================
    # 3. AI 엔진 가동 (Analysis & Recommendation)
    # =========================================
    advisor = SkinCareAdvisor(payload)

    # 1. 피부 나이 계산
    skin_age = int(advisor.calc_skin_age())
    print(f"\n🔎 분석 결과: 피부 나이 예측 {skin_age}세")

    # 2. 제품 데이터 로드 및 추천 실행
    product_db = load_products_csv(CSV_DATA_PATH)
    if not product_db:
        print(f"⚠️ {CSV_DATA_PATH} 파일이 없습니다. 추천을 건너뜁니다.")
        return

    rec_result = advisor.recommend_products(product_db)

    # =========================================
    # 4. 결과 출력 (Console Output)
    # =========================================
    print("\n🏆 [TOP 3 추천 제품]")
    for item in rec_result["top3"]:
        print(f"{item['rank']}위: {item['name']} ({item['brand']})")
        print(f"   └ 점수: {item['score']}점 | 이유: {', '.join(item['reasons'])}")

    print("\n💡 [추천 이유 요약]")
    for r in rec_result["reasons"]:
        print(f"- {r}")

    # 5. 루틴 텍스트 생성
    routine = advisor.generate_routine_text(rec_result["top3"])
    print("\n📅 [오늘의 루틴]")
    print("\n".join(routine["am"]))
    print("-" * 30)
    print("\n".join(routine["pm"]))

    # 6. 머신러닝 트러블 예측
    ml_pred = predict_trouble_proba(payload)
    print(f"\n🔮 [AI 트러블 예측] {ml_pred['msg']}")

    # 확률값 가져올 때 float() 강제 변환
    raw_prob = ml_pred.get("prob", 0.0)
    if raw_prob is None:
        raw_prob = 0.0
    trouble_prob_val = float(raw_prob)

    # =========================================
    # 7. 결과 저장 (Logging & DB)
    # =========================================

    # DB에 저장하기 전에 모든 데이터를 깨끗한 파이썬 타입으로 변환
    # (rec_result 안에 numpy 점수가 들어있을 수 있으므로 전체 세탁)
    clean_rec_result = convert_numpy_to_native(rec_result)
    clean_routine = convert_numpy_to_native(routine)

    # (1) ML 학습용 CSV 로그 저장
    log_daily_status(clean_rec_result, payload)

    # (2) JSON 파일 저장
    save_json(RESULT_JSON_PATH, {
        "date": str(datetime.date.today()),
        "analysis_id": analysis_id,
        "skin_age": skin_age,
        "recommendation": clean_rec_result,
        "routine": clean_routine
    })

    # (3) PostgreSQL DB에 저장
    if analysis_id:
        print("💾 DB 저장을 시도합니다...")
        save_recommendation_to_db(
            analysis_id=analysis_id,
            skin_age=skin_age,
            rec_result=clean_rec_result,
            routine=clean_routine,
            trouble_prob=trouble_prob_val
        )
    else:
        print("⚠️ 분석 ID가 없어 DB에 처방 결과를 연결하여 저장할 수 없습니다.")

    print("\n✅ 모든 결과 처리가 완료되었습니다.")


if __name__ == "__main__":
    main()