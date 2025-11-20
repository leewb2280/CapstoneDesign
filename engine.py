# engine.py
"""
[핵심 로직 담당]
이 파일은 'SkinCareAdvisor' 클래스를 통해 데이터를 분석하고 결정을 내립니다.
1. 피부 데이터 파생 지표 계산 (건조도, 민감도 등)
2. 피부 나이 추정 알고리즘
3. 제품별 점수 채점 (환경/피부상태/선호도 반영)
4. 아침/저녁 루틴 텍스트 생성
"""

import datetime
from config import *  # config.py의 모든 설정(가중치, 규칙 등) 불러오기


class SkinCareAdvisor:
    def __init__(self, payload: dict):
        """
        클래스 초기화: 외부에서 받은 데이터(payload)를 내부 변수로 저장하고,
        분석에 필요한 2차 지표(metrics)를 즉시 계산합니다.
        payload 구조: { "camera":..., "env":..., "lifestyle":..., "user":..., "time":... }
        """
        self.cam = payload["camera"]  # 카메라/센서 분석 값 (여드름, 주름 등)
        self.env = payload["env"]  # 날씨 환경 (UV, 온도, 습도)
        self.life = payload["lifestyle"]  # 생활습관 (수면, 물 섭취 등)
        self.user = payload["user"]  # 사용자 기본 정보 (나이, 선호 제형)
        self.hour = payload["time"]["hour"]  # 현재 시간 (아침/저녁 구분용)

        # 파생 지표 미리 계산 (건조도, 민감도 등 단순 수치 이상의 결합 지표)
        self.metrics = self._derive_metrics()

    def _derive_metrics(self):
        """
        [내부 함수] 기본 센서 데이터 + 환경 데이터를 결합해
        '복합적인 피부 상태'를 계산합니다.
        예: 피부 수분이 낮고 + 날씨가 건조하면 -> '건조도(dryness)'가 급증함
        """
        sebum = float(self.cam.get("sebum", 50))
        moisture = float(self.cam.get("moisture", 50))
        redness = float(self.cam.get("redness", 30))
        acne = float(self.cam.get("acne", 30))

        # 1. 건조도 계산: 피부 수분값이 낮을수록 높음 + 주변 습도가 낮으면 가산점(+10)
        dryness = max(0, 60 - moisture)
        if self.env.get("humidity", 45) <= 40:
            dryness += 10

        # 2. 민감도 계산: 설문조사(Yes) 혹은 홍조/여드름 수치가 높으면 민감성으로 판단
        is_sensitive_flag = str(self.life.get("sensitivity", "no")).lower() == "yes"
        sensitivity = max(redness, acne, 65 if is_sensitive_flag else 0)

        return {
            "sebum": sebum,
            "dryness": dryness,
            "sensitivity": sensitivity,
            "acne": acne,
            "redness": redness
        }

    def calc_skin_age(self) -> float:
        """
        [피부 나이 계산 알고리즘]
        주름, 모공, 색소, 홍조 등 결점(flaws)이 많을수록 나이가 많게 측정됩니다.
        마지막에 실제 나이를 기준으로 보정하여 너무 터무니없는 값이 나오지 않게 합니다.
        """
        # 주요 지표 가져오기
        wrinkle = float(self.cam.get("wrinkle", 40))
        pore = float(self.cam.get("pore", 50))
        pigm = float(self.cam.get("pigmentation", 40))
        tone = float(self.cam.get("tone", 50))

        # 가중치 합산 (주름이 가장 큰 영향)
        aging_score = (
                0.30 * wrinkle +
                0.15 * pore +
                0.15 * pigm +
                0.10 * self.metrics["redness"] +
                0.05 * self.metrics["acne"] +
                0.10 * self.metrics["dryness"] +
                0.15 * max(0, 50 - tone)
        )

        # 실제 나이 기준 보정 (너무 늙거나 젊게 나오지 않도록 범위 제한)
        user_age = self.user.get("age", 25)
        delta = 0.12 * (aging_score - 50)
        return round(min(80, max(15, user_age + delta)), 1)

    def recommend_products(self, product_db: list) -> dict:
        """
        [제품 추천 메인 함수]
        DB에 있는 모든 제품을 하나씩 꺼내 점수를 매기고(Scoring),
        점수가 가장 높은 Top 3 제품을 반환합니다.
        """
        scored_list = []

        for p in product_db:
            # 개별 제품 채점
            score, detail, evidences = self._score_single_product(p)

            # 0점 이상인 제품만 후보에 등록
            if score > 0:
                scored_list.append({
                    "product": p,
                    "score": round(score, 2),
                    "detail": detail,
                    "evidences": evidences
                })

        # 점수 높은 순서로 정렬 후 상위 3개 자르기
        scored_list.sort(key=lambda x: x["score"], reverse=True)
        top3 = scored_list[:3]

        return {
            "top3": [self._format_product_result(item, i + 1) for i, item in enumerate(top3)],
            "reasons": self._summarize_reasons(top3)
        }

    def _score_single_product(self, p: dict):
        """
        [채점 엔진] 제품 하나에 대해 환경/피부/선호도 적합성을 평가하여 점수를 줍니다.
        """
        score = 0.0
        detail = {}
        evidences = []

        tags = set(p.get("tags", []))  # 제품 태그 (예: #진정, #수분)
        ings = set(p.get("featured_ingredients", []))  # 주요 성분 (예: 시카, 히알루론산)
        cat = p.get("official_category", "")  # 카테고리 (예: 크림, 선크림)

        # --- [A] 환경 점수 (날씨 반영) ---
        # 1. 자외선이 높으면 -> 선케어 제품, SPF50 제품에 가산점
        uv_level = "high" if self.env["uv"] >= 6 else ("low" if self.env["uv"] < 3 else "mod")
        if uv_level in ("high", "very") and (("spf50" in tags) or cat == "Sunscreen"):
            pts = 30
            score += pts
            evidences.append(f"자외선 높음(UV {self.env['uv']}) → 강력 자외선 차단({pts}점)")

        # 2. 날씨가 건조하면 -> 보습/장벽 케어 제품에 가산점
        if self.env["humidity"] <= 40 and any(t in tags for t in ["barrier", "rich", "ceramide", "moisturizing"]):
            pts = 15
            score += pts
            evidences.append(f"건조한 날씨(습도 {self.env['humidity']}%) → 고보습/장벽 케어({pts}점)")

        # 3. 기온이 높으면 -> 끈적이지 않는 산뜻한/젤 제형에 가산점
        if self.env["temperature"] > 26 and any(t in tags for t in ["light", "gel", "non-comedogenic"]):
            pts = 8
            score += pts
            evidences.append(f"더운 날씨({self.env['temperature']}도) → 산뜻한 제형({pts}점)")

        # --- [B] 피부 상태 점수 (개인 맞춤) ---
        # 1. 유분/모공이 많으면 -> 피지 조절 제품
        d_sebum = (0.5 * self.metrics["sebum"] + 0.3 * float(self.cam.get("pore", 50)))
        if d_sebum >= 60 and any(t in tags for t in ["oily-skin", "sebum", "light"]):
            score += 12
            evidences.append(f"유분/모공 고민 → 피지 조절/가벼운 제형(+12점)")

        # 2. 여드름(트러블)이 있으면 -> 진정, 티트리, BHA 성분
        if self.metrics["acne"] >= 60 and any(t in tags for t in ["bha", "azelaic", "acne-care", "tea tree"]):
            score += 14
            evidences.append(f"트러블 지수 높음 → 진정/BHA 성분(+14점)")

        # 3. 민감하거나 홍조가 있으면 -> 시카, 무향, 저자극
        if self.metrics["sensitivity"] >= 60 and any(t in tags for t in ["cica", "soothing", "fragrance-free"]):
            score += 12
            evidences.append(f"민감/홍조 지수 높음 → 시카/저자극(+12점)")

        # --- [C] 사용자 선호도 및 안전성 페널티 ---
        # 1. 사용자가 선호하는 제형(젤/크림)이면 가산점
        pref = self.user.get("pref_texture", "gel")
        if (pref == "gel" and "gel" in tags) or (pref == "cream" and "cream" in tags):
            score += 3
            evidences.append(f"선호 제형({pref}) 일치(+3점)")

        # 2. [안전장치] 낮 시간(06~18시)에는 '레티놀' 성분 제품 추천 금지 (햇빛에 불안정)
        if 6 <= self.hour < 18 and ("retinol" in ings or "retinoid" in tags):
            score = -999  # 점수를 깎아서 추천 목록에서 제외
            evidences.append("주간 레티놀 사용 제한(점수 삭제)")

        return score, detail, evidences

    def _format_product_result(self, item, rank):
        """[헬퍼 함수] 프론트엔드/클라이언트에 보내기 좋게 결과 포맷을 정리합니다."""
        p = item["product"]
        return {
            "rank": rank,
            "name": p["name"],
            "brand": p["brand"],
            "category": CAT_KO.get(p["official_category"], p["official_category"]),
            "score": item["score"],
            "tags": [TAG_KO.get(t, t) for t in p.get("tags", [])[:4]],  # 태그 한글 변환
            "reasons": item["evidences"][:3]  # 가장 중요한 추천 근거 3가지만 표시
        }

    def _summarize_reasons(self, top3):
        """[요약 함수] 추천된 제품들의 공통적인 선정 이유를 한 문장으로 만듭니다."""
        reasons = []
        if self.env["uv"] >= 6: reasons.append(f"UV가 강한 날({self.env['uv']})이라 선케어를 1순위로 챙겼어요.")
        if self.metrics["dryness"] >= 60: reasons.append("피부가 많이 건조해 보여 보습 장벽 제품을 골랐어요.")
        if self.metrics["acne"] >= 60: reasons.append("트러블 진정에 좋은 성분을 우선시했어요.")
        if not reasons: reasons.append("현재 피부 상태와 날씨 밸런스를 고려해 선정했어요.")
        return reasons

    def generate_routine_text(self, top3_products) -> dict:
        """
        [루틴 생성기] 추천된 제품(Top 3)을 사용하여
        실제 따라 할 수 있는 아침/저녁 루틴 가이드를 작성합니다.
        """
        # 추천된 제품을 기능별(선크림, 진정, 보습)로 분류
        slots = {"sun": None, "relief": None, "moist": None}

        for item in top3_products:
            name = f"**{item['name']}**"
            cat = item["category"]
            tags = item.get("tags", [])

            if "선크림" in cat or "SPF" in str(tags):
                if not slots["sun"]: slots["sun"] = name
            elif any(x in str(tags) for x in ["진정", "시카", "트러블"]):
                if not slots["relief"]: slots["relief"] = name
            elif any(x in str(tags) for x in ["보습", "장벽", "히알루론산"]):
                if not slots["moist"]: slots["moist"] = name

        # 기본 템플릿
        am = ["🚿 **아침**: 미온수 세안 → 토너(결 정돈)"]
        pm = ["🌙 **저녁**: 꼼꼼한 세안 → 토너"]

        # [아침 루틴 조립]
        if slots["moist"]:
            am.append(f"→ {slots['moist']} (수분 충전)")
        elif slots["relief"]:
            am.append(f"→ {slots['relief']} (진정 케어)")
        else:
            am.append("→ 가벼운 수분 에센스/로션")

        if slots["sun"]:
            am.append(f"→ {slots['sun']} (자외선 차단 필수!)")
        else:
            am.append("→ **선크림** (집에 있는 제품이라도 꼭 발라주세요)")

        # [저녁 루틴 조립]
        if slots["relief"]: pm.append(f"→ {slots['relief']} (지친 피부 진정)")
        if slots["moist"]: pm.append(f"→ {slots['moist']} (수분막 형성)")
        if not slots["relief"] and not slots["moist"]: pm.append("→ 평소 쓰시는 수분 크림 듬뿍")

        return {"am": am, "pm": pm}