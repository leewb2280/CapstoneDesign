# skin_advisor.py
"""
[피부 맞춤형 조언 및 처방 담당]
API 서버의 요청을 받아, 수집된 데이터를 종합하여
최종적인 피부 나이 진단, 화장품 추천, 관리 루틴을 생성하는 모듈입니다.
"""

import logging
import datetime
import numpy as np

# 설정 및 유틸리티
from .config import *
from core.utils import (
    load_products_from_db,
    get_current_weather,
    predict_trouble_proba,
    get_skin_data_by_id,
    save_recommendation_to_db,
    save_training_log_db
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
    사용자 정보와 분석 데이터를 결합하여 최종 처방을 내립니다.
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
    clean_rec_result = convert_numpy_to_native(rec_result)
    clean_routine = convert_numpy_to_native(routine)

    save_recommendation_to_db(
        user_id=user_id,
        analysis_id=analysis_id,
        skin_age=skin_age,
        rec_result=clean_rec_result,
        routine=clean_routine,
        trouble_prob=raw_prob
    )

    save_training_log_db(user_id, payload) # AI 학습용 데이터 저장

    logger.info(f"✨ [Advisor] 분석 완료")

    return {
        "user_id": user_id,
        "skin_age": skin_age,
        "top3": clean_rec_result["top3"],
        "routine": clean_routine,
        "trouble_prediction": ml_pred["msg"],
        "trouble_prob": raw_prob
    }
