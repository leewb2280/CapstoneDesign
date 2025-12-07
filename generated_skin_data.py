# gemerated_skin_data.py
'''
피부 분석 데이터가 부족하기에 더미로 만드는 파일입니다.
'''

import psycopg2
import random
import uuid
from datetime import datetime, timedelta

# ✅ 기존 config.py에서 설정을 가져옵니다 (핵심!)
from services.config import DB_CONFIG, SKIN_THRESHOLDS

# 테이블 이름 (혹시 다르면 수정하세요)
TABLE_NAME = "analysis_log"


def calculate_total_score(row):
    """
    Total Score = 100 - (5개 부정적 항목 합계 / 5)
    """
    negative_sum = (
            row["acne"] + row["wrinkles"] + row["pores"] +
            row["redness"] + row["pigmentation"]
    )
    return max(0, 100 - int(negative_sum / 5))


def generate_and_insert():
    try:
        # 1. config.py의 DB_CONFIG를 사용하여 접속
        # (**DB_CONFIG는 딕셔너리 내용을 인자로 풀어줍니다)
        print(f"🔌 DB 접속 시도: {DB_CONFIG['host']}...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("✅ DB 연결 성공!")

        # 2. 현재 ID 확인 (중복 방지)
        cur.execute(f"SELECT MAX(id) FROM {TABLE_NAME}")
        max_id = cur.fetchone()[0]
        if max_id is None: max_id = 0
        current_id = max_id + 1

        print(f"ℹ️ ID {current_id}번부터 60개의 데이터를 생성합니다.")

        # 3. 데이터 생성 (이전과 동일한 로직)
        scenarios = ['dry', 'oily', 'sensitive', 'pore', 'acne', 'wrinkle', 'perfect', 'random']
        users = ['test']

        insert_query = f"""
            INSERT INTO {TABLE_NAME} 
            (id, user_id, acne, wrinkles, pores, pigmentation, redness, moisture, sebum, created_at, image_path, total_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for i in range(60):
            scenario = scenarios[i % len(scenarios)]

            # 기본값
            row = {
                "acne": random.randint(5, 45),
                "wrinkles": random.randint(5, 45),
                "pores": random.randint(10, 55),
                "pigmentation": random.randint(5, 45),
                "redness": random.randint(5, 45),
                "moisture": random.randint(35, 80),
                "sebum": random.randint(20, 65)
            }

            # 시나리오 적용 (config.py의 SKIN_THRESHOLDS 기준 참고)
            # 건성: 수분 < 30
            if scenario == 'dry':
                row["moisture"] = random.randint(10, int(SKIN_THRESHOLDS["dry_limit"]) - 1)
            # 지성: 유분 > 70
            elif scenario == 'oily':
                row["sebum"] = random.randint(int(SKIN_THRESHOLDS["oily_limit"]) + 1, 95)
            # 민감성: 홍조 > 50
            elif scenario == 'sensitive':
                row["redness"] = random.randint(int(SKIN_THRESHOLDS["sensitive_limit"]) + 1, 90)
            # 모공 고민: 모공 > 60
            elif scenario == 'pore':
                row["pores"] = random.randint(int(SKIN_THRESHOLDS["pore_limit"]) + 1, 90)
            # 트러블성: 여드름 > 50
            elif scenario == 'acne':
                row["acne"] = random.randint(int(SKIN_THRESHOLDS["acne_limit"]) + 1, 90)
            # 탄력 저하: 주름 > 50
            elif scenario == 'wrinkle':
                row["wrinkles"] = random.randint(int(SKIN_THRESHOLDS["wrinkle_limit"]) + 1, 90)
            # 완벽 피부
            elif scenario == 'perfect':
                for k in row: row[k] = 10
                row["moisture"] = 80

            # 점수 계산 및 기타 데이터
            row["total_score"] = calculate_total_score(row)
            uid = current_id + i
            user_id = random.choice(users)

            # 날짜 랜덤 (최근 60일)
            created_at = (datetime.now() - timedelta(days=random.randint(0, 60))).strftime("%Y-%m-%d %H:%M:%S.%f")
            image_path = f"temp_uploads/{uuid.uuid4()}.jpg"

            cur.execute(insert_query, (
                uid, user_id, row["acne"], row["wrinkles"], row["pores"],
                row["pigmentation"], row["redness"], row["moisture"], row["sebum"],
                created_at, image_path, row["total_score"]
            ))

        conn.commit()
        cur.close()
        conn.close()
        print(f"🎉 데이터 주입 완료! (Total: {current_id + 59}번까지 저장됨)")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("💡 .env 파일이나 config.py 경로를 확인해주세요.")


if __name__ == "__main__":
    generate_and_insert()