# services/filters.py
from .config import SKIN_THRESHOLDS


def get_filter_query(condition: str):
    """
    입력된 조건(condition) 문자열을 받아서,
    알맞은 SQL WHERE 절과 파라미터를 반환하는 함수입니다.

    Returns:
        tuple: (sql_fragment, parameter_value)
    """
    # 1. 기준값 로드
    limits = SKIN_THRESHOLDS

    # 2. 조건별 SQL 매핑 테이블 (Dictionary 패턴 사용)
    # 키: 클라이언트가 보낼 조건명
    # 값: (SQL 조건문, 비교할 값)
    filter_map = {
        # [기존 조건]
        "dry": ("AND moisture < %s", limits["dry_limit"]),
        "oily": ("AND sebum > %s", limits["oily_limit"]),
        "sensitive": ("AND redness > %s", limits["sensitive_limit"]),
        "pore": ("AND pores > %s", limits["pore_limit"]),

        # [새로 추가한 조건]
        "acne": ("AND acne > %s", limits["acne_limit"]),  # 트러블 심한 날
        "wrinkle": ("AND wrinkles > %s", limits["wrinkle_limit"]),  # 주름 심한 날

        # [복합 조건 예시: 피부 상태가 아주 좋은 날 (수분 높고 트러블 없음)]
        # 주의: 파라미터가 여러 개면 튜플 대신 리스트 사용 필요 (여기선 단순화)
        "good": ("AND moisture >= 50 AND acne < 20", None)
    }

    # 3. 해당하는 조건 반환 (없으면 None)
    return filter_map.get(condition)