# gpt_api.py
"""
[GPT API 통신 담당]
OpenAI API와 통신하는 모든 기능을 전담하는 모듈입니다.

기능:
1. analyze_skin_image: 피부 사진 분석 (Vision)
3. analyze_batch_product_tags: 제품 여러 개 배치 분석 (Chat Batch)
"""

import os
import json
import base64
import logging
from openai import OpenAI
from dotenv import load_dotenv

# 설정 파일 로드
from .config import GPT_MODEL_NAME, GPT_SYSTEM_PROMPT, STANDARD_TAGS, STANDARD_INGREDIENTS

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
# 1. 이미지 처리 및 분석 (Vision)
# ==============================================================================

def encode_image_to_base64(image_path: str) -> str:
    """이미지 파일을 Base64 문자열로 변환"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"❌ 이미지 인코딩 실패 ({image_path}): {e}")
        return None


def analyze_skin_image(image_path: str) -> dict:
    """GPT Vision API에 이미지를 전송하여 피부 상태를 분석합니다."""
    if not client: return None

    base64_image = encode_image_to_base64(image_path)
    if not base64_image: return None

    try:
        logger.info(f"📤 GPT 피부 분석 요청 시작...")
        response = client.chat.completions.create(
            model=GPT_MODEL_NAME,
            messages=[
                {"role": "system", "content": GPT_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 피부를 분석해서 JSON 형식으로 점수를 알려줘."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        logger.error(f"⚠️ GPT 피부 분석 실패: {e}")
        return None


# ==============================================================================
# 2. 텍스트 분석 (Chat Completion)
# ==============================================================================

def analyze_batch_product_tags(batch_data: list) -> dict:
    """
    [배치 처리용] 제품 리스트(여러 개)를 받아 한 번에 태그를 분석합니다.

    Args:
        batch_data (list): [(id, name, category), ...] 형태의 튜플 리스트

    Returns:
        dict: { "제품ID": {"tags": [], "ingredients": []}, ... }
    """
    if not client: return {}

    # 프롬프트 구성을 위한 문자열 변환
    items_str = "\n".join([f"- ID:{p[0]} Name:{p[1]} Cat:{p[2]}" for p in batch_data])
    
    # 허용된 태그/성분 리스트 문자열 변환
    allowed_tags_str = ", ".join(STANDARD_TAGS)
    allowed_ings_str = ", ".join(STANDARD_INGREDIENTS)

    prompt = f"""
    Analyze these skincare products.
    {items_str}

    Task: Extract 'ingredients' and select 'tags' for each product.
    
    IMPORTANT RULES:
    1. You MUST ONLY use tags from this allowed list: [{allowed_tags_str}]
    2. You MUST ONLY use ingredients from this allowed list: [{allowed_ings_str}]
    3. If a product has no relevant tags or ingredients from the list, return empty arrays.
    4. Do not invent new tags or ingredients.
    
    Return JSON: {{ "ID": {{"tags": [], "ingredients": []}} }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a skincare data analyst."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        logger.error(f"⚠️ GPT 배치 분석 실패: {e}")
        return {}