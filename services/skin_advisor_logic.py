# skin_advisor_logic.py
"""
[로직 담당]
수집된 데이터(피부, 환경, 사용자)를 분석하여 피부 상태를 진단하고,
최적의 제품과 루틴을 추천하는 알고리즘 엔진입니다.

기능 목록:
1. Metrics Calculation: 파생 지표(건조도, 민감도 등) 계산
2. Skin Age Estimation: 피부 나이 추정
3. Scoring Engine: 제품별 적합도 채점 (가중치 기반)
4. Routine Generator: 개인화된 루틴 텍스트 생성
"""

import datetime
from .config import *


class SkinCareAdvisor:
    def __init__(self, payload: dict):
        """
        분석 엔진 초기화
        """
        self.cam = payload["camera"]        # 센서/AI 분석 데이터
        self.env = payload["env"]           # 날씨 환경 데이터
        self.life = payload["lifestyle"]    # 생활습관 설문 데이터
        self.user = payload["user"]         # 사용자 기본 정보
        self.hour = payload["time"]["hour"] # 시간 데이터

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
        scored_list = []
        for p in product_db:
            score, detail, evidences = self._score_single_product(p)
            if score > 0:
                scored_list.append({
                    "product": p, "score": round(score, 2),
                    "detail": detail, "evidences": evidences
                })

        # 점수순 정렬
        scored_list.sort(key=lambda x: x["score"], reverse=True)

        # [알고리즘 수정] 카테고리별로 1등만 뽑아서 Top 3 구성하기
        final_top3 = []
        seen_categories = set()

        for item in scored_list:
            cat = item["product"]["official_category"]
            # 이미 뽑은 카테고리라면 패스 (단, Top 3가 안 찼으면 계속)
            if cat not in seen_categories:
                final_top3.append(item)
                seen_categories.add(cat)

            if len(final_top3) >= 3:
                break

        # 만약 카테고리가 너무 겹쳐서 3개를 못 채웠으면 나머지도 채움
        if len(final_top3) < 3:
            for item in scored_list:
                if item not in final_top3:
                    final_top3.append(item)
                    if len(final_top3) >= 3: break

        return {
            "top3": [self._format_product_result(item, i + 1) for i, item in enumerate(final_top3)],
            "reasons": self._summarize_reasons(final_top3)
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

        # ---------------------------------------------------------
        # [D] 나이 기반 가산점 (Age Bonus)
        # ---------------------------------------------------------
        user_age = self.user.get("age", 25)

        # 30대 이상이면 '탄력/주름/레티놀' 제품에 가산점 부여
        if user_age >= 30:
            if any(t in tags for t in ["anti-aging", "retinoid", "collagen", "rich"]):
                score += 15
                evidences.append(f"30대 피부 관리({user_age}세) → 안티에이징 케어(+15점)")

        # 20대 초반이고 지성이면 '산뜻한' 제품에 가산점
        elif user_age <= 24 and self.metrics["sebum"] > 50:
            if any(t in tags for t in ["light", "fresh", "pore-care"]):
                score += 10
                evidences.append(f"20대 피지 관리({user_age}세) → 산뜻한 케어(+10점)")


        # ---------------------------------------------------------
        # [E] 안전 규칙 (Safety Rules) - [복구된 기능]
        # ---------------------------------------------------------

        # 1. 낮 시간(06:00 ~ 18:00) 레티놀 추천 금지
        # 레티놀은 자외선을 받으면 피부에 독이 될 수 있어 밤에만 써야 합니다.
        if 6 <= self.hour < 18:
            if "retinol" in ings or "retinoid" in tags:
                score = -999  # 추천 목록에서 즉시 탈락시킴
                evidences.append(f"현재 시간({self.hour}시) → 주간 레티놀 사용 금지(-999점)")

        # 2. 민감성 피부 강한 성분 금지 (final_skin.py 로직 반영)
        is_sensitive = self.metrics["sensitivity"] >= 60 or str(self.life.get("sensitivity")).lower() == "yes"
        if is_sensitive:
            # 고농도 비타민C(Ascorbic Acid), 강한 산(AHA/BHA) 등 자극 성분 체크
            # config.py의 blacklist 활용 가능하지만, 여기서는 직관적으로 태그 체크
            if any(t in tags for t in ["strong_acid", "high_alcohol"]):
                score = -999
                evidences.append("민감성 피부 → 자극 성분 제외(-999점)")

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
        [루틴 생성 업그레이드]
        팀원 코드(final_skin.py)의 디테일한 케어 팁을 이식하여,
        단순 나열이 아닌 '상황별 맞춤 행동 지침'을 제공합니다.
        """
        # 1. 상황 판단 플래그 (Context Flags)
        is_sensitive = self.metrics["sensitivity"] >= 60 or str(self.life.get("sensitivity")).lower() == "yes"
        high_dry = self.metrics["dryness"] >= 60
        high_acne = self.metrics["acne"] >= 60
        high_uv = self.env["uv"] >= 6
        hot_day = self.env["temperature"] >= 28
        dry_env = self.env["humidity"] <= 40
        pref = self.user.get("pref_texture", "gel")

        # 2. 제품 슬롯 매핑 (추천된 제품을 역할별로 분류)
        slots = {"sun": None, "relief": None, "moist": None, "retinol": None}

        for item in top3_products:
            name = f"**{item['name']}**"
            cat = item["category"]
            tags = str(item.get("tags", []))

            # 선크림
            if "선크림" in cat or "SPF" in tags:
                if not slots["sun"]: slots["sun"] = name
            # 레티놀 (밤 전용)
            elif "레티놀" in tags or "retinol" in tags or "안티에이징" in tags:
                if not slots["retinol"]: slots["retinol"] = name
            # 진정/트러블
            elif any(x in tags for x in ["진정", "시카", "트러블", "BHA"]):
                if not slots["relief"]: slots["relief"] = name
            # 보습
            elif any(x in tags for x in ["보습", "장벽", "히알루론산", "크림"]):
                if not slots["moist"]: slots["moist"] = name

        # ---------------------------------------------------------
        # [AM] 아침 루틴 구성
        # ---------------------------------------------------------
        am = []

        # (1) 세안
        if is_sensitive:
            am.append("🚿 **아침**: 폼 클렌저 대신 '물세안'이나 약산성 젤로 가볍게 시작하세요.")
        elif self.metrics["sebum"] >= 60:
            am.append("🚿 **아침**: 밤사이 쌓인 유분 제거를 위해 T존 위주로 꼼꼼히 세안하세요.")
        else:
            am.append("🚿 **아침**: 미온수로 가볍게 씻어 피부 장벽을 지켜주세요.")

        # (2) 토너/에센스
        if dry_env or high_dry:
            am.append("💧 **수분**: 건조한 날씨입니다. 토너를 2번 겹쳐 바르는 '레이어링'을 추천해요.")
        else:
            am.append("💧 **결 정돈**: 토너로 피부결을 정돈해주세요.")

        # (3) 메인 케어 (진정 vs 보습)
        if slots["relief"]:
            am.append(f"🌿 **진정**: {slots['relief']} (자극받은 피부 보호)")
        elif slots["moist"]:
            if hot_day:
                am.append(f"💧 **보습**: {slots['moist']} (덥지 않게 얇게 펴 바르기)")
            else:
                am.append(f"💧 **보습**: {slots['moist']} (수분막 형성)")
        else:
            # 추천 제품에 없으면 일반적인 팁
            if pref == "gel":
                am.append("💧 **보습**: 선호하시는 가벼운 젤 로션으로 산뜻하게 마무리.")
            else:
                am.append("💧 **보습**: 가지고 계신 수분 크림을 얇게 발라주세요.")

        # (4) 선크림 (필수)
        if slots["sun"]:
            if high_uv:
                am.append(f"☀️ **선케어**: {slots['sun']} (UV 강함! 검지 두 마디만큼 충분히)")
            else:
                am.append(f"☀️ **선케어**: {slots['sun']} (외출 20분 전 도포)")
        else:
            am.append("☀️ **선케어**: **선크림**은 선택이 아닌 필수! (집에 있는 제품 꼭 챙기세요)")

        # ---------------------------------------------------------
        # [PM] 저녁 루틴 구성
        # ---------------------------------------------------------
        pm = []

        # (1) 세안 (이중 세안 여부)
        if slots["sun"] or "oil" in pref:
            pm.append("🌙 **저녁**: 선크림/메이크업 잔여물이 남지 않게 '이중 세안' 꼼꼼히!")
        else:
            pm.append("🌙 **저녁**: 하루 종일 쌓인 먼지를 약산성 폼으로 부드럽게 씻어내세요.")

        # (2) 스페셜 케어 (레티놀/트러블)
        if slots["retinol"]:
            pm.append(f"✨ **나이트케어**: {slots['retinol']} (밤에만 사용)")
            pm.append("   💡 Tip: 자극이 느껴지면 '크림 → 레티놀 → 크림' 순서로 발라보세요(샌드위치 법).")

        elif high_acne:
            if slots["relief"]:
                pm.append(f"🚑 **트러블**: {slots['relief']} (고민 부위에 도톰하게 얹기)")
            else:
                pm.append("🚑 **트러블**: 스팟 케어 제품이 있다면 고민 부위에만 톡톡.")

        # (3) 마무리 보습
        if slots["moist"]:
            pm.append(f"🛡️ **잠금**: {slots['moist']} (수분이 날아가지 않게 듬뿍)")
        elif slots["relief"] and not high_acne:  # 진정 제품을 보습 대용으로 쓸 때
            pm.append(f"🌿 **진정**: {slots['relief']} (피부 휴식)")
        else:
            pm.append("🛡️ **보습**: 평소 쓰시는 영양 크림으로 마무리.")

        # (4) 주말 스페셜 팁 (오늘이 금/토요일이면)
        weekday = datetime.datetime.now().weekday()
        if weekday in [4, 5, 6]:  # 금,토,일
            pm.append("🛀 **주말 Tip**: 이번 주는 고생한 피부를 위해 마스크팩 어떠세요?")

        return {"am": am, "pm": pm}