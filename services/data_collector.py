# data_collector.py
"""
[데이터 수집기]
네이버 쇼핑 API를 통해 최신 화장품 데이터를 수집하고,
자동 태깅 분석을 거쳐 PostgreSQL DB('products' 테이블)에 저장하는 모듈입니다.

사용법:
1. 직접 실행: python data_collector.py
2. 외부 호출: main.py (관리자 API)에서 run_data_collection() 호출
"""

import time
import json
import logging
import psycopg2
from dotenv import load_dotenv

# 외부 모듈
from .naver_api import get_naver_shopping_data
from .config import DB_CONFIG

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ==============================================================================
# 1. 수집 규칙 및 태그 설정 (Configuration)
# ==============================================================================

# [검색 키워드] 카테고리별 검색어 리스트
SEARCH_KEYWORDS = {
    "Sunscreen": ["선크림", "무기자차", "유기자차", "선스틱"],
    "Toner": ["토너", "닦토", "스킨", "진정 토너"],
    "Serum": ["세럼", "앰플", "잡티 세럼", "수분 앰플"],
    "Cream": ["수분크림", "시카크림", "장벽크림", "재생크림"],
    "Cleanser": ["약알칼리 클렌징폼", "약산성 클렌징", "여드름 폼클렌징"],
    "Mask": ["마스크팩", "진정 팩", "수분 팩"],
    "Lotion": ["로션", "에멀전"]
}

# [자동 태깅 규칙] 제품명에 특정 단어가 포함되면 태그/성분 자동 추가
AUTO_TAG_RULES = {
    # 성분 관련
    "티트리": {"ing": "tea tree", "tag": "acne-care"},
    "시카": {"ing": "cica", "tag": "soothing"},
    "병풀": {"ing": "centella asiatica", "tag": "soothing"},
    "어성초": {"ing": "heartleaf", "tag": "soothing"},
    "히알루론": {"ing": "hyaluronic acid", "tag": "moisturizing"},
    "세라마이드": {"ing": "ceramide", "tag": "barrier"},
    "판테놀": {"ing": "panthenol", "tag": "barrier"},
    "비타민": {"ing": "vitamin c", "tag": "brightening"},
    "미백": {"ing": "niacinamide", "tag": "brightening"},
    "주름": {"ing": "adenosine", "tag": "anti-aging"},
    "레티놀": {"ing": "retinol", "tag": "anti-aging"},
    "탄력": {"ing": "collagen", "tag": "anti-aging"},

    # 효과/타입 관련
    "진정": {"ing": "", "tag": "soothing"},
    "장벽": {"ing": "", "tag": "barrier"},
    "보습": {"ing": "", "tag": "moisturizing"},
    "지성": {"ing": "", "tag": "oily-skin"},
    "건성": {"ing": "", "tag": "rich"},
    "모공": {"ing": "", "tag": "pore-care"},
    "약산성": {"ing": "", "tag": "low-irritation"},
    "저자극": {"ing": "", "tag": "sensitive"}
}


# ==============================================================================
# 2. 데이터 분석 로직 (Analysis Logic)
# ==============================================================================

def analyze_tags(title: str) -> tuple:
    """
    제품 제목(title)을 분석하여 성분(ingredients)과 태그(tags) 리스트를 추출합니다.

    Returns:
        tuple: (성분 리스트, 태그 리스트)
    """
    ings = []
    tags = []
    title_n = title.replace(" ", "")  # 띄어쓰기 무시하고 검색하기 위함

    for keyword, data in AUTO_TAG_RULES.items():
        if keyword in title or keyword in title_n:
            if data["ing"]: ings.append(data["ing"])
            if data["tag"]: tags.append(data["tag"])

    return list(set(ings)), list(set(tags))


# ==============================================================================
# 3. 데이터베이스 저장 (DB Handling)
# ==============================================================================

def save_products_to_db(product_list: list):
    """
    수집된 제품 리스트를 DB에 저장합니다.
    (주의: 기존 데이터를 모두 삭제(TRUNCATE)하고 새로 채워 넣습니다)
    """
    if not product_list:
        logger.warning("⚠️ 저장할 데이터가 없습니다.")
        return

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. 테이블 생성 (없으면 생성)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER,
                brand TEXT,
                official_category TEXT,
                tags TEXT, 
                featured_ingredients TEXT,
                url TEXT,
                image_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. 기존 데이터 초기화 (TRUNCATE)
        cursor.execute("TRUNCATE TABLE products RESTART IDENTITY;")

        # 3. 데이터 일괄 삽입
        insert_query = """
            INSERT INTO products 
            (name, price, brand, official_category, tags, featured_ingredients, url, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        count = 0
        for p in product_list:
            # 리스트 -> JSON 문자열 변환
            tags_json = json.dumps(p["tags"], ensure_ascii=False)
            ings_json = json.dumps(p["featured_ingredients"], ensure_ascii=False)

            cursor.execute(insert_query, (
                p["name"],
                p["price"],
                p["brand"],
                p["official_category"],
                tags_json,
                ings_json,
                p["url"],
                p["image_url"]
            ))
            count += 1

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"✅ DB 저장 완료! 총 {count}개의 제품이 등록되었습니다.")

    except Exception as e:
        logger.error(f"❌ DB 저장 중 오류 발생: {e}")


# ==============================================================================
# 4. 메인 실행 로직 (Main Execution)
# ==============================================================================

def run_data_collection():
    """
    [진입점] 네이버 쇼핑 API를 순회하며 데이터를 수집하고 DB에 저장합니다.
    """
    all_data = []
    seen_names = set()  # 중복 제거용

    logger.info("🚀 [관리자 요청] 데이터 수집 및 업데이트 시작...")

    # 카테고리별 키워드 순회
    for category, keywords in SEARCH_KEYWORDS.items():
        for kw in keywords:
            logger.info(f"   🔎 [{category}] '{kw}' 검색 중...")

            # API 호출 (40개씩 수집)
            items = get_naver_shopping_data(kw, display=40)
            if not items:
                continue

            for item in items:
                title = item['title']

                # 중복 제품 필터링
                if title in seen_names:
                    continue
                seen_names.add(title)

                # 데이터 추출
                price = int(item['lprice'])
                link = item['link']
                image = item['image']
                brand = item.get('brand', 'Unknown')

                # 태그/성분 분석
                ings, tags = analyze_tags(title)

                # 카테고리별 특수 태그 추가
                if category == "Sunscreen":
                    tags.append("spf50")

                # 데이터 구조화
                product = {
                    "name": title,
                    "price": price,
                    "brand": brand,
                    "official_category": category,
                    "tags": tags,
                    "featured_ingredients": ings,
                    "url": link,
                    "image_url": image
                }
                all_data.append(product)

            # API 과부하 방지 딜레이
            time.sleep(0.3)

    # 수집 종료 후 DB 저장
    save_products_to_db(all_data)
    logger.info("✨ [관리자 요청] 모든 작업이 완료되었습니다.")


# ==============================================================================
# 5. 직접 실행 시 (Local Test)
# ==============================================================================
if __name__ == "__main__":
    run_data_collection()