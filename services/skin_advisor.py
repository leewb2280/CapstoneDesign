# skin_advisor.py
"""
[피부 맞춤형 조언 및 처방 담당]
API 서버의 요청을 받아, 수집된 데이터를 종합하여
최종적인 피부 나이 진단, 화장품 추천, 관리 루틴을 생성하는 모듈입니다.
"""

import logging
import datetime
import json
import numpy as np

# 설정 및 유틸리티
from .config import *
from core.utils import (
    load_products_from_db,
    get_current_weather,
    predict_trouble_proba,
    get_skin_data_by_id,
    save_recommendation_to_db
)
# 분석 로직 엔진
from .skin_advisor_logic import SkinCareAdvisor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
OWM_API_KEY = os.getenv("OWM_API_KEY")


# ==============================================================================
# 1. 헬퍼 함수 (Helper Functions)
# ==============================================================================

def convert_numpy_to_native(obj):
    """
    Numpy 데이터 타입(int64, float32 등)을 파이썬 기본 타입으로 변환합니다.
    (JSON 직렬화 에러 방지용)
    """
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


# ==============================================================================
# 2. 메인 실행 함수 (Main Logic)
# ==============================================================================

def run_skin_advisor(user_id: str, analysis_id: int, lifestyle: dict, user_pref: dict) -> dict:
    """
    [핵심 로직] 사용자 정보와 분석 데이터를 결합하여 최종 처방을 내립니다.

    Args:
        user_id (str): 사용자 ID
        analysis_id (int): 1단계에서 생성된 분석 로그 ID
        lifestyle (dict): 생활습관 설문 데이터
        user_pref (dict): 사용자 선호도 데이터

    Returns:
        dict: 최종 추천 결과 (피부나이, 추천제품, 루틴, 트러블예측)
    """
    logger.info(f"🧠 [Advisor] 심층 분석 시작 (User: {user_id}, AnalysisID: {analysis_id})")

    # -------------------------------------------------------
    # Step 1. 데이터 수집 (Data Aggregation)
    # -------------------------------------------------------

    # 1. 피부 분석 데이터 로드 (DB)
    camera_data = get_skin_data_by_id(analysis_id)

    if not camera_data:
        logger.warning(f"❌ DB에서 ID({analysis_id})를 찾을 수 없습니다. 더미 데이터를 사용합니다.")
        camera_data = {
            "tone": 50, "sebum": 50, "moisture": 50, "acne": 50,
            "wrinkle": 50, "pore": 50, "pigmentation": 50, "redness": 50
        }

    # 2. 날씨 정보 로드 (API)
    env_data = get_current_weather(OWM_API_KEY)

    # 3. 분석용 Payload 생성
    payload = {
        "camera": camera_data,
        "env": env_data,
        "lifestyle": lifestyle,
        "user": user_pref,
        "time": {"hour": datetime.datetime.now().hour}
    }

    # -------------------------------------------------------
    # Step 2. AI 엔진 가동 (Analysis & Recommendation)
    # -------------------------------------------------------
    advisor = SkinCareAdvisor(payload)

    # 1. 피부 나이 계산
    skin_age = int(advisor.calc_skin_age())

    # 2. 제품 추천
    # (최신 재고 반영을 위해 매번 DB에서 로드)
    product_db = load_products_from_db()
    rec_result = advisor.recommend_products(product_db)

    # 3. 루틴 텍스트 생성
    routine = advisor.generate_routine_text(rec_result["top3"])

    # 4. 트러블 발생 확률 예측 (ML 모델)
    ml_pred = predict_trouble_proba(payload)
    raw_prob = float(ml_pred.get("prob", 0.0) or 0.0)

    # -------------------------------------------------------
    # Step 3. 데이터 정리 및 저장 (Cleanup & Save)
    # -------------------------------------------------------

    # 1. Numpy 타입 제거 (JSON 변환 안전하게)
    clean_rec_result = convert_numpy_to_native(rec_result)
    clean_routine = convert_numpy_to_native(routine)

    # 2. 결과 DB 저장
    save_recommendation_to_db(
        user_id=user_id,
        analysis_id=analysis_id,
        skin_age=skin_age,
        rec_result=clean_rec_result,
        routine=clean_routine,
        trouble_prob=raw_prob
    )

    logger.info(f"✨ [Advisor] 분석 완료 (피부나이: {skin_age}세, 트러블확률: {int(raw_prob * 100)}%)")

    # 3. 최종 결과 반환
    return {
        "user_id": user_id,
        "skin_age": skin_age,
        "top3": clean_rec_result["top3"],
        "routine": clean_routine,
        "trouble_prediction": ml_pred["msg"],
        "trouble_prob": raw_prob
    }


# ==============================================================================
# 3. 테스트 코드 (Local Test)
# ==============================================================================
if __name__ == "__main__":
    print("\n🧪 [테스트 모드] skin_advisor.py 직접 실행")

    # 1. 테스트용 가짜 데이터
    TEST_USER = "test_advisor_user"
    TEST_ANALYSIS_ID = 1  # 주의: DB에 실제로 존재하는 ID여야 정확함

    TEST_LIFESTYLE = {
        "sleep_hours_7d": 6.5,
        "water_intake_ml": 1200,
        "wash_freq_per_day": 2,
        "wash_temp": "hot",
        "sensitivity": "yes"
    }

    TEST_PREF = {
        "age": 24,
        "pref_texture": "cream"
    }

    # 2. 실행
    try:
        result = run_skin_advisor(TEST_USER, TEST_ANALYSIS_ID, TEST_LIFESTYLE, TEST_PREF)

        # 3. 결과 출력
        print("\n✅ 최종 결과 JSON:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n💥 오류 발생: {e}")