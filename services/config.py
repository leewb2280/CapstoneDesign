# config.py
"""
[전역 설정 및 상수 관리]
서버, 데이터베이스, AI 모델, 비즈니스 로직에서 사용하는 모든 상수를 관리합니다.

목차:
1. SYSTEM & ML : 파일 경로 및 모델 설정
2. LOCALIZATION : 한글 변환 매핑 (카테고리, 태그, 성분)
3. LOGIC RULES : 추천 알고리즘 가중치 설정
4. INFRASTRUCTURE : 데이터베이스 및 외부 API 키 설정
"""

import os
from dotenv import load_dotenv

# .env 파일 로드 (환경변수 설정)
load_dotenv()

# ==============================================================================
# 1. SYSTEM & ML (시스템 및 머신러닝 모델)
# ==============================================================================

# 트러블 예측 모델(.pkl) 파일 경로
# (utils.py의 predict_trouble_proba 함수에서 사용)
MODEL_PATH = "../models/trouble_model.pkl"

# ==============================================================================
# 2. LOCALIZATION (한글 표기 매핑)
# ==============================================================================

# [카테고리 번역] 올리브영 영문 카테고리 -> 한글 표기
CAT_KO = {
    "Sunscreen": "선크림", "Toner": "토너",
    "Serum": "세럼", "Essence": "에센스",
    "Ampoule": "앰플", "Cream": "크림",
    "Gel": "젤 크림", "Balm": "밤",
    "Cleanser": "클렌저", "Cleansing Oil": "오일 클렌저",
    "Cleansing Foam": "폼 클렌저", "Toner Pads": "패드",
    "Sheet Mask": "시트 마스크", "Mask": "마스크",
    "Moisturizer": "보습제", "Lotion": "로션",
    "Emulsion": "에멀전", "Cleansing Gel": "젤 클렌저",
}

# [태그 번역] 제품 특성 태그 -> 한글 표기
TAG_KO = {
    # 기능/효과
    "soothing": "진정", "barrier": "장벽 케어",
    "moisturizing": "보습", "anti-aging": "안티에이징",
    "brightening": "미백", "acne-care": "트러블 케어",
    "sebum": "피지 케어", "pore-care": "모공 케어",

    # 제형/타입
    "light": "가벼운 제형", "rich": "영양감 있는",
    "gel": "젤 타입", "cream": "크림 타입",
    "lotion": "로션 타입", "emulsion": "에멀전",

    # 피부 타입/안전성
    "sensitive": "민감 피부용", "oily-skin": "지성 피부용",
    "non-comedogenic": "논코메도제닉",
    "no-white-cast": "백탁 적음", "spf50": "자외선 차단(강)",
    "fragrance-free": "무향", "alcohol-free": "무알콜",
    "low-alcohol": "저알콜",

    # 성분 관련
    "cica": "시카", "ceramide": "세라마이드",
    "ha": "히알루론산", "hyaluronic": "히알루론산",
    "bha": "BHA(각질제거)", "azelaic": "아젤라익산",
    "niacinamide": "나이아신아마이드", "zinc": "징크",
    "retinoid": "레티노이드", "occlusive": "밀폐 보습",
}

# [성분 번역] 주요 성분 영문명 -> 한글 표기
ING_KO = {
    "hyaluronic acid": "히알루론산",
    "niacinamide": "나이아신아마이드",
    "ceramide": "세라마이드",
    "centella asiatica": "센텔라(병풀)",
    "madecassoside": "마데카소사이드",
    "panthenol": "판테놀",
    "allantoin": "알란토인",
    "salicylic acid": "살리실산(BHA)",
    "glycolic acid": "글리콜산(AHA)",
    "alpha-arbutin": "알파-알부틴",
    "rice extract": "쌀 추출물",
    "probiotics": "프로바이오틱스",
    "tea tree": "티트리",
    "green tangerine extract": "청귤 추출물",
}

# ==============================================================================
# 3. LOGIC RULES (추천 엔진 규칙)
# ==============================================================================

# [가중치 설정] analysis_logic.py에서 점수 계산 시 사용
RULES = {
    # [환경 규칙] 날씨 데이터(UV, 습도, 기온)에 따른 가중치
    "env_rules": {
        "uv": {
            "low": {"SPF30": 5},
            "mod": {"SPF30": 15},
            "high": {"SPF50": 30},
            "very": {"SPF50": 35},
        },
        "humidity": {
            "dry": {"Rich_Moist": 20, "Occlusive": 10},
            "humid": {"Light_Gel": 20},
        },
        "temp": {
            "hot": {"SebumGel": 15},
            "cold": {"BarrierCream": 15},
        },
    },

    # [피부 규칙] 측정된 피부 상태(유분, 트러블 등)에 따른 가중치
    "skin_rules": {
        "sebum_high":   {"SebumGel": 15, "Heavy_Oil": -10},
        "acne_high":    {"BHA_Azelaic": 20, "Occlusive": -5},
        "redness_high": {"SoothingFF": 15, "Strong_Acid": -20},
        "wrinkle_high": {"Retinol_PM": 40, "Rich_Moist": 20},
        "dryness_high": {"Ceramide_HA": 20},
    },

    # [안전 규칙] 특정 조건에서 추천 제외(Blacklist)
    "safety": {
        "night_only": ["Retinol_PM"],  # 밤에만 써야 하는 성분
        "ban_if_sensitive": [  # 민감성 피부일 때 제외할 성분
            "Strong_Acid", "High_Retinol", "High_Alcohol", "Fragrance",
        ],
    },
}

# ==============================================================================
# 4. INFRASTRUCTURE (DB & API)
# ==============================================================================

# [데이터 검증] 올리브영 데이터 로딩 시 허용할 공식 카테고리 화이트리스트
ALLOWED_OFFICIAL_CATS = {
    "Toner", "Serum", "Essence", "Ampoule", "Cream", "Lotion",
    "Gel", "Balm", "Sunscreen", "Cleanser", "Oil Cleanser",
    "Toner Pads", "Mask", "Sheet Mask", "Moisturizer",
    "Emulsion", "Cleansing Foam", "Cleansing Gel", "Cleansing Oil",
}

# [데이터베이스] PostgreSQL 접속 정보 (환경변수 우선)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "port": os.getenv("DB_PORT", "5432")
}

# [OpenAI] GPT 모델 설정
GPT_MODEL_NAME = "gpt-4o-mini"

# [OpenAI] 시스템 프롬프트 (피부 분석관 페르소나)
GPT_SYSTEM_PROMPT = """
너는 피부과 전문의처럼 작동하는 AI 분석가야.
사용자가 이미지를 주면, 1에서 100까지의 수치로 피부 상태를 평가해.
(1은 '매우 좋음/없음', 100은 '매우 심각함/많음'을 의미함).

반드시 다음 5가지 키를 포함한 JSON 객체 형식으로만 응답해야 해.
다른 설명이나 텍스트는 절대 추가하지 마.

{
  "acne": [여드름/뾰루지 점수],
  "wrinkles": [눈에 띄는 주름 점수],
  "pores": [눈에 띄는 모공 점수],
  "pigmentation": [색소침착/잡티 점수],
  "redness": [홍조/붉은기 점수]
}
"""

# ==============================================================================
# 5. SKIN ANALYSIS CRITERIA (피부 진단 기준값)
# ==============================================================================

SKIN_THRESHOLDS = {
    "dry_limit": 30.0,       # 수분 30 미만 (건성)
    "oily_limit": 70.0,      # 유분 70 초과 (지성)
    "sensitive_limit": 50.0, # 홍조 50 초과 (민감성)
    "pore_limit": 60.0,      # 모공 60 초과 (모공 고민)
    "acne_limit": 50.0,      # 트러블 50 초과 (트러블성) [추가됨]
    "wrinkle_limit": 50.0    # 주름 50 초과 (탄력 저하) [추가됨]
}