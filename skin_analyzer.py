# skin_analyzer.py
"""
[피부 분석 실행 및 저장 담당]
API 서버(main.py)의 요청을 받아 실제 AI 분석을 수행하고 로그를 저장하는 모듈입니다.

기능:
1. GPT Vision API 호출 (피부 이미지 분석)
2. PostgreSQL DB 저장 (분석 결과 기록)
"""

import os
import logging
import psycopg2
from dotenv import load_dotenv

# 사용자 정의 모듈
from gpt_api import analyze_skin_image
from config import DB_CONFIG

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


# ==============================================================================
# 1. 데이터베이스 저장 (DB Handling)
# ==============================================================================

def save_analysis_to_db(user_id: str, gpt_result: dict, manual_input: dict) -> int:
    """
    분석 결과와 사용자 입력값(유수분)을 PostgreSQL DB에 저장합니다.

    Returns:
        int: 저장된 로그의 ID (실패 시 None)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 테이블 자동 생성 (없을 경우)
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        query = """
            INSERT INTO analysis_log 
            (user_id, acne, wrinkles, pores, pigmentation, redness, moisture, sebum)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """

        # 데이터 매핑 (값이 없을 경우 기본값 0 처리)
        data = (
            user_id,
            gpt_result.get("acne", 0),
            gpt_result.get("wrinkles", 0),
            gpt_result.get("pores", 0),
            gpt_result.get("pigmentation", 0),
            gpt_result.get("redness", 0),
            manual_input.get("moisture", 50),
            manual_input.get("sebum", 50)
        )

        cursor.execute(query, data)
        new_id = cursor.fetchone()[0]
        conn.commit()

        cursor.close()
        conn.close()

        logger.info(f"✅ [DB] 분석 결과 저장 완료 (ID: {new_id}, User: {user_id})")
        return new_id

    except Exception as e:
        logger.error(f"❌ DB 저장 실패: {e}")
        return None


# ==============================================================================
# 2. 분석 실행 메인 로직 (Main Logic)
# ==============================================================================

def perform_skin_analysis(user_id: str, image_path: str, moisture: int, sebum: int) -> dict:
    """
    [핵심 함수] 이미지 경로와 센서 데이터를 받아 피부 분석 전체 과정을 수행합니다.

    Args:
        user_id (str): 사용자 ID
        image_path (str): 분석할 이미지 파일 경로
        moisture (int): 수분 센서값
        sebum (int): 유분 센서값

    Returns:
        dict: {analysis_id, gpt_result, manual_input} 또는 None
    """
    logger.info(f"📸 [피부 분석 요청] User: {user_id}, Path: {image_path}")

    # 1. 이미지 파일 검증
    if not os.path.exists(image_path):
        logger.error(f"⚠️ 파일이 존재하지 않습니다: {image_path}")
        return None

    # 2. GPT Vision API 호출
    logger.info("🚀 AI(GPT) 분석 수행 중...")
    gpt_result = analyze_skin_image(image_path)

    # [안전장치] GPT 분석 실패 시 처리
    if not gpt_result:
        logger.warning("❌ GPT 분석 실패 (API 오류 또는 응답 없음)")
        # 필요하다면 여기서 '비상용 더미 데이터'를 반환하도록 수정 가능
        # gpt_result = {"acne": 50, "wrinkles": 50, ...}
        return None

    logger.info(f"📊 AI 분석 완료: {gpt_result}")

    # 3. 데이터 패키징
    manual_input = {"moisture": moisture, "sebum": sebum}

    # 4. DB 저장
    analysis_id = save_analysis_to_db(user_id, gpt_result, manual_input)

    if not analysis_id:
        logger.error("⚠️ DB 저장이 실패했지만 분석 결과는 반환합니다.")

    # 5. 최종 결과 반환
    return {
        "analysis_id": analysis_id,
        "gpt_result": gpt_result,
        "manual_input": manual_input
    }


# ==============================================================================
# 3. 테스트 코드 (Local Test)
# ==============================================================================
if __name__ == "__main__":
    print("\n🧪 [테스트 모드] skin_analyzer.py 직접 실행")

    # 1. 테스트용 가짜 데이터
    # (주의: 실제 존재하는 이미지 경로를 입력해야 테스트 가능)
    TEST_USER = "test_local_user"
    TEST_IMG = "image-data/test/images/acne-5_jpeg.rf.2d6671715f0149df7b494c4d3f12a98b.jpg"
    TEST_MOIST = 35
    TEST_SEBUM = 75

    # 2. 실행
    result = perform_skin_analysis(TEST_USER, TEST_IMG, TEST_MOIST, TEST_SEBUM)

    # 3. 결과 출력
    if result:
        print("\n🎉 [성공] 분석 프로세스 완료")
        print(result)
    else:
        print("\n💥 [실패] 분석 중 오류 발생")