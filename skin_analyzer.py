# skin_analyzer.py
"""
[피부 분석 및 데이터 수집 담당]
이 파일은 사용자의 피부 이미지를 분석하고 기초 데이터를 DB에 저장하는 역할을 합니다.
1. 이미지 파일을 Base64 코드로 변환 (GPT Vision API 전송용)
2. OpenAI GPT API를 호출하여 피부 상태(여드름, 주름 등) 수치화
3. 사용자로부터 유수분(Moisture/Sebum) 수치 입력 받기 (센서 대용)
4. 분석 결과와 입력값을 PostgreSQL 데이터베이스('analysis_log')에 저장
"""

import base64
import os
import json
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

# config에서 설정값 가져오기 (DB접속정보, 모델명, 프롬프트)
from config import DB_CONFIG, GPT_MODEL_NAME, GPT_SYSTEM_PROMPT

# 1. API 키 설정 (보안 강화: 환경변수 로드)
load_dotenv()
client = OpenAI()


# =========================================
# 2. 이미지 전처리
# =========================================

def encode_image_to_base64(image_path):
    """
    이미지 파일을 읽어서 Base64 문자열로 변환합니다.
    GPT Vision API는 이미지 파일을 직접 받지 않고 Base64 문자열을 요구하기 때문입니다.
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"오류: '{image_path}' 파일을 찾을 수 없습니다.")
        return None
    except Exception as e:
        print(f"이미지 인코딩 중 오류 발생: {e}")
        return None


# =========================================
# 3. DB 저장 (PostgreSQL)
# =========================================

def save_to_db(result, image_path, moisture, sebum):
    """
    GPT 분석 결과(JSON)와 사용자가 입력한 유수분 수치를
    PostgreSQL의 'analysis_log' 테이블에 저장합니다.
    """
    try:
        # PostgreSQL 연결
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 테이블 생성 (없으면 생성, id는 SERIAL로 자동 증가)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_log (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acne INTEGER,
            wrinkles INTEGER,
            pores INTEGER,
            pigmentation INTEGER,
            redness INTEGER,
            moisture INTEGER,
            sebum INTEGER,
            image_path TEXT
        );
        """)

        # 데이터 삽입 (Python 변수를 SQL 쿼리에 안전하게 바인딩하기 위해 %s 사용)
        insert_query = """
        INSERT INTO analysis_log (acne, wrinkles, pores, pigmentation, redness, moisture, sebum, image_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        data = (
            result.get('acne'),
            result.get('wrinkles'),
            result.get('pores'),
            result.get('pigmentation'),
            result.get('redness'),
            moisture,
            sebum,
            image_path
        )

        cursor.execute(insert_query, data)
        conn.commit()
        cursor.close()  # 커서 닫기
        conn.close()  # 연결 닫기
        print(f"✅ [DB] PostgreSQL에 분석 결과 저장 완료")

    except Exception as e:
        print(f"⚠️ [DB 저장 오류] {e}")


# =========================================
# 4. AI 이미지 분석 (OpenAI GPT)
# =========================================

def analyze_skin_image(image_path):
    """
    OpenAI API를 호출하여 이미지를 분석합니다.
    config.py에 정의된 시스템 프롬프트를 사용하여 JSON 형식의 응답을 받습니다.
    """
    base64_image = encode_image_to_base64(image_path)
    if not base64_image: return None

    try:
        response = client.chat.completions.create(
            model=GPT_MODEL_NAME,  # config에서 설정한 모델 사용
            response_format={"type": "json_object"},  # 결과값을 반드시 JSON으로 받도록 강제
            messages=[
                {"role": "system", "content": GPT_SYSTEM_PROMPT},  # 페르소나 설정
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 이미지의 피부 상태를 분석해서 JSON 수치로 알려줘."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=1024
        )
        # 응답 텍스트를 파이썬 딕셔너리로 변환하여 반환
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"API 호출 중 오류가 발생했습니다: {e}")
        return None


# =========================================
# 실행 블록 (테스트용)
# =========================================
if __name__ == "__main__":
    # 1. 이미지 경로 설정 (현재 파일 위치 기준)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 테스트할 이미지 경로 (본인 환경에 맞게 수정 필요)
    TEST_IMAGE_PATH = os.path.join(base_dir,
                                   r"image-data/test/images/acne-5_jpeg.rf.2d6671715f0149df7b494c4d3f12a98b.jpg")

    print(f"--- 1. GPT 이미지 분석 시작 ({GPT_MODEL_NAME}) ---")
    gpt_result = analyze_skin_image(TEST_IMAGE_PATH)

    if gpt_result:
        print("GPT 분석 완료:", gpt_result)

        # 2. 유수분 데이터 입력 (센서가 없으므로 수동 입력 가정)
        print("\n--- 2. 유수분 데이터 입력 ---")
        try:
            in_moist = int(input("💧 수분 수치 입력 (0-100): "))
            in_sebum = int(input("🛢️ 유분 수치 입력 (0-100): "))
        except:
            print("잘못된 입력. 기본값(50) 사용.")
            in_moist, in_sebum = 50, 50

        # 3. DB 저장 실행
        save_to_db(gpt_result, TEST_IMAGE_PATH, in_moist, in_sebum)
        print("\n✅ 저장 완료.")
    else:
        print("GPT 분석 실패")