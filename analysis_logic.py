# analysis_logic.py
"""
[핵심 로직 담당]
수집된 데이터(피부, 환경, 사용자)를 분석하여 피부 상태를 진단하고,
최적의 제품과 루틴을 추천하는 알고리즘 엔진입니다.

기능 목록:
1. Metrics Calculation: 파생 지표(건조도, 민감도 등) 계산
2. Skin Age Estimation: 피부 나이 추정
3. Scoring Engine: 제품별 적합도 채점 (가중치 기반)
4. Routine Generator: 개인화된 루틴 텍스트 생성
"""

import datetime
from config import *  # 가중치(RULES), 번역 매핑(CAT_KO 등) 로드


class SkinCareAdvisor:
    def __init__(self, payload: dict):
        """
        분석 엔진 초기화

        Args:
            payload (dict): {
                "camera": {acne, wrinkles, ...},
                "env": {uv, humidity, ...},
                "lifestyle": {sleep, water, ...},
                "user": {age, pref_texture},
                "time": {hour}
            }
        """
        self.cam = payload["camera"]  # 센서/AI 분석 데이터
        self.env = payload["env"]  # 날씨 환경 데이터
        self.life = payload["lifestyle"]  # 생활습관 설문 데이터
        self.user = payload["user"]  # 사용자 기본 정보
        self.hour = payload["time"]["hour"]

        # 파생 지표 즉시 계산 (건조도, 민감도 등)
        self.metrics = self._derive_metrics()

    # ==========================================================================
    # 1. 지표 계산 및 진단 (Analysis)
    # ==========================================================================

    def _derive_metrics(self) -> dict:
        """
        [내부 함수] 기본 데이터들을 결합하여 복합적인 피부 상태 지표를 계산합니다.

        Returns:
            dict: {sebum, dryness, sensitivity, acne, redness}
        """
        sebum = float(self.cam.get("sebum", 50))
        moisture = float(self.cam.get("moisture", 50))
        redness = float(self.cam.get("redness", 30))
        acne = float(self.cam.get("acne", 30))

        # 1. 건조도(Dryness): 수분이 낮을수록 높음 + 건조한 날씨면 가산점
        dryness = max(0, 60 - moisture)
        if self.env.get("humidity", 45) <= 40:
            dryness += 10

        # 2. 민감도(Sensitivity): 설문(Yes) 또는 붉은기/트러블이 심하면 민감성
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
        [피부 나이 추정] 결점(주름, 모공 등)이 많을수록 실제 나이보다 높게 측정됩니다.

        Returns:
            float: 추정된 피부 나이
        """
        # 주요 결점 지표
        wrinkle = float(self.cam.get("wrinkle", 40))
        pore = float(self.cam.get("pore", 50))
        pigm = float(self.cam.get("pigmentation", 40))
        tone = float(self.cam.get("tone", 50))

        # 노화 점수 계산 (주름 가중치가 가장 높음)
        aging_score = (
                0.30 * wrinkle +
                0.15 * pore +
                0.15 * pigm +
                0.10 * self.metrics["redness"] +
                0.05 * self.metrics["acne"] +
                0.10 * self.metrics["dryness"] +
                0.15 * max(0, 50 - tone)
        )

        # 실제 나이 기준 보정 (너무 터무니없는 값 방지)
        user_age = self.user.get("age", 25)
        delta = 0.12 * (aging_score - 50)

        # 최소 15세, 최대 80세로 제한
        return round(min(80, max(15, user_age + delta)), 1)

    # ==========================================================================
    # 2. 제품 추천 엔진 (Scoring Engine)
    # ==========================================================================

    def recommend_products(self, product_db: list) -> dict:
        """
        [메인 추천 함수] 모든 제품에 대해 적합도 점수를 매기고 Top 3를 선정합니다.

        Args:
            product_db (list): 제품 정보 딕셔너리 리스트

        Returns:
            dict: {"top3": [...], "reasons": [...]}
        """
        scored_list = []

        for p in product_db:
            # 개별 제품 채점
            score, detail, evidences = self._score_single_product(p)

            # 0점 이상인 유의미한 제품만 후보 등록
            if score > 0:
                scored_list.append({
                    "product": p,
                    "score": round(score, 2),
                    "detail": detail,
                    "evidences": evidences
                })

        # 점수 내림차순 정렬 후 상위 3개 추출
        scored_list.sort(key=lambda x: x["score"], reverse=True)
        top3 = scored_list[:3]

        return {
            "top3": [self._format_product_result(item, i + 1) for i, item in enumerate(top3)],
            "reasons": self._summarize_reasons(top3)
        }

    def _score_single_product(self, p: dict):
        """
        [채점 로직] config.py의 RULES를 기반으로 제품의 점수를 계산합니다.
        """
        score = 0.0
        detail = {}
        evidences = []

        tags = set(p.get("tags", []))
        ings = set(p.get("featured_ingredients", []))
        cat = p.get("official_category", "")

        # ---------------------------------------------------------
        # [A] 환경 점수 (Environment Rules)
        # ---------------------------------------------------------
        env_rules = RULES["env_rules"]

        # 1. 자외선 (UV)
        uv_val = self.env["uv"]
        uv_level = "very" if uv_val >= 8 else ("high" if uv_val >= 6 else ("mod" if uv_val >= 3 else "low"))

        uv_targets = env_rules["uv"].get(uv_level, {})
        for target, pts in uv_targets.items():
            if (target.lower() in tags) or (target == "SPF50" and cat == "Sunscreen"):
                score += pts
                evidences.append(f"자외선 {uv_level} (UV {uv_val}) → {target} 제품(+{pts}점)")

        # 2. 습도 (Humidity)
        h_val = self.env["humidity"]
        humid_level = "dry" if h_val <= 40 else ("humid" if h_val >= 70 else "normal")

        humid_targets = env_rules["humidity"].get(humid_level, {})
        for target, pts in humid_targets.items():
            # 매핑: Rich_Moist -> moisturizing/rich 등
            if target == "Rich_Moist" and any(t in tags for t in ["moisturizing", "rich", "cream"]):
                score += pts
                evidences.append(f"건조한 날씨(습도 {h_val}%) → 고보습 케어(+{pts}점)")
            elif target == "Light_Gel" and any(t in tags for t in ["light", "gel", "watery"]):
                score += pts
                evidences.append(f"습한 날씨 → 산뜻한 제형(+{pts}점)")

        # 3. 기온 (Temperature)
        t_val = self.env["temperature"]
        temp_level = "hot" if t_val >= 28 else ("cold" if t_val <= 10 else "normal")

        temp_targets = env_rules["temp"].get(temp_level, {})
        for target, pts in temp_targets.items():
            if target == "SebumGel" and any(t in tags for t in ["sebum", "pore", "gel"]):
                score += pts
                evidences.append(f"더운 날씨({t_val}도) → 피지 조절/젤(+{pts}점)")
            elif target == "BarrierCream" and any(t in tags for t in ["barrier", "ceramide", "cream"]):
                score += pts
                evidences.append(f"추운 날씨 → 장벽 보호(+{pts}점)")

        # ---------------------------------------------------------
        # [B] 피부 상태 점수 (Skin Rules)
        # ---------------------------------------------------------
        skin_rules = RULES["skin_rules"]

        # 1. 유분 과다 (Sebum High)
        d_sebum = (0.5 * self.metrics["sebum"] + 0.3 * float(self.cam.get("pore", 50)))
        if d_sebum >= 60:
            targets = skin_rules["sebum_high"]
            for target, pts in targets.items():
                if target == "SebumGel" and any(t in tags for t in ["sebum", "oily-skin"]):
                    score += pts
                    evidences.append(f"유분/모공 고민 → 피지 케어(+{pts}점)")
                elif target == "Heavy_Oil" and ("oil" in tags or "balm" in tags):
                    score += pts  # 감점
                    evidences.append(f"지성 피부 주의 → 오일/밤 감점({pts}점)")

        # 2. 트러블 (Acne High)
        if self.metrics["acne"] >= 60:
            targets = skin_rules["acne_high"]
            for target, pts in targets.items():
                if target == "BHA_Azelaic" and any(t in tags for t in ["bha", "azelaic", "tea tree", "acne-care"]):
                    score += pts
                    evidences.append(f"트러블 지수 높음 → 진정/BHA 성분(+{pts}점)")

        # 3. 민감성/홍조 (Redness High)
        if self.metrics["sensitivity"] >= 60:
            targets = skin_rules["redness_high"]
            for target, pts in targets.items():
                if target == "SoothingFF" and any(t in tags for t in ["cica", "soothing", "mugwort"]):
                    score += pts
                    evidences.append(f"민감/홍조 심함 → 시카/진정(+{pts}점)")

                # 감점 요인 (강한 자극 성분)
                if target == "Strong_Acid" and ("aha" in tags or "bha" in tags):
                    score += pts
                if target == "High_Retinol" and ("retinol" in ings):
                    score += pts

        # ---------------------------------------------------------
        # [C] 사용자 선호도 (User Preferences)
        # ---------------------------------------------------------
        pref = self.user.get("pref_texture", "gel")
        if (pref == "gel" and "gel" in tags) or (pref == "cream" and "cream" in tags):
            score += 5
            evidences.append(f"선호 제형({pref}) 일치(+5점)")

        return score, detail, evidences

    # ==========================================================================
    # 3. 결과 포매팅 및 루틴 생성 (Formatting & Routine)
    # ==========================================================================

    def _format_product_result(self, item, rank):
        """프론트엔드용 JSON 포맷 변환 (한글 태그 적용)"""
        p = item["product"]
        return {
            "rank": rank,
            "name": p["name"],
            "brand": p["brand"],
            "category": CAT_KO.get(p["official_category"], p["official_category"]),
            "score": item["score"],
            "tags": [TAG_KO.get(t, t) for t in p.get("tags", [])[:4]],
            "reasons": item["evidences"][:3]  # 핵심 이유 3가지만 노출
        }

    def _summarize_reasons(self, top3):
        """추천 사유 요약 (AI 코멘트용)"""
        reasons = []
        if self.env["uv"] >= 6: reasons.append(f"UV가 강한 날({self.env['uv']})이라 선케어를 1순위로 챙겼어요.")
        if self.metrics["dryness"] >= 60: reasons.append("피부가 많이 건조해 보여 보습 장벽 제품을 골랐어요.")
        if self.metrics["acne"] >= 60: reasons.append("트러블 진정에 좋은 성분을 우선시했어요.")
        if not reasons: reasons.append("현재 피부 상태와 날씨 밸런스를 고려해 선정했어요.")
        return reasons

    def generate_routine_text(self, top3_products) -> dict:
        """
        [루틴 생성] 추천된 Top 3 제품을 활용하여 아침/저녁 루틴 가이드를 작성합니다.

        Returns:
            dict: {"am": [...], "pm": [...]}
        """
        slots = {"sun": None, "relief": None, "moist": None}

        for item in top3_products:
            name = f"**{item['name']}**"
            cat = item["category"]
            tags = item.get("tags", [])
            tag_str = str(tags)

            if "선크림" in cat or "SPF" in tag_str:
                if not slots["sun"]: slots["sun"] = name
            elif any(x in tag_str for x in ["진정", "시카", "트러블"]):
                if not slots["relief"]: slots["relief"] = name
            elif any(x in tag_str for x in ["보습", "장벽", "히알루론산"]):
                if not slots["moist"]: slots["moist"] = name

        # 아침 루틴 (보습 -> 선케어)
        am = ["🚿 **아침**: 미온수 세안 → 토너(결 정돈)"]
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

        # 저녁 루틴 (진정 -> 보습)
        pm = ["🌙 **저녁**: 꼼꼼한 세안 → 토너"]
        if slots["relief"]: pm.append(f"→ {slots['relief']} (지친 피부 진정)")
        if slots["moist"]: pm.append(f"→ {slots['moist']} (수분막 형성)")
        if not slots["relief"] and not slots["moist"]: pm.append("→ 평소 쓰시는 수분 크림 듬뿍")

        return {"am": am, "pm": pm}