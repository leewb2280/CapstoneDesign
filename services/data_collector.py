# data_collector.py
"""
[데이터 수집기 - Pure Collector]
네이버 쇼핑 API에서 데이터를 긁어와 DB에 저장하는 역할만 수행합니다.
태그 분석 로직은 data_enricher.py로 모두 이관되었습니다.
"""

import time
import json
import logging
import psycopg2
from dotenv import load_dotenv

# 외부 모듈
from .naver_api import get_naver_shopping_data
from .config import DB_CONFIG
from .data_enricher import run_hybrid_enrichment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# 검색 키워드 설정 (config.py의 것을 쓰거나 여기서 정의)
# 편의상 여기에 둠 (확장된 키워드 리스트 유지)
SEARCH_KEYWORDS = {
    "Sunscreen": ["선크림", "무기자차", "선스틱", "톤업 선크림"],
    "Toner": ["토너", "닦토", "진정 토너", "약산성 스킨"],
    "Serum": ["세럼", "수분 앰플", "잡티 세럼", "비타민 앰플", "레티놀"],
    "Cream": ["수분크림", "시카크림", "장벽크림", "탄력 크림", "재생크림"],
    "Cleanser": ["클렌징폼", "약산성 클렌징", "클렌징 오일"],
    "Mask": ["마스크팩", "진정 팩", "수분 팩", "모델링팩"],
    "Lotion": ["로션", "에멀전", "올인원"]
}


def save_products_raw(product_list):
    """수집된 데이터를 DB에 저장 (태그는 비워둠)"""
    if not product_list: return

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER,
                brand TEXT,
                official_category TEXT,
                tags TEXT DEFAULT '[]', 
                featured_ingredients TEXT DEFAULT '[]',
                url TEXT,
                image_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 기존 데이터 삭제 후 갱신
        cursor.execute("TRUNCATE TABLE products RESTART IDENTITY;")

        insert_sql = """
            INSERT INTO products (name, price, brand, official_category, url, image_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        count = 0
        for p in product_list:
            cursor.execute(insert_sql, (
                p["name"], p["price"], p["brand"],
                p["official_category"], p["url"], p["image_url"]
            ))
            count += 1

        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"✅ [수집 완료] 총 {count}개 제품 저장됨 (태그 미분석 상태)")

    except Exception as e:
        logger.error(f"DB 저장 실패: {e}")


def run_data_collection():
    logger.info("🚀 [1단계] 데이터 수집 시작...")
    all_data = []
    seen_names = set()

    for category, keywords in SEARCH_KEYWORDS.items():
        for kw in keywords:
            items = get_naver_shopping_data(kw, display=40)
            if not items: continue

            for item in items:
                title = item['title']
                if title in seen_names: continue
                seen_names.add(title)

                # 태그 분석 없이 기본 정보만 저장
                product = {
                    "name": title,
                    "price": int(item['lprice']),
                    "brand": item.get('brand', 'Unknown'),
                    "official_category": category,
                    "url": item['link'],
                    "image_url": item['image']
                }
                all_data.append(product)
            time.sleep(0.2)

    # 1. 저장 (Raw Data)
    save_products_raw(all_data)

    # 2. 보강 (Hybrid Enrichment) 바로 실행
    logger.info("🚀 [2단계] 하이브리드 데이터 보강 시작 (Regex -> GPT)")
    run_hybrid_enrichment()


if __name__ == "__main__":
    run_data_collection()