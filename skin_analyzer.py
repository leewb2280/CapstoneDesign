# skin_analyzer.py
"""
[피부 분석 실행 및 저장 담당]
1. 사용자로부터 이미지 경로와 유수분 수치를 입력받음
2. gpt_api.py를 호출해 피부 사진 분석
3. 결과 데이터를 PostgreSQL(analysis_log)에 저장
"""

import os
import psycopg2
from dotenv import load_dotenv

# 분리한 모듈 불러오기
from gpt_api import analyze_skin_image
from config import DB_CONFIG

load_dotenv()


# =========================================
# DB 저장 함수
# =========================================
def save_analysis_to_db(gpt_result, manual_input):
    """분석 결과와 사용자 입력값을 DB에 저장합니다."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 테이블 생성 (없을 경우)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_log (
                id SERIAL PRIMARY KEY,
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
            (acne, wrinkles, pores, pigmentation, redness, moisture, sebum)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """

        # 데이터 매핑
        data = (
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
        print(f"✅ 분석 결과가 DB에 저장되었습니다. (ID: {new_id})")
        return new_id

    except Exception as e:
        print(f"❌ DB 저장 실패: {e}")
        return None


# =========================================
# 메인 실행 함수
# =========================================
def run_skin_analysis():
    print("\n📸 [피부 분석 시작]")

    # 1. 이미지 경로 입력 (실제 앱에서는 파일 업로드로 대체)
    image_path = r"image-data/test/images/acne-5_jpeg.rf.2d6671715f0149df7b494c4d3f12a98b.jpg"

    if not os.path.exists(image_path):
        print("   ⚠️ 파일이 존재하지 않습니다.")
        return None

    # 2. GPT 분석 호출 (분리된 gpt_api 사용)
    print("   🚀 AI가 피부를 분석 중입니다... (잠시 대기)")
    gpt_result = analyze_skin_image(image_path)

    if not gpt_result:
        print("   ❌ 분석에 실패했습니다.")
        return None

    print(f"   📊 분석 결과: {gpt_result}")

    # 3. 추가 정보(유수분) 수동 입력
    print("\n💧 [추가 정보 입력]")
    try:
        moisture = int(input("   현재 수분감 (0~100): ") or 50)
        sebum = int(input("   현재 유분감 (0~100): ") or 50)
    except:
        moisture, sebum = 50, 50

    manual_input = {"moisture": moisture, "sebum": sebum}

    # 4. DB 저장
    analysis_id = save_analysis_to_db(gpt_result, manual_input)

    return analysis_id


if __name__ == "__main__":
    run_skin_analysis()