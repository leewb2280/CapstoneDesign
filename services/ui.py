import tkinter as tk
import threading
import asyncio
import os
import sys

# -----------------------------------------------------------
# [1] 경로 설정
# -----------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from services.skin_analyzer import process_skin_analysis


# -----------------------------------------------------------
# [2] 헬퍼 함수
# -----------------------------------------------------------
def draw_gauge(canvas, oil, moisture):
    """유수분 게이지 그리기"""
    canvas.delete("all")

    # 유분 (파랑)
    canvas.create_oval(40, 40, 160, 160, outline="#e0e0e0", width=20)
    canvas.create_arc(40, 40, 160, 160, start=90, extent=-oil * 3.6, outline="#00aaff", width=20, style="arc")
    canvas.create_text(100, 100, text=f"유분\n{int(oil)}%", fill="black", font=("Arial", 12, "bold"))

    # 수분 (초록)
    canvas.create_oval(190, 40, 310, 160, outline="#e0e0e0", width=20)
    canvas.create_arc(190, 40, 310, 160, start=90, extent=-moisture * 3.6, outline="#55ff55", width=20, style="arc")
    canvas.create_text(250, 100, text=f"수분\n{int(moisture)}%", fill="black", font=("Arial", 12, "bold"))


# -----------------------------------------------------------
# [3] 측정 스레드
# -----------------------------------------------------------
def run_measurement_thread():
    measure_button.config(state="disabled", text="분석 중... (약 10초)")
    recommendation_label.config(text="측정 및 분석 중입니다...")

    ui_data = None

    try:
        # 1. 서버 분석 로직 호출
        result = asyncio.run(process_skin_analysis(user_id="demo_user_kiosk", file=None))

        # 2. 결과 추출
        scores = result["scores"]

        # 3. UI 데이터 생성 (reco 삭제함)
        ui_data = {
            "score": result["total_score"],
            "oil": scores.get("sebum", 0),
            "moisture": scores.get("moisture", 0),
            "acne": scores.get("acne", 0),
            "wrinkles": scores.get("wrinkles", 0),
            "pores": scores.get("pores", 0),
            "redness": scores.get("redness", 0),
            "pigmentation": scores.get("pigmentation", 0)
        }
        print(f"✅ 분석 완료: {ui_data}")

    except Exception as e:
        print(f"❌ 분석 실패: {e}")
        ui_data = None

    root.after(0, update_ui, ui_data)


def update_ui(data):
    """화면 갱신 (reco 관련 코드 제거됨)"""
    if data is None:
        recommendation_label.config(text="측정 실패. 다시 시도해주세요.")
        draw_gauge(canvas, 0, 0)
        score_label.config(text="종합 점수: --점")
        # 상세 항목 초기화는 생략 (그대로 둠)
    else:
        # 게이지 & 점수
        draw_gauge(canvas, data['oil'], data['moisture'])
        score_label.config(text=f"종합 점수: {data['score']}점")

        # 5가지 항목 표시
        acne_label.config(text=f"여드름: {data['acne']}")
        wrinkles_label.config(text=f"주름: {data['wrinkles']}")
        pores_label.config(text=f"모공: {data['pores']}")
        redness_label.config(text=f"홍조: {data['redness']}")
        pigmentation_label.config(text=f"색소: {data['pigmentation']}")

        # [수정됨] 복잡한 추천 멘트 대신 고정 멘트 출력
        recommendation_label.config(text="✅ 피부 분석이 완료되었습니다.")

    measure_button.config(state="normal", text="다시 측정하기")


def start_measurement():
    threading.Thread(target=run_measurement_thread, daemon=True).start()


# -----------------------------------------------------------
# [4] GUI 레이아웃
# -----------------------------------------------------------
root = tk.Tk()
root.title("AI SkinCare Kiosk")
# root.attributes('-fullscreen', True) # 실전용
# root.geometry("480x800")  # 테스트용
root.configure(bg="white")
root.bind("<Escape>", lambda e: root.destroy())

# UI 요소들
tk.Label(root, text="AI 스킨케어 분석", font=("Arial", 20, "bold"), bg="white").pack(pady=20)

canvas = tk.Canvas(root, width=350, height=200, bg="white", highlightthickness=0)
canvas.pack()

score_label = tk.Label(root, text="종합 점수: --점", font=("Arial", 18, "bold"), fg="#007bff", bg="white")
score_label.pack(pady=5)

# 상세 항목 (2줄)
detail_frame = tk.Frame(root, bg="white")
detail_frame.pack(pady=10)

row1 = tk.Frame(detail_frame, bg="white")
row1.pack(pady=2)
acne_label = tk.Label(row1, text="여드름: --", font=("Arial", 11), bg="white", width=12)
acne_label.pack(side="left")
redness_label = tk.Label(row1, text="홍조: --", font=("Arial", 11), bg="white", width=12)
redness_label.pack(side="left")
pigmentation_label = tk.Label(row1, text="색소: --", font=("Arial", 11), bg="white", width=12)
pigmentation_label.pack(side="left")

row2 = tk.Frame(detail_frame, bg="white")
row2.pack(pady=2)
wrinkles_label = tk.Label(row2, text="주름: --", font=("Arial", 11), bg="white", width=12)
wrinkles_label.pack(side="left")
pores_label = tk.Label(row2, text="모공: --", font=("Arial", 11), bg="white", width=12)
pores_label.pack(side="left")

# 하단 메시지
tk.Label(root, text="[ 상태 메시지 ]", font=("Arial", 14, "bold"), fg="#d9534f", bg="white").pack(pady=(20, 5))
recommendation_label = tk.Label(root, text="버튼을 눌러 측정을 시작하세요.", font=("Arial", 12), bg="white")
recommendation_label.pack(pady=5)

measure_button = tk.Button(root, text="피부 측정하기",
                           font=("Arial", 24, "bold"),
                           bg="#00aaff", fg="white", relief="flat",
                           height=3,
                           command=start_measurement)
measure_button.pack(side="bottom", pady=30, padx=20, fill="x", ipady=10)

draw_gauge(canvas, 0, 0)
root.mainloop()