# data_collector.py
import pandas as pd
import time
from naver_api import get_naver_shopping_data  # 1단계에서 만든 파일 import

# ==========================================
# 1. 검색 키워드 설정 (분석 로직이 이해하는 카테고리명: 검색어 리스트)
# ==========================================
SEARCH_KEYWORDS = {
    "Sunscreen": ["선크림", "무기자차", "유기자차", "선스틱"],
    "Toner": ["토너", "닦토", "스킨", "진정 토너"],
    "Serum": ["세럼", "앰플", "잡티 세럼", "수분 앰플"],
    "Cream": ["수분크림", "시카크림", "장벽크림", "재생크림"],
    "Cleanser": ["약알칼리 클렌징폼", "약산성 클렌징", "여드름 폼클렌징"],
    "Mask": ["마스크팩", "진정 팩", "수분 팩"],
    "Lotion": ["로션", "에멀전"]
}

# ==========================================
# 2. 자동 태깅 규칙 (제목에 단어가 포함되면 -> 성분/태그 자동 입력)
# ==========================================
AUTO_TAG_RULES = {
    # [진정/트러블]
    "티트리": {"ing": "tea tree", "tag": "acne-care"},
    "시카": {"ing": "cica", "tag": "soothing"},
    "병풀": {"ing": "centella asiatica", "tag": "soothing"},
    "어성초": {"ing": "heartleaf", "tag": "soothing"},
    "진정": {"ing": "", "tag": "soothing"},

    # [보습/장벽]
    "히알루론": {"ing": "hyaluronic acid", "tag": "moisturizing"},
    "세라마이드": {"ing": "ceramide", "tag": "barrier"},
    "판테놀": {"ing": "panthenol", "tag": "barrier"},
    "장벽": {"ing": "", "tag": "barrier"},
    "보습": {"ing": "", "tag": "moisturizing"},

    # [기능성]
    "비타민": {"ing": "vitamin c", "tag": "brightening"},
    "미백": {"ing": "niacinamide", "tag": "brightening"},
    "주름": {"ing": "adenosine", "tag": "anti-aging"},
    "레티놀": {"ing": "retinol", "tag": "anti-aging"},
    "탄력": {"ing": "collagen", "tag": "anti-aging"},

    # [피부타입/제형]
    "지성": {"ing": "", "tag": "oily-skin"},
    "건성": {"ing": "", "tag": "rich"},
    "모공": {"ing": "", "tag": "pore-care"},
    "약산성": {"ing": "", "tag": "low-irritation"},
    "저자극": {"ing": "", "tag": "sensitive"}
}


def analyze_tags(title):
    """제목을 분석해 성분과 태그 리스트를 생성"""
    ings = []
    tags = []
    title_n = title.replace(" ", "")  # 띄어쓰기 없이도 검색

    for keyword, data in AUTO_TAG_RULES.items():
        if keyword in title or keyword in title_n:
            if data["ing"]: ings.append(data["ing"])
            if data["tag"]: tags.append(data["tag"])

    return list(set(ings)), list(set(tags))


def main():
    all_data = []
    print("🚀 데이터 수집을 시작합니다...")

    for category, keywords in SEARCH_KEYWORDS.items():
        for kw in keywords:
            print(f"   🔎 [{category}] '{kw}' 검색 중...")

            # naver_api를 통해 40개씩 수집
            items = get_naver_shopping_data(kw, display=40)

            if not items: continue

            for item in items:
                title = item['title']
                price = item['lprice']
                link = item['link']
                image = item['image']
                brand = item.get('brand', 'Unknown')

                # 태그 자동 분석
                ings, tags = analyze_tags(title)

                # 선크림은 기본적으로 SPF50 태그 추가 (요즘 대부분 50이라 가정)
                if category == "Sunscreen": tags.append("spf50")

                # 결과 데이터 구조 (기존 CSV와 호환)
                product = {
                    "name": title,
                    "price": price,
                    "brand": brand,
                    "official_category": category,
                    "tags": str(tags),  # 리스트를 문자열로 변환 "[...]"
                    "featured_ingredients": str(ings),
                    "url": link,
                    "image_url": image
                }
                all_data.append(product)

            time.sleep(0.3)  # API 과부하 방지 딜레이

    # CSV 저장
    df = pd.DataFrame(all_data)

    # 이름 중복 제거 (여러 키워드에 걸린 제품 삭제)
    df = df.drop_duplicates(subset=["name"])

    filename = "expanded_product_db.csv"
    df.to_csv(filename, index=False, encoding="utf-8-sig")

    print(f"\n✅ 수집 완료! 총 {len(df)}개의 제품 데이터가 저장되었습니다.")
    print(f"📂 파일명: {filename}")


if __name__ == "__main__":
    main()