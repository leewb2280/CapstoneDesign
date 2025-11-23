# gpt_api.py
"""
[GPT API 통신 담당]
OpenAI Vision API와 통신하여 이미지를 분석하고 피부 상태 점수를 받아오는 모듈입니다.

기능:
1. 이미지 인코딩 (File -> Base64)
2. OpenAI API 호출 (GPT-4 Vision)
3. 응답 파싱 (JSON Parsing)
"""

import os
import json
import base64
import logging
from openai import OpenAI
from dotenv import load_dotenv

# 설정 파일 로드
from .config import GPT_MODEL_NAME, GPT_SYSTEM_PROMPT

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수 및 클라이언트 로드
load_dotenv()
try:
    client = OpenAI()
except Exception as e:
    logger.error(f"OpenAI Client 초기화 실패: {e}")
    client = None


# ==============================================================================
# 1. 이미지 처리 (Image Processing)
# ==============================================================================

def encode_image_to_base64(image_path: str) -> str:
    """
    이미지 파일을 읽어 Base64 문자열로 인코딩합니다.
    (OpenAI API 전송용)

    Args:
        image_path (str): 이미지 파일 경로

    Returns:
        str: Base64로 인코딩된 이미지 문자열 (실패 시 None)
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"❌ 이미지 인코딩 실패 ({image_path}): {e}")
        return None


# ==============================================================================
# 2. GPT API 호출 (API Request)
# ==============================================================================

def analyze_skin_image(image_path: str) -> dict:
    """
    GPT Vision API에 이미지를 전송하여 피부 상태를 분석합니다.

    Args:
        image_path (str): 분석할 이미지 파일 경로

    Returns:
        dict: 피부 분석 결과 (acne, wrinkles 등) 또는 None
    """
    if not client:
        logger.error("⚠️ OpenAI 클라이언트가 설정되지 않았습니다. (.env 확인 필요)")
        return None

    # 1. 이미지 인코딩
    base64_image = encode_image_to_base64(image_path)
    if not base64_image:
        return None

    try:
        # 2. API 호출
        logger.info(f"📤 GPT 분석 요청 시작 ({GPT_MODEL_NAME})...")

        response = client.chat.completions.create(
            model=GPT_MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": GPT_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 피부 이미지를 분석해서 JSON 포맷으로 점수를 출력해줘."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            max_tokens=1024,
            temperature=0.0,  # 일관된 분석을 위해 0으로 설정
            response_format={"type": "json_object"}  # JSON 응답 강제
        )

        # 3. 응답 처리
        result_text = response.choices[0].message.content
        parsed_result = json.loads(result_text)

        logger.info("✅ GPT 분석 완료")
        return parsed_result

    except Exception as e:
        logger.error(f"⚠️ GPT API 호출 중 오류 발생: {e}")
        return None


# ==============================================================================
# 3. 테스트 코드 (Local Test)
# ==============================================================================
if __name__ == "__main__":
    print("\n🧪 [테스트 모드] gpt_api.py 직접 실행")

    # 테스트할 이미지 경로 (실제 파일이 있어야 함)
    TEST_IMG = "image-data/test/images/acne-5_jpeg.rf.2d6671715f0149df7b494c4d3f12a98b.jpg"

    if os.path.exists(TEST_IMG):
        result = analyze_skin_image(TEST_IMG)
        if result:
            print("\n🎉 분석 결과:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("\n💥 분석 실패 (로그 확인)")
    else:
        print(f"\n⚠️ 테스트 이미지가 없습니다: {TEST_IMG}")
        print("   경로를 수정하거나 파일을 넣어주세요.")