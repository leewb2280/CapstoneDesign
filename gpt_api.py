# gpt_api.py
"""
[GPT API 통신 담당]
이 파일은 OpenAI API와 통신하여 이미지를 분석하는 기능만 전담합니다.
다른 파일(skin_analyzer.py 등)에서 이 파일을 import해서 사용합니다.
"""

import base64
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# config에서 모델명과 프롬프트 가져오기
from config import GPT_MODEL_NAME, GPT_SYSTEM_PROMPT

# API 키 로드
load_dotenv()
client = OpenAI()


def encode_image_to_base64(image_path):
    """이미지 파일을 Base64 문자열로 변환"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"❌ 이미지 인코딩 실패: {e}")
        return None


def analyze_skin_image(image_path):
    """
    GPT Vision API에 이미지를 전송하고 분석 결과를 반환합니다.
    Returns:
        dict: 피부 상태 점수 (acne, wrinkles 등) 또는 None
    """
    base64_image = encode_image_to_base64(image_path)
    if not base64_image:
        return None

    try:
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
                        {"type": "text", "text": "이 피부를 분석해서 JSON 형식으로 점수를 알려줘."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=1024,
            response_format={"type": "json_object"}  # JSON 모드 강제 (모델 지원 시)
        )

        # 응답 텍스트를 파이썬 딕셔너리로 변환
        result_text = response.choices[0].message.content
        return json.loads(result_text)

    except Exception as e:
        print(f"⚠️ GPT API 호출 중 오류 발생: {e}")
        return None


# (테스트용) 이 파일을 직접 실행할 때만 동작
if __name__ == "__main__":
    # 테스트할 이미지 경로를 넣어보세요
    test_path = "test_image.jpg"
    if os.path.exists(test_path):
        print(analyze_skin_image(test_path))
    else:
        print("테스트할 이미지가 없습니다.")