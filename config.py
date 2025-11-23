# config.py
"""
[전역 설정 및 상수 관리]
이 파일은 프로그램 전체에서 사용하는 모든 설정값, 규칙, 텍스트 매핑을 관리합니다.
코드 로직 없이 '데이터'만 담고 있어 유지보수가 쉽습니다.

1. 파일 경로: 로그, 데이터, 모델 파일의 위치 정의
2. 한글 매핑: 영어로 된 카테고리/성분을 사용자 친화적인 한글로 변환
3. 추천 규칙: 날씨/피부 상태에 따른 가점/감점 로직 정의
4. UI 설정: 사용자에게 물어볼 질문 리스트 정의
5. DB/API 설정: PostgreSQL 및 OpenAI 연결 정보
"""

import os
from dotenv import load_dotenv

# .env 파일 로드 (API 키, DB 비밀번호 등 보안 정보)
load_dotenv()

# =========================================
# 1. 파일 경로 설정 (File Paths)
# =========================================
# 프로그램이 읽거나 쓰는 파일들의 경로를 상수화합니다.
USER_PREFS_JSON = "user_prefs.json"       # 사용자 선호도 저장
LIFESTYLE_JSON = "lifestyle.json"         # 생활습관 저장
LOG_PATH = "weekly_log.csv"               # ML 학습용 로그 데이터
MODEL_PATH = "trouble_model.pkl"          # 학습된 트러블 예측 모델
CSV_DATA_PATH = "expanded_product_db.csv" # 제품 데이터베이스
WEEKLY_TREND_IMG = "weekly_trend.png"     # (옵션) 그래프 이미지
RESULT_JSON_PATH = "today_result.json"    # 최종 결과 JSON 저장 경로


# =========================================
# 2. 번역 및 표기 매핑 (English -> Korean)
# =========================================

# [카테고리 번역]
# 올리브영 데이터(영어) -> 사용자 출력용(한글)
CAT_KO = {
    "Sunscreen": "선크림",
    "Toner": "토너",
    "Serum": "세럼",
    "Essence": "에센스",
    "Ampoule": "앰플",
    "Cream": "크림",
    "Gel": "젤 크림",
    "Balm": "밤",
    "Cleanser": "클렌저",
    "Cleansing Oil": "오일 클렌저",
    "Cleansing Foam": "폼 클렌저",
    "Toner Pads": "패드",
    "Sheet Mask": "시트 마스크",
    "Mask": "마스크",
    "Moisturizer": "보습제",
    "Lotion": "로션",
    "Emulsion": "에멀전",
    "Cleansing Gel": "젤 클렌저",
}

# [태그 번역]
# 제품 특징 태그 번역
TAG_KO = {
    "spf50": "SPF50+",
    "no-white-cast": "백탁 적음",
    "light": "가벼운 제형",
    "moisturizing": "보습",
    "sensitive": "민감 피부",
    "barrier": "장벽 케어",
    "rich": "리치/영양",
    "ceramide": "세라마이드",
    "ha": "히알루론산",
    "hyaluronic": "히알루론산",
    "oily-skin": "지성 피부",
    "sebum": "피지 케어",
    "non-comedogenic": "논코메도제닉",
    "gel": "젤 제형",
    "acne-care": "트러블 케어",
    "bha": "BHA",
    "azelaic": "아젤라익",
    "niacinamide": "나이아신아마이드",
    "zinc": "징크",
    "fragrance-free": "무향",
    "alcohol-free": "무알콜",
    "low-alcohol": "저알콜",
    "cica": "시카",
    "retinoid": "레티노이드",
    "anti-aging": "안티에이징",
    "occlusive": "오클루시브",
    "lotion": "로션",
    "emulsion": "에멀전",
    "cream": "크림",
    "soothing": "진정",
}

# [성분 번역]
# 주요 성분(Featured Ingredients) 번역
ING_KO_FULL = {
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
    "zinc": "징크",
    "retinol": "레티놀",
    "centella asiatica extract": "센텔라(병풀) 추출물",
}

# 간단 성분 표기 (일부 중복 허용)
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

# [규칙 설명]
# 추천 결과에 표시될 이유 텍스트
RULE_KO = {
    "uv_spf": "자외선 지수↑ → SPF 가산",
    "dry_moist": "건조 환경 → 보습/장벽 가산",
    "hot_light": "더운 날씨 → 가벼운 제형 가산",
    "sebum_gel": "피지/모공↑ → 산뜻한 젤 가산",
    "acne_actives": "트러블↑ → BHA/아젤라익/나이아신아마이드 가산",
    "soothing": "민감/홍조 → 진정/무향·저자극 가산",
    "sens_penalty": "민감 시 강산/고알코올 감점",
    "antiaging": "주름↑ → 안티에이징 가산",
    "dry_barrier": "건조↑ → 세라마이드/장벽 가산",
    "sleep_boost": "수면 부족 → 장벽/진정 보강",
    "water_boost": "수분 섭취 낮음 → 보습 보강",
    "wash_boost": "세안 잦음 → 저자극 가산",
    "hot_boost": "뜨거운 세안 → 진정 가산",
    "day_retinol_penalty": "주간 레티놀 제외",
    "texture_bonus": "제형 선호(젤) 가산",
}


# =========================================
# 3. 추천 엔진 규칙 (Scoring Rules)
# =========================================

# 평가 항목 카테고리 (내부 로직용 ID)
CATEGORIES = [
    "SPF30", "SPF50", "Rich_Moist", "Occlusive", "Light_Gel",
    "SebumGel", "BarrierCream", "BHA_Azelaic", "SoothingFF",
    "Strong_Acid", "High_Retinol", "Retinol_PM", "Heavy_Oil", "Ceramide_HA",
]

# [가중치 설정]
# Engine에서 점수를 계산할 때 사용하는 규칙들입니다.
# 예: uv가 high이면 SPF50 점수를 30점 더한다.
RULES = {
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
    "skin_rules": {
        "sebum_high": {"SebumGel": 25, "Heavy_Oil": -15},
        "acne_high": {"BHA_Azelaic": 25, "Occlusive": -10},
        "redness_high": {"SoothingFF": 30, "Strong_Acid": -40, "High_Retinol": -30},
        "wrinkle_high": {"Retinol_PM": 20},
        "dryness_high": {"Ceramide_HA": 25},
    },
    "safety": {
        "night_only": ["Retinol_PM"],
        "ban_if_sensitive": [
            "Strong_Acid", "High_Retinol", "High_Alcohol", "Fragrance",
        ],
    },
}


# =========================================
# 4. 사용자 입력 설정 (UI Config)
# =========================================

# 터미널에서 사용자에게 물어볼 질문 목록과 입력 제한 설정
LIFESTYLE_FIELDS = {
    "sleep_hours_7d": {
        "label": "최근 7일 평균 수면 시간(시간)",
        "type": "float",
        "default": 7.0,
        "min": 0,
        "max": 12,
    },
    "water_intake_ml": {
        "label": "하루 물 섭취량(ml)",
        "type": "int",
        "default": 1500,
        "min": 0,
        "max": 6000,
    },
    "wash_freq_per_day": {
        "label": "하루 세안 횟수(회)",
        "type": "float",
        "default": 2.0,
        "min": 0,
        "max": 10,
    },
    "wash_temp": {
        "label": "세안 온도(hot/normal/cold)",
        "type": "choice",
        "default": "normal",
        "choices": ["hot", "normal", "cold"],
    },
    "sensitivity": {
        "label": "피부가 민감한 편인가요? (yes/no)",
        "type": "choice",
        "default": "no",
        "choices": ["yes", "no"],
    },
}

# 올리브영 데이터 로딩 시 허용할 공식 카테고리 목록 (데이터 검증용)
ALLOWED_OFFICIAL_CATS = {
    "Toner", "Serum", "Essence", "Ampoule", "Cream", "Lotion",
    "Gel", "Balm", "Sunscreen", "Cleanser", "Oil Cleanser",
    "Toner Pads", "Mask", "Sheet Mask", "Moisturizer",
    "Emulsion", "Cleansing Foam", "Cleansing Gel", "Cleansing Oil",
}

# =========================================
# 5. 데이터베이스 설정 (PostgreSQL)
# =========================================

# .env 파일에서 환경변수를 읽어옵니다. (보안 중요)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "port": os.getenv("DB_PORT", "5432")
}

# =========================================
# 6. Skin Analyzer GPT API 설정
# =========================================

# OpenAI 모델명 (예: gpt-4o-mini, gpt-4-turbo 등)
GPT_MODEL_NAME = "gpt-4o-mini"

# 시스템 프롬프트 (피부 분석관 페르소나)
# AI가 이미지를 분석할 때 어떤 역할을 수행해야 하는지 지시합니다.
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
