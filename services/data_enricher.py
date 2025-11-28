# data_enricher.py
"""
[데이터 보강 통합 모듈]
수집된 제품 데이터의 태그와 성분 정보를 보강합니다.
1단계: Regex(정규표현식)로 빠르고 무료로 분석 (로컬)
2단계: 정보가 부족한 제품만 골라서 GPT에게 분석 요청 (API)
"""

import re
import json
import time
import logging
import psycopg2
from dotenv import load_dotenv

from .config import DB_CONFIG, STANDARD_TAGS, STANDARD_INGREDIENTS
from .gpt_api import analyze_batch_product_tags

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# [최적화] 배치 사이즈 50으로 증가 (속도 향상)
BATCH_SIZE = 50

# ==============================================================================
# [PART 1] Regex 패턴 정의 (단어장)
# ==============================================================================
# config.py의 STANDARD_TAGS, STANDARD_INGREDIENTS에 정의된 키로 매핑합니다.
PATTERNS = {
    "ingredients": {
        "teatree": r"티트리|tea\s?tree",
        "cica": r"시카|병풀|센텔라|마데카|cica|centella",
        "heartleaf": r"어성초|약모밀|heartleaf",
        "mugwort": r"쑥|사철쑥|인진쑥|mugwort|artemisia",
        "hyaluronic": r"히알루론|하이드라|수분|hyaluronic",
        "ceramide": r"세라마이드|세라|ceramide",
        "panthenol": r"판테놀|panthenol",
        "propolis": r"프로폴리스|꿀|로얄젤리|propolis",
        "vitamin-c": r"비타민|비타민C|잡티|청귤|유자|vita",
        "niacinamide": r"나이아신|미백|niacin",
        "retinol": r"레티놀|레티날|retinol|retinal",
        "collagen": r"콜라겐|탄력|collagen",
        "bha": r"바하|살리실산|bha|salicylic",
        "aha": r"아하|글라이콜릭|aha|glycolic",
        "shea-butter": r"쉐어버터|shea\s?butter",
        "azelaic": r"아젤라익|azelaic",
        "pha": r"파하|pha"
    },
    "tags": {
        "soothing": r"진정|수딩|쿨링|시카|티트리|어성초",
        "moisturizing": r"보습|수분|물광|촉촉|히알루론",
        "barrier": r"장벽|판테놀|세라마이드|재생",
        "brightening": r"미백|톤업|브라이트닝|잡티|비타민|화이트닝",
        "anti-aging": r"주름|탄력|안티에이징|리프팅|노화|레티놀",
        "acne-care": r"트러블|여드름|아크네|진정|티트리",
        "pore-care": r"모공|피지|블랙헤드",
        "sebum-care": r"피지|개기름|산뜻",
        "spf": r"선크림|선블록|선스틱|자차|spf|pa\+",
        "hydration": r"수분|hydration",
        "firming": r"탄력|firming",
        "sensitive-skin": r"민감|저자극|순한|약산성",
        "oily-skin": r"지성|피지|개기름|산뜻|가벼운",
        "dry-skin": r"건성|속건조|당김",
        "vegan": r"비건|vegan",
        "low-ph": r"약산성|low\s?ph",
        "hypoallergenic": r"저자극|hypoallergenic",
        "fragrance-free": r"무향|fragrance\s?free",
        "alcohol-free": r"무알콜|alcohol\s?free",
        "light": r"가벼운|산뜻|light",
        "rich": r"영양|rich|꾸덕",
        "gel": r"젤|gel",
        "cream": r"크림|cream",
        "watery": r"워터|watery|물",
        "oil": r"오일|oil",
        "balm": r"밤|balm",
        "fresh": r"상쾌|fresh"
    }
}


def analyze_text_local(text):
    """Regex 엔진: 텍스트에서 성분과 태그 추출"""
    found_ings = set()
    found_tags = set()
    text_lower = text.lower()

    for ing_name, pattern in PATTERNS["ingredients"].items():
        if ing_name in STANDARD_INGREDIENTS and re.search(pattern, text_lower):
            found_ings.add(ing_name)

    for tag_name, pattern in PATTERNS["tags"].items():
        if tag_name in STANDARD_TAGS and re.search(pattern, text_lower):
            found_tags.add(tag_name)

    return list(found_ings), list(found_tags)


# ==============================================================================
# [PART 2] 1단계: Regex 일괄 처리
# ==============================================================================
def enrich_with_regex():
    logger.info("🔹 [Phase 1] Regex 엔진 가동 (Local Processing)...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, official_category FROM products")
        products = cursor.fetchall()

        updates = []
        count = 0

        for p in products:
            p_id, name, cat = p

            ings, tags = analyze_text_local(name)
            if cat == "Sunscreen": tags.append("spf50")

            ings = list(set(ings))
            tags = list(set(tags))

            if ings or tags:
                updates.append((json.dumps(tags), json.dumps(ings), p_id))
                count += 1

        if updates:
            sql = "UPDATE products SET tags = %s, featured_ingredients = %s WHERE id = %s"
            cursor.executemany(sql, updates)
            conn.commit()

        logger.info(f"✅ Regex 완료: {count}개 제품 정보 1차 보강됨.")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Regex 단계 실패: {e}")


# ==============================================================================
# [PART 3] 2단계: GPT 엔진 (gpt_api 모듈 사용)
# ==============================================================================

def get_poor_data_products():
    """태그가 부족한 제품 조회 (카테고리별 정렬)"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
            SELECT id, name, official_category, tags, featured_ingredients 
            FROM products 
            ORDER BY official_category, id
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        targets = []
        for r in rows:
            tags = json.loads(r[3]) if r[3] else []
            if len(tags) < 2:
                targets.append(r)  # 전체 row를 다 넣음

        cursor.close()
        conn.close()
        return targets
    except Exception as e:
        logger.error(f"Target 조회 실패: {e}")
        return []


def enrich_with_gpt():
    logger.info("🔹 [Phase 2] GPT 엔진 가동 (AI Processing)...")

    targets = get_poor_data_products()
    total = len(targets)
    logger.info(f"📋 GPT 보강 대상: {total}개")

    if total == 0: return

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 배치 처리 (50개씩)
    for i in range(0, total, BATCH_SIZE):
        batch = targets[i: i + BATCH_SIZE]
        logger.info(f"   🔄 Batch {i // BATCH_SIZE + 1} Processing ({len(batch)} items)...")

        # [수정] 직접 호출 대신 gpt_api 모듈의 함수 사용!
        # batch는 (id, name, cat, ...) 튜플이므로 앞의 3개만 잘라서 보냄
        batch_input = [(p[0], p[1], p[2]) for p in batch]
        gpt_res = analyze_batch_product_tags(batch_input)

        updates = []
        for p in batch:
            p_id = str(p[0])
            if p_id in gpt_res:
                data = gpt_res[p_id]

                old_tags = json.loads(p[3]) if p[3] else []
                old_ings = json.loads(p[4]) if p[4] else []

                new_tags = list(set(old_tags + data.get("tags", [])))
                new_ings = list(set(old_ings + data.get("ingredients", [])))

                # 업데이트 쿼리 준비
                updates.append((json.dumps(new_tags), json.dumps(new_ings), p[0]))

        # DB 저장
        if updates:
            cursor.executemany(
                "UPDATE products SET tags=%s, featured_ingredients=%s WHERE id=%s",
                updates
            )
            conn.commit()

        time.sleep(0.5)

    cursor.close()
    conn.close()
    logger.info("✅ GPT 보강 완료!")


# ==============================================================================
# [MAIN] 실행 컨트롤러
# ==============================================================================
def run_hybrid_enrichment():
    enrich_with_regex()  # 1차
    enrich_with_gpt()  # 2차
    logger.info("🎉 [데이터 최적화 완료] 모든 프로세스 종료")


if __name__ == "__main__":
    run_hybrid_enrichment()
