# naver_api.py
import requests
import re
import os
from dotenv import load_dotenv

# .env 파일에서 API 키 로드 (보안 필수)
load_dotenv()

CLIENT_ID = os.getenv("NAVER_CLIENT_ID")  # .env 파일에 정의되어 있어야 함
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")  # .env 파일에 정의되어 있어야 함


def clean_html(text):
    """HTML 태그(<b> 등)를 제거하는 헬퍼 함수"""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', text)


def get_naver_shopping_data(keyword, display=10, sort="sim"):
    """
    특정 키워드로 네이버 쇼핑을 검색하고 결과 리스트를 반환합니다.
    :param keyword: 검색어 (예: "시카 크림")
    :param display: 가져올 개수 (최대 100)
    :param sort: 정렬 순서 (sim:정확도순, date:날짜순, asc:가격오름차순)
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        print("⚠️ 오류: .env 파일에 네이버 API 키가 설정되지 않았습니다.")
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
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            items = response.json().get('items', [])
            # 가져온 데이터의 제목에서 HTML 태그 미리 제거
            for item in items:
                item['title'] = clean_html(item['title'])
            return items
        else:
            print(f"⚠️ API 요청 실패 (Code: {response.status_code})")
            return []

    except Exception as e:
        print(f"⚠️ API 연결 중 에러 발생: {e}")
        return []


# (테스트용) 이 파일을 직접 실행했을 때만 작동
if __name__ == "__main__":
    print("🔵 네이버 API 테스트 중...")
    results = get_naver_shopping_data("선크림", display=3)
    for item in results:
        print(f"- {item['title']} ({item['lprice']}원)")