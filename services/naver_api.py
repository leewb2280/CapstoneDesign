# naver_api.py
"""
[네이버 쇼핑 API 통신 담당]
네이버 개발자 센터(OpenAPI)를 통해 쇼핑 검색 결과를 가져오는 모듈입니다.
data_collector.py에서 이 모듈을 호출하여 화장품 데이터를 수집합니다.
"""

import os
import re
import logging
import requests
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수 로드
load_dotenv()

# .env 파일에서 API 키 로드
CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")


# ==============================================================================
# 1. 헬퍼 함수 (Helper Functions)
# ==============================================================================

def clean_html(text: str) -> str:
    """
    문자열에 포함된 HTML 태그(<b>, </b> 등)를 제거합니다.
    네이버 API 검색 결과는 검색어에 <b> 태그가 붙어서 오기 때문입니다.
    """
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', text)


# ==============================================================================
# 2. API 호출 함수 (API Request)
# ==============================================================================

def get_naver_shopping_data(keyword: str, display: int = 10, sort: str = "sim") -> list:
    """
    특정 키워드로 네이버 쇼핑을 검색하고 결과 리스트를 반환합니다.

    Args:
        keyword (str): 검색어 (예: "시카 크림")
        display (int): 가져올 결과 개수 (최대 100)
        sort (str): 정렬 순서 ('sim': 정확도순, 'date': 날짜순, 'asc': 가격오름차순)

    Returns:
        list: 검색된 제품 정보 딕셔너리 리스트 (실패 시 빈 리스트 [])
    """
    # 1. API 키 검증
    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("⚠️ .env 파일에 네이버 API 키(CLIENT_ID/SECRET)가 설정되지 않았습니다.")
        return []

    url = "https://openapi.naver.com/v1/search/shop.json"

    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }

    params = {
        "query": keyword,
        "display": display,
        "sort": sort
    }

    try:
        # 2. 요청 전송
        response = requests.get(url, headers=headers, params=params, timeout=5)

        # 3. 응답 처리
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])

            # HTML 태그 제거 전처리
            for item in items:
                item['title'] = clean_html(item['title'])

            return items

        else:
            logger.error(f"⚠️ API 요청 실패 (Status Code: {response.status_code})")
            logger.error(f"   응답 내용: {response.text}")
            return []

    except Exception as e:
        logger.error(f"⚠️ API 연결 중 에러 발생: {e}")
        return []


# ==============================================================================
# 3. 테스트 코드 (Local Test)
# ==============================================================================
if __name__ == "__main__":
    print("\n🔵 [테스트 모드] naver_api.py 직접 실행")

    test_keyword = "무기자차 선크림"
    print(f"🔎 검색어 '{test_keyword}' 로 테스트를 진행합니다...")

    results = get_naver_shopping_data(test_keyword, display=3)

    if results:
        print(f"\n✅ {len(results)}개의 결과를 가져왔습니다:")
        for idx, item in enumerate(results, 1):
            print(f"   {idx}. {item['title']} ({item['lprice']}원)")
    else:
        print("\n❌ 검색 결과가 없거나 API 호출에 실패했습니다.")